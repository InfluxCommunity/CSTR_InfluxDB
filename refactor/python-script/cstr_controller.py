import numpy as np
from scipy.integrate import odeint
from kafka import KafkaProducer, KafkaConsumer
import json
import logging
import os

#The purpose of this script is to calculate the Ca (concentration of the reactor) and T (temperature of the reactor) value.
#It is responsible for using the initial steady state values to calculate the first Ca and T values. 
#Ca and T values are then sent to a kafka topic, "cstr_data". 
#It will also read ts (time steps) and u (temperautre of the cooling jacket) values and from a kafka topic, "pid_values". 
#And use these values to calculate the subsequent Ca and T values. 


class CSTRData(faust.Record, serializer='json'):
    Tc: float
    Setpoint_counter: float 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = faust.App('cstr-controller', broker='kafka://kafka:9092')
data_topic = app.topic('cstr_data', value_type=CSTRData)
tc_topic = app.topic('cstr_control')

#Initialize the producer
producer = KafkaProducer(bootstrap_servers='kafka:9092', value_serializer=lambda v: json.dumps(v).encode('utf-8'))
# Initialize Kafka consumer
consumer = KafkaConsumer('cstr_data', bootstrap_servers='kafka:9092', value_deserializer=lambda m: json.loads(m.decode('utf-8')))


# Function to send data to Kafka
def send_data_to_kafka(ca, temp_reactor):
    if not np.isnan(ca) and not np.isnan(temp_reactor):
        data = {
            "Ca": float(ca),
            "Reactor_Temperature": float(temp_reactor)
        }
        producer.send('cstr_data', value=data)
        producer.flush()
        logger.info(f"Sent data to Kafka: {data}")
        # Once the initial value is sent to Kafka, create a healthcheck file
        if not os.path.isfile("/healthcheck"):
            with open("/healthcheck", "w") as f:
                f.write("healthcheck")
    else:
        logger.error(f"Attempted to send values to Kafka: Ca={ca}, Reactor_Temperature={temp_reactor}")

# Function to receive Tc from Kafka
def receive_tc_from_kafka():
    logger.info("Waiting to receive message from Kafka...")
    for attempt in range(5):  # Retry up to 5 times
        for message in consumer:
            logger.debug(f"Raw message from Kafka: {message}")
            if message.value is not None:
                logger.info(f"Received message from Kafka: {message.value}")
                try:
                    value = message.value
                    if isinstance(value, str):
                        value = json.loads(value)
                    if not np.isnan(value["Tc"]):
                        return value["Tc"]
                    else:
                        logger.error(f"Received NaN value for Tc: {value}")
                except (KeyError, json.JSONDecodeError) as e:
                    logger.error(f"Error processing message: {e}")
            else:
                logger.warning("Received an empty message or invalid JSON")
        logger.info(f"Attempt {attempt + 1} failed, retrying...")
        consumer.poll(timeout_ms=5000)
    logger.info("Exiting receive_tc_from_kafka after 5 attempts")
    return None

# This function defines the model of the Continuous Stirred Tank Reactor (CSTR). It is purely a differential equation function.
# x: State vector, where x[0] is the concentration of A (Ca) and x[1] is the temperature (T).
# t: Time (not used in the equations, but required by odeint).
# u: Control input (e.g., the temperature of the cooling jacket).
# Tf: Feed temperature.
# Caf: Feed concentration of A.

# Returns: Derivatives of the state variables (dCadt and dTdt).

def cstr(x, t, u, Tf, Caf):
    Ca = x[0]
    T = x[1]

    q = 100
    V = 100
    rho = 1000
    Cp = 0.239
    mdelH = 5e4
    EoverR = 8750
    k0 = 7.2e10
    UA = 5e4
    rA = k0 * np.exp(-EoverR / T) * Ca

    dCadt = q / V * (Caf - Ca) - rA
    dTdt = q / V * (Tf - T) + mdelH / (rho * Cp) * rA + UA / V / rho / Cp * (u - T)

    xdot = np.zeros(2)
    xdot[0] = dCadt
    xdot[1] = dTdt
    return xdot

# This is a simulation function. This function simulates the CSTR over a given time period. 
# It integrates the CSTR model using the odeint function to obtain the concentration and temperature profiles over time based on the initial conditions and control inputs.
    # Inputs:
    # u: Array of control inputs (e.g., cooling jacket temperatures) over time.
    # Tf: Feed temperature.
    # Caf: Feed concentration of A.
    # x0: Initial state vector [Ca0, T0].
    # t: Array of time points.
    # Returns: 
    # y: an arrays of concentration (Ca) and temperature (T) at a time point.
def simulate_cstr(x0,ts,u,Tf,Caf):
    # The odeint function from the SciPy library to solve a system of ordinary differential equations (ODEs).
        # Specifically:
        # cstr: the function that defines the system of ODEs representing the reactor dynamics. It calculates the rates of change of the concentration (dCa/dt) and temperature (dT/dt) based on the current state and inputs.
        # x0: provides the starting values of Ca and T at the initial time.
        # ts: This is the time points at which the solution is to be computed. It is a sequence of time values over which the ODEs are solved.
        # args: This is a tuple of additional arguments to pass to the cstr function. In this case, it includes u[i+1] (the control input for the cooling jacket temperature), Tf (feed temperature), and Caf (feed concentration).
    y = odeint(cstr, x0, ts, args=(u, Tf, Caf))  # Use u[i + 1]
    return y 


@app.agent(tc_topic)
async def process(stream):
    async for event in stream:
        Tc = event.tc
        # Compute new Ca and T values to send to kafka topic cstr_data
        y = simulate_cstr(x0, t, Tc, Tf, Caf)
        Ca = y[-1][0]
        T = y[-1][1]
        send_data_to_kafka(Ca, T)

        # Produce the result to the data topic
        await data_topic.send(value={"Ca": Ca, "Reactor_Temperature": T})


# Main loop to continuously run the simulation
if __name__ == "__main__":
    # Time steps 
    # TODO: assuming I can keep this interval the same double check and see how to incorporat "loop logic" back with kafka
    # Originally was t = np.linspace(0, 10, 301) for the loop we'll make it 10 seconds apart and see how we can add looping back/bouncing back and forth with kafka later. 
    t = [0,10]
    # Initial Ca (concentration of a in the reactor) and T (temperature of the reactor) values.
    x0 = [0.87725294608097, 324.475443431599]
    # Initial steady state temperature of the cooling jacket
    u_ss = 300.0
    # Temperature of the feed
    Tf = 350
    # Concentration A of the feed
    Caf = 1 
    # Initial sp

    logger.info("Starting simulation")
    # Run simulation with the inititial values to get the first Ca nd T values. 
    y = simulate_cstr(x0, t, u_ss, Tf, Caf)
    # Rember y returns an array where each row corresponds to the state vector [Ca, T] at each time step in ts.
    Ca = y[-1][0]
    T = y[-1][1]
    # Send newly produced Ca and T values based of initial values to kafka topic cstr_data to start the produce/consume cycle. 
    send_data_to_kafka(Ca, T)

    logger.info("Completed execution, exiting...")

    # Close Kafka producer and consumer
    producer.close()
    consumer.close()
