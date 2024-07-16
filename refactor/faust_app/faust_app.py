import faust
import logging
import json
import numpy as np
from scipy.integrate import odeint
from kafka import KafkaProducer, KafkaConsumer

class CSTRData(faust.Record, serializer='json'):
    Ca: float
    Reactor_Temperature: float
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

# Function to send Tc, temperature of the cooling jacket to Kafka. Tc = u = op[i]
def send_tc_to_kafka(tc):
    if not np.isnan(tc):
        data = {
            "Tc": tc
        }
        producer.send('cstr_control', value=data)
        producer.flush()
        logger.info(f"Sent Tc to Kafka: {data}")
    else:
        logger.error(f"Attempted to send NaN value to Kafka: Tc={tc}")

# Function to receive data from Kafka
def receive_data_from_kafka():
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
                    if not np.isnan(value["Ca"]) and not np.isnan(value["Reactor_Temperature"]):
                        return value["Ca"], value["Reactor_Temperature"]
                    else:
                        logger.error(f"Received NaN value for Ca or Reactor_Temperature: {value}")
                except (KeyError, json.JSONDecodeError) as e:
                    logger.error(f"Error processing message: {e}")
            else:
                logger.warning("Received an empty message or invalid JSON")
        logger.info(f"Attempt {attempt + 1} failed, retrying...")
        consumer.poll(timeout_ms=5000)
    logger.info("Exiting receive_data_from_kafka after 5 attempts")
    return None, None


# PID parameters
Kc = 4.61730615181 * 2.0
tauI = 0.913444964569 / 4.0
tauD = 0.0


# This function implements the PID control loop for the CSTR. 
# T_ss: Steady-state temperature.
# u_ss: Steady-state control input.
# t: Array of time points.
# Tf: Feed temperature.
# Caf: Feed concentration of A.
# x0: Initial state vector [Ca0, T0].
# Ca: the concentration of A in the the reactor. 
# T: the temperature of the reactor. 

# Returns: Control input (u) and temperature (T) over time.
# Where the control input (u) is the temperature of the cooling jacket and the temperatuer (T) is the temperature of the tank.  

def pid_control(T_ss, u_ss, t, Tf, Caf, x0, sp):
    op = np.ones(len(t)) * u_ss
    pv = np.zeros(len(t))
    e = np.zeros(len(t))
    ie = np.zeros(len(t))
    dpv = np.zeros(len(t))
    P = np.zeros(len(t))
    I = np.zeros(len(t))
    D = np.zeros(len(t))

    # Initialize Ca and T arrays
    Ca = np.ones(len(t)) * x0[0]
    T = np.ones(len(t)) * x0[1]

    # Upper and Lower limits on OP
    op_hi = 350.0
    op_lo = 250.0

    pv[0] = T_ss

    delta_t = t[1] - t[0]
    e[1] = sp - pv[1]
    dpv[1] = (pv[1] - pv[0]) / delta_t
    ie[1] = ie[0] + e[1] * delta_t
    P[1] = Kc * e[1]
    I[1] = Kc / tauI * ie[1]
    D[1] = -Kc * tauD * dpv[1]
    op[1] = u_ss + P[1] + I[1] + D[1]
    if op[1] > op_hi:
        op[1] = op_hi
        ie[1] = ie[1] - e[1] * delta_t
    if op[1] < op_lo:
        op[1] = op_lo
        ie[1] = ie[1] - e[1] * delta_t
    u = op[1]

    
    
    pv[i + 1] = T[i + 1]

    op[len(t) - 1] = op[len(t) - 2]
    ie[len(t) - 1] = ie[len(t) - 2]
    P[len(t) - 1] = P[len(t) - 2]
    I[len(t) - 1] = I[len(t) - 2]
    D[len(t) - 1] = D[len(t) - 2]

    return u



@app.agent(data_topic)
async def process(stream):
    async for event in stream:
        ca = event.Ca
        temp_reactor = event.Reactor_Temperature
        sp_counter = event.sp_counter

        # Compute Tc value based on your control logic
        _, T = pid_control(T_ss, u_ss, t, Tf, Caf, x0)
        tc = T[-1]  # Use the last temperature value as the control signal
        

        # Produce the result to the control topic
        await tc_topic.send(value={"Tc": tc})

# Main execution
if __name__ == "__main__":
    # Initialize Value
    # Time steps 
    # TODO: assuming I can keep this interval the same double check and see how to incorporat "loop logic" back with kafka
    # Originally was t = np.linspace(0, 10, 301) for the loop we'll make it 10 seconds apart and see how we can add looping back/bouncing back and forth with kafka later. 
    t = [0,10]
    # Initial steady state temperature of the cooling jacket. 
    u_ss = 300.0
    # Initial steady state temperature. Primarily used to set the desired setpoint for temperature control.
    T_ss = 324.475443431599
    # Temperature of the feed
    Tf = 350
    # Concentration A of the feed
    Caf = 1 
    #Initial set point
    sp = T_ss

    # TODO sp value needs to icrease by 7.0 every 20 timesteps or counters so need to include a counter 


    # Get current Ca and T values from the cstr_data topic 
    Ca, T = receive_data_from_kafka()
    if Ca is not None and T is not None:
            x0 = [Ca, T]
            u = pid_control(T_ss, u_ss, t, 350, 1, x0, sp)
            
            # Log the new values
            logger.info(f"New Ca: {Ca}, New Reactor Temperature: {T}")

        else:
            logger.error("No valid Ca and T values received, terminating loop")
            break
            
    # Create the new initial state vector [Ca0, T0]
    x0 = [Ca, T]

    # Find the new temperature of the cooling jacket 
    u = pid_control(T_ss, u_ss, t, 350, 1, x0)

    # Send the new cooling jacket temperature to the kafka topic "cstr_control"


    # Close Kafka producer and consumer
    producer.close()
    consumer.close()
