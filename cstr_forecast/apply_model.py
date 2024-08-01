import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint
import joblib
import os

# Load the trained model and polynomial transformer
model_path = 'trained_model.pkl'
poly_path = 'poly_transformer.pkl'

if not os.path.exists(model_path) or not os.path.exists(poly_path):
    raise FileNotFoundError("One or more model files are missing. Please check the paths and ensure the files exist.")

model = joblib.load(model_path)
poly = joblib.load(poly_path)

# Define the CSTR model
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

# Steady State Initial Conditions
Ca_ss = 0.87725294608097
T_ss = 324.475443431599
x0 = np.array([Ca_ss, T_ss])

u_ss = 300.0
Tf = 350
Caf = 1

t = np.linspace(0, 10, 301)
Ca = np.ones(len(t)) * Ca_ss
T = np.ones(len(t)) * T_ss
u = np.ones(len(t)) * u_ss

op = np.ones(len(t)) * u_ss
pv = np.zeros(len(t))
sp = np.ones(len(t)) * T_ss

# Define setpoint steps
for i in range(15):
    sp[i * 20:(i + 1) * 20] = 300 + i * 7.0
sp[300] = sp[299]

pv[0] = T_ss

# PID controller parameters
Kc = 4.61730615181 * 1.0
tauI = 0.913444964569 / 8.0
tauD = 0.0
ie = 0  # integral of the error
dpv = 0  # derivative of the process variable

# Loop through time steps
for i in range(len(t) - 1):
    delta_t = t[i + 1] - t[i]
    e = sp[i] - pv[i]
    
    if i >= 1:
        dpv = (pv[i] - pv[i - 1]) / delta_t
        ie += e * delta_t

    P = Kc * e
    I = Kc / tauI * ie
    D = -Kc * tauD * dpv

    # Prepare input for the model
    X_new = np.array([[T[i], Ca[i]]])
    X_new_poly = poly.transform(X_new)

    # Predict Tc using the trained model
    model_output = model.predict(X_new_poly)[0]

    # Combine model output with PID control elements
    u[i + 1] = model_output + P + I + D

    # Ensure Tc remains within bounds
    u[i + 1] = max(250, min(350, u[i + 1]))

    ts = [t[i], t[i + 1]]
    y = odeint(cstr, x0, ts, args=(u[i + 1], Tf, Caf))
    Ca[i + 1] = y[-1][0]
    T[i + 1] = y[-1][1]
    x0[0] = Ca[i + 1]
    x0[1] = T[i + 1]
    pv[i + 1] = T[i + 1]

# Construct results and save data file
data = np.vstack((t, u, T, Ca, sp)).T
np.savetxt('cstr_output.txt', data, delimiter=',')

# Plot the results
plt.figure(1)
plt.subplot(4, 1, 1)
plt.plot(t, u, 'b--', linewidth=3)
plt.ylabel('Cooling T (K)')
plt.legend(['Jacket Temperature'], loc='best')

plt.subplot(4, 1, 2)
plt.plot(t, Ca, 'g-', linewidth=3)
plt.ylabel('Ca (mol/L)')
plt.legend(['Reactor Concentration'], loc='best')

plt.subplot(4, 1, 3)
plt.plot(t, T, 'k:', linewidth=3, label='Reactor Temperature')
plt.plot(t, sp, 'r--', linewidth=2, label='Set Point')
plt.ylabel('T (K)')
plt.xlabel('Time (min)')
plt.legend(loc='best')

plt.show()
