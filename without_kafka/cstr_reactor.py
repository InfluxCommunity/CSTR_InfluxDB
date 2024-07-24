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
    dTdt = q / V * (Tf - T) + mdelH / (rho * Cp) * rA + UA / V / rho / Cp * (u - T)
    return [dCadt, dTdt]


def simulate_cstr(x0,ts,u,Tf,Caf):
    y = odeint(cstr, x0, ts, args=(u, Tf, Caf))  # Use u[i + 1]
    return y 


# goal produce Ca and T values here 
# and then send them to PID_control function
# and the PID function calculates the u or T cooling jacket 
