import logging
import numpy as np
from scipy.integrate import odeint
from kafka import KafkaProducer, KafkaConsumer
import json
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
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

# Send a test message to Kafka
test_data = {"Tc": 300.0}
producer.send('cstr_control', value=test_data)
producer.flush()
logger.info(f"Sent test data to Kafka: {test_data}")

# Initial Tc value
initial_tc = 300.0

# from IMC tuning
Kc = 4.61730615181 * 2.0
tauI = 0.913444964569 / 4.0
tauD = 0.0

# define CSTR model
def cstr(x, t, u, Tf, Caf):
    Tc = u
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
    dTdt = q / V * (Tf - T) + mdelH / (rho * Cp) * rA + UA / V / rho / Cp * (Tc - T)

    xdot = np.zeros(2)
    xdot[0] = dCadt
    xdot[1] = dTdt
    return xdot

Ca_ss = 0.87725294608097
T_ss = 324.475443431599
x0 = np.empty(2)
x0[0] = Ca_ss
x0[1] = T_ss

u_ss = initial_tc
Tf = 350
Caf = 1

t = np.linspace(0, 10, 301)

Ca = np.ones(len(t)) * Ca_ss
T = np.ones(len(t)) * T_ss
u = np.ones(len(t)) * u_ss

op = np.ones(len(t)) * u_ss
pv = np.zeros(len(t))
e = np.zeros(len(t))
ie = np.zeros(len(t))
dpv = np.zeros(len(t))
P = np.zeros(len(t))
I = np.zeros(len(t))
D = np.zeros(len(t))
sp = np.ones(len(t)) * T_ss

for i in range(15):
    sp[i * 20:(i + 1) * 20] = 300 + i * 7.0
sp[300] = sp[299]

op_hi = 350.0
op_lo = 250.0

pv[0] = T_ss

# Function to send data to Kafka
def send_data_to_kafka(ca, temp_reactor):
    if not np.isnan(ca) and not np.isnan(temp_reactor):
        data = {
            "Ca": ca,
            "Reactor_Temperature": temp_reactor
        }
        producer.send('cstr_data', value=data)
        producer.flush()
        logger.info(f"Sent data to Kafka: {data}")
    else:
        logger.error(f"Attempted to send NaN values to Kafka: Ca={ca}, Reactor_Temperature={temp_reactor}")

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

logger.info("Starting CSTR simulation loop")

# Initial iteration with predefined Tc
logger.info("Initial iteration with predefined Tc")
ts = [0, t[1]]
y = odeint(cstr, x0, ts, args=(initial_tc, Tf, Caf))
Ca[1] = y[-1][0]
T[1] = y[-1][1]
x0[0] = Ca[1]
x0[1] = T[1]
pv[1] = T[1]

send_data_to_kafka(Ca[1], T[1])

# Ready to start-up faust to send msgs and faust can go collect
# the initial value.
if not os.path.isfile("/healthcheck"):
    with open("/healthcheck", "w") as f:
        f.write("healthcheck")

# Main simulation loop
for i in range(1, len(t) - 1):
    logger.info(f"Iteration {i} starting")
    delta_t = t[i + 1] - t[i]
    e[i] = sp[i] - pv[i]
    if i >= 1:
        dpv[i] = (pv[i] - pv[i - 1]) / delta_t
        ie[i] = ie[i - 1] + e[i] * delta_t
    P[i] = Kc * e[i]
    I[i] = Kc / tauI * ie[i]
    D[i] = -Kc * tauD * dpv[i]
    op[i] = op[0] + P[i] + I[i] + D[i]
    if op[i] > op_hi:
        op[i] = op_hi
        ie[i] = ie[i] - e[i] * delta_t
    if op[i] < op_lo:
        op[i] = op_lo
        ie[i] = ie[i] - e[i] * delta_t
    ts = [t[i], t[i + 1]]
    logger.info("Waiting to receive message from Kafka...")
    try:
        u[i + 1] = receive_tc_from_kafka()
        if u[i + 1] is None:
            logger.error("No valid Tc value received, breaking loop.")
            break
    except Exception as e:
        logger.error(f"Error receiving Tc: {e}")
        break
    y = odeint(cstr, x0, ts, args=(u[i + 1], Tf, Caf))
    Ca[i + 1] = y[-1][0]
    T[i + 1] = y[-1][1]
    if not np.isnan(Ca[i + 1]) and not np.isnan(T[i + 1]):
        x0[0] = Ca[i + 1]
        x0[1] = T[i + 1]
        pv[i + 1] = T[i + 1]
        send_data_to_kafka(Ca[i + 1], T[i + 1])
    else:
        logger.error(f"Encountered NaN values in iteration {i}: Ca={Ca[i + 1]}, T={T[i + 1]}")
        break

op[len(t) - 1] = op[len(t) - 2]
ie[len(t) - 1] = ie[len(t) - 2]
P[len(t) - 1] = P[len(t) - 2]
I[len(t) - 1] = I[len(t) - 2]
D[len(t) - 1] = D[len(t) - 2]

data = np.vstack((t, u, T)).T
np.savetxt('data_doublet_steps.txt', data, delimiter=',')

producer.close()
consumer.close()

# Add a simple test run to check message reception
if __name__ == "__main__":
    logger.info("Starting test run...")
    try:
        tc = receive_tc_from_kafka()
        logger.info(f"Received Tc: {tc}")
    except Exception as e:
        logger.error(f"Error receiving message from Kafka: {e}")
