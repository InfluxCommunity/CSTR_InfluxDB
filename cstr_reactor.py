import numpy as np
from scipy.integrate import odeint

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

# Simulation function
def simulate_cstr(u, Tf, Caf, x0, t):
    Ca = np.ones(len(t)) * x0[0]
    T = np.ones(len(t)) * x0[1]
    for i in range(len(t) - 1):
        ts = [t[i], t[i + 1]]
        y = odeint(cstr, x0, ts, args=(u[i+1], Tf, Caf))
        Ca[i + 1] = y[-1][0]
        T[i + 1] = y[-1][1]
        x0[0] = Ca[i + 1]
        x0[1] = T[i + 1]
    return Ca, T
