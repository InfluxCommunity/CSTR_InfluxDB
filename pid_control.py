import numpy as np
import matplotlib.pyplot as plt
from cstr_reactor import simulate_cstr, cstr  # Ensure cstr is imported
from scipy.integrate import odeint


# PID parameters and initial conditions
Kc = 4.61730615181 * 2.0
tauI = 0.913444964569 / 4.0
tauD = 0.0

# Control loop
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
    sp[300] = sp[299]

    # Create plot
    plt.figure(figsize=(10, 7))
    plt.ion()
    plt.show()

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
        ts = [t[i], t[i+1]]
        y = odeint(cstr, x0, ts, args=(u[i + 1], Tf, Caf))  # Use u[i + 1]
        Ca[i + 1] = y[-1][0]
        T[i + 1] = y[-1][1]
        pv[i + 1] = T[i + 1]

        # Debugging information
        if i % 50 == 0:
            print(f"Time: {t[i]:.2f}, Setpoint: {sp[i]:.2f}, PV: {pv[i]:.2f}, OP: {op[i]:.2f}, Ca: {Ca[i]:.2f}, T: {T[i]:.2f}")
        
        # Plotting
        plt.clf()
        plt.subplot(3, 1, 1)
        plt.plot(t[:i + 1], sp[:i + 1], 'r--', label='Setpoint')
        plt.plot(t[:i + 1], pv[:i + 1], 'b-', label='Process Variable (Reactor Temp)')
        plt.ylabel('Reactor Temperature (C)')
        plt.legend(loc='best')

        plt.subplot(3, 1, 2)
        plt.plot(t[:i + 1], op[:i + 1], 'k-', label='Control Output (Cooling Jacket Temp)')
        plt.ylabel('Cooling Jacket Temperature (C)')
        plt.xlabel('Time (sec)')
        plt.legend(loc='best')

        plt.subplot(3, 1, 3)
        plt.plot(t[:i + 1], Ca[:i + 1], 'g-', label='Concentration Ca')
        plt.ylabel('Concentration Ca')
        plt.xlabel('Time (sec)')
        plt.legend(loc='best')

        plt.pause(0.01)
    op[len(t) - 1] = op[len(t) - 2]
    ie[len(t) - 1] = ie[len(t) - 2]
    P[len(t) - 1] = P[len(t) - 2]
    I[len(t) - 1] = I[len(t) - 2]
    D[len(t) - 1] = D[len(t) - 2]

    # Save data to file
    data = np.vstack((t, u, T, Ca, op)).T
    np.savetxt('data_doublet_steps.txt', data, delimiter=',')

    plt.ioff()
    plt.show()

    return u, T

# Main execution
if __name__ == "__main__":
    t = np.linspace(0, 10, 301)
    x0 = [0.87725294608097, 324.475443431599]
    u_ss = 300.0
    T_ss = 324.475443431599

    u, T = pid_control(T_ss, u_ss, t, 350, 1, x0)
