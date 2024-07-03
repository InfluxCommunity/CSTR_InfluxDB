import faust
import logging
import json
import numpy as np
from scipy.integrate import odeint
from kafka import KafkaProducer

class CSTRData(faust.Record, serializer='json'):
    Ca: float
    Reactor_Temperature: float

app = faust.App('cstr-controller', broker='kafka://kafka:9092')
data_topic = app.topic('cstr_data', value_type=CSTRData)
tc_topic = app.topic('cstr_control')

# PID parameters
Kc = 4.61730615181 * 2.0
tauI = 0.913444964569 / 4.0
tauD = 0.0

# Control loop function
def pid_control(T_ss, u_ss, t, Tf, Caf, x0):
    u = np.ones(len(t)) * u_ss
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

    # Define the setpoint ramp or steps
    sp = np.ones(len(t)) * T_ss
    for i in range(15):
        sp[i * 20:(i + 1) * 20] = 300 + i * 7.0
    sp[299] = sp[298]

    for i in range(len(t) - 1):
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
        u[i + 1] = op[i]

        # Use the current Ca and T for the initial condition of the next step
        x0 = [Ca[i], T[i]]
        ts = [t[i], t[i + 1]]
        y = odeint(cstr, x0, ts, args=(u[i + 1], Tf, Caf))  # Use u[i + 1]
        Ca[i + 1] = y[-1][0]
        T[i + 1] = y[-1][1]
        pv[i + 1] = T[i + 1]

        # Send Tc to Kafka
        send_tc_to_kafka(op[i])

        # Debugging information
        if i % 50 == 0:
            print(f"Time: {t[i]:.2f}, Setpoint: {sp[i]:.2f}, PV: {pv[i]:.2f}, OP: {op[i]:.2f}, Ca: {Ca[i]:.2f}, T: {T[i]:.2f}")

    op[len(t) - 1] = op[len(t) - 2]
    ie[len(t) - 1] = ie[len(t) - 2]
    P[len(t) - 1] = P[len(t) - 2]
    I[len(t) - 1] = I[len(t) - 2]
    D[len(t) - 1] = D[len(t) - 2]

    return u, T

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
    dTdt = q / V * (Tf - T) \
           + mdelH / (rho * Cp) * rA \
           + UA / V / rho / Cp * (u - T)

    xdot = np.zeros(2)
    xdot[0] = dCadt
    xdot[1] = dTdt
    return xdot

# Maintain integral of error (ie) globally
ie = 0

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to send Tc value to Kafka
def send_tc_to_kafka(tc_value):
    logger.info(f"Sending Tc to Kafka: {tc_value}")
    producer = KafkaProducer(bootstrap_servers='kafka:9092', value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    producer.send('cstr_control', value={"Tc": tc_value})
    producer.flush()

@app.agent(data_topic)
async def process(stream):
    async for event in stream:
        ca = event.Ca
        temp_reactor = event.Reactor_Temperature

        # Define the PID control parameters and initial conditions
        T_ss = 300  # Steady-state temperature
        u_ss = 300  # Steady-state control input
        t = np.linspace(0, 20, 300)  # Time vector
        Tf = 300  # Feed temperature
        Caf = 1  # Feed concentration
        x0 = [ca, temp_reactor]  # Initial conditions

        # Compute Tc value based on your control logic
        _, T = pid_control(T_ss, u_ss, t, Tf, Caf, x0)
        tc = T[-1]  # Use the last temperature value as the control signal

        # Produce the result to the control topic
        await tc_topic.send(value={"Tc": tc})

if __name__ == '__main__':
    app.main()


# Function to send Tc to Kafka
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

# Main execution
if __name__ == "__main__":
    t = np.linspace(0, 10, 301)
    u_ss = 300.0
    T_ss = 324.475443431599

    while True:
        Ca, T = receive_data_from_kafka()
        if Ca is not None and T is not None:
            x0 = [Ca, T]
            u, T = pid_control(T_ss, u_ss, t, 350, 1, x0)
        else:
            logger.error("No valid Ca and T values received, terminating loop")
            break
