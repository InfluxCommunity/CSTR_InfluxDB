import faust
import logging
import json
import numpy as np
import os


app = faust.App(
    'pid_controller',
    broker='kafka://kafka:9092',
    store='memory://',
    value_serializer='json',  
    web_port=6067
)

cstr_topic = app.topic('cstr')
pid_control_topic = app.topic('pid_control')

# Initial Values

# Initial Values and Constant Values
# To stop the processs after process is run a max iterations. 
process_count = 0
max_iterations = 300
# The setpoint that the operator will have input. The setpoint value icreases by 7.0 every 20 timesteps. 
# setpoint = 1
# time steps, assuming regular time series 
ts = [0,0.03333]
# Initial steady state temperature of the cooling jacket. 
u_ss = 300.0
# Initial steady state temperature. Primarily used to set the desired setpoint for temperature control.
T_ss = 324.475443431599
# Temperature of the feed
Tf = 350
# Concentration A of the feed
Caf = 1 
# Initial setpoint of the reactor, operator controlled. The setpoint value icreases by 7.0 every 20 timesteps. 
sp = u_ss
# Inital Ca
Ca0 = 0.87725294608097
# Initial T 
T0 = 324.475443431599 

# PID parameters
Kc = 9.23461230362
tauI = 0.22836124114
# To retain previous values 
T_previous = T_ss
ie_previous = 0


# This function implements the PID control loop for the CSTR. 
# T_ss: Steady-state temperature.
# u_ss: Steady-state control input.
# t: Array of time points.
# Tf: Feed temperature.
# Caf: Feed concentration of A.
# x0: Initial state vector [Ca0, T0].
# Ca: the concentration of A in the the reactor. 
# T: the temperature of the reactor. 
# ie: The integral of error (IE) is the accumulated sum of past errors over time. It represents the cumulative deviation of the process variable from the setpoint.

# Returns: Control input (u).
# Where the control input (u) is the temperature of the cooling jacket and the temperatuer (T) is the temperature of the tank.  
    # pid_control(T_ss, u_ss, ts, Tf, Caf, ca, t_current, sp, T_previous, ie_previous)
def pid_control(T_ss, u_ss, ts, Tf, Caf, Ca, T, sp, ie_previous):
    """Compute the u value based on PID control."""
    delta_t = ts[1] - ts[0]
    e = sp - T
    if process_count >= 1:
        ie = ie_previous + e * delta_t
    else:
        ie = 0.0
    P = Kc * e
    I = Kc / tauI * ie
    print(f"delta_t: {delta_t}, e: {e}, ie_previous: {ie_previous}, ie: {ie}")  # Debugging print
    op = u_ss + P + I 
    # Upper and Lower limits on OP
    op_hi = 350.0
    op_lo = 250.0
    if op > op_hi:
        op = op_hi
        ie = ie - e * delta_t
    if op < op_lo:
        op = op_lo
        ie = ie - e * delta_t
    u = op
    return u, ie

@app.agent(cstr_topic)
async def process_cstr_events(events):
    global T_previous, sp, process_count, ie_previous
    # first_iteration = True
    async for event in events:
        if process_count >= max_iterations:
            await app.stop()
            break
        ca_current = event.get('Ca')
        t_current = event.get('T')
        print(f"Ca into pid: {ca_current}, T into pid: {t_current}")
        if ca_current is not None and t_current is not None:
            # if first_iteration:
            #     t_current = T_ss  # Use initial T_ss for the first iteration
            #     ca = Caf  # Use initial T_ss for the first iteration
            #     first_iteration = False
            u, ie_current = pid_control(T_ss, u_ss, ts, Tf, Caf, ca_current, t_current, sp, ie_previous)
            control_message = {
                'Ca': ca_current,
                'T': t_current,
                'u': u,
                'setpoint': sp,
                'ie': ie_current
            }
            print(f"Received Ca: {ca_current}, T: {t_current}, Computed u: {u}, Setpoint: {sp}, IE: {ie_current}")
            await pid_control_topic.send(value=control_message)
            T_previous = t_current  # Update the previous temperature value
            ie_previous = ie_current  # Update the previous error value

            # Update the iteration count and setpoint
            process_count += 1
            if process_count % 20 == 0:
                sp += 7.0

if __name__ == '__main__':
    app.main()
