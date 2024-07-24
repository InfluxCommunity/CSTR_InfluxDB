import faust
import numpy as np
from scipy.integrate import odeint


app = faust.App(
    'cstr_model',
    broker='kafka://localhost:9092',
    store='memory://',
    value_serializer='json',
    web_port=6066
)

cstr_topic = app.topic('cstr')
pid_control_topic = app.topic('pid_control')

# Initial Values
process_count = 0
max_iterations = 300
# Tf and Caf are constant values of the feed. 
Tf = 350
Caf = 1
ts = [0,0.03333]  
initial_Ca = 0.87725294608097
initial_T = 324.475443431599

print("Running cstr_model script with unique ID: 12345")


def cstr_model_func(x, t, u, Tf, Caf):
    Ca, T = x
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

    return [dCadt, dTdt]

def simulate_cstr(Ca, T, ts, u, Tf, Caf):
    x0 = [Ca, T]
    y = odeint(cstr_model_func, x0, ts, args=(u, Tf, Caf))
    new_Ca = y[-1][0]
    new_T = y[-1][1]
    return new_Ca, new_T

@app.agent(cstr_topic)
async def cstr(cstr):
    global process_count
    async for Ca_T_values in cstr:
        Ca = Ca_T_values.get('Ca')
        T = Ca_T_values.get('T')
        print(f"cstr func")
        print(f"Received Ca cstr: {Ca}, T: {T}")

@app.agent(pid_control_topic)
async def consume_u(events):
    global process_count
    print("Starting PID control loop")
    initial_values = {
        'Ca': initial_Ca,
        'T': initial_T
    }
    print(f"Sending initial values: Ca: {initial_Ca}, T: {initial_T}")
    await cstr_topic.send(value=initial_values)

    async for event in events:
        if process_count >= max_iterations:
            await app.stop()
            break
        u = event.get('u')
        Ca = event.get('Ca')
        T = event.get('T')
        print(f"Into simulate_cstr u: {u}, Into simulate_cstr Ca: {Ca}, Into simulate_cstr T: {T}")
        if u is not None and Ca is not None and T is not None:
            new_Ca, new_T = simulate_cstr(Ca, T, ts, u, Tf, Caf)
            new_values = {
                'Ca': new_Ca,
                'T': new_T,
            }
            print(f"consume sent")
            print(f"Received u: {u}, Computed new Ca: {new_Ca}, new T: {new_T}")
            await cstr_topic.send(value=new_values)
            process_count += 1

if __name__ == '__main__':
    app.main()
