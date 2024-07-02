import faust
import json
import logging

class CSTRData(faust.Record, serializer='json'):
    Ca: float
    Reactor_Temperature: float

app = faust.App('cstr-controller', broker='kafka://kafka:9092')
data_topic = app.topic('cstr_data', value_type=CSTRData)
tc_topic = app.topic('cstr_control')

# Maintain integral of error (ie) globally
ie = 0

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.agent(data_topic)
async def process(stream):
    global ie
    async for event in stream:
        ca = event.Ca
        temp_reactor = event.Reactor_Temperature

        # Compute Tc value based on your control logic
        tc = compute_tc(ca, temp_reactor)

        # Produce the result to the control topic
        await tc_topic.send(value=json.dumps({"Tc": tc}))

def compute_tc(ca, temp_reactor):
    global ie
    Kc = 4.61730615181 * 2.0
    tauI = 0.913444964569 / 4.0
    e = temp_reactor - 324.475443431599
    ie += e  # Update integral of error
    tc = 300.0 + Kc * e + Kc / tauI * ie
    
    # Log the PID components and Tc value
    logger.info(f"e: {e}, ie: {ie}, P: {Kc * e}, I: {Kc / tauI * ie}, tc: {tc}")

    return tc

if __name__ == '__main__':
    app.main()
