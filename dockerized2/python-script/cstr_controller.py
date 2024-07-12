import numpy as np
from scipy.integrate import odeint
from kafka import KafkaProducer, KafkaConsumer
import json
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka setup
producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BROKER_ADDRESS'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

consumer = KafkaConsumer(
    'cstr_control',
    bootstrap_servers=os.getenv('KAFKA_BROKER_ADDRESS'),
    auto_offset_reset='earliest',
    enable_auto_commit=False,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
    consumer_timeout_ms=10000,  # Increased timeout
)

# Define CSTR model
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

# Simulation function
def simulate_cstr(u, Tf, Caf, x0, t):
    logger.info("Entered simulate_cstr function")
    Ca = np.ones(len(t)) * x0[0]
    T = np.ones(len(t)) * x0[1]
    for i in range(len(t) - 1):
        ts = [t[i], t[i + 1]]
        logger.info(f"Calling odeint for iteration {i} with x0={x0}, u[i+1]={u[i+1]}, Tf={Tf}, Caf={Caf}")
        y = odeint(cstr, x0, ts, args=(u[i+1], Tf, Caf))
        Ca[i + 1] = y[-1][0]
        T[i + 1] = y[-1][1]
        x0[0] = Ca[i + 1]
        x0[1] = T[i + 1]

        logger.info(f"Iteration {i}: Ca={Ca[i + 1]}, T={T[i + 1]}, Tc={u[i+1]}")
        
        # Send data to Kafka
        logger.info("Sending data to Kafka from simulate_cstr")
        send_data_to_kafka(Ca[i + 1], T[i + 1])
        
        # Receive Tc from Kafka
        tc = receive_tc_from_kafka()
        if tc is not None:
            logger.info(f"Received new Tc: {tc}, updating u[i+1]")
            u[i + 1] = tc
        else:
            logger.error("No valid Tc value received")
            # u[i + 1] = u[i]

    return Ca, T

# Main loop to continuously run the simulation
if __name__ == "__main__":
    t = np.linspace(0, 10, 301)
    x0 = [0.87725294608097, 324.475443431599]
    u_ss = 300.0

    max_iterations = 1  # Adjust as needed
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        logger.info(f"Iteration value: {iteration}")

        # Initial Tc value
        initial_tc = 300.0
        u = np.ones(301) * initial_tc

        logger.info("Starting simulation")
        # Run simulation
        Ca, T = simulate_cstr(u, 350, 1, x0, t)
        logger.info("Simulation completed")

        # Update x0 for the next iteration
        x0 = [Ca[-1], T[-1]]

    logger.info("Completed execution, exiting...")

    # Close Kafka producer and consumer
    producer.close()
    consumer.close()
