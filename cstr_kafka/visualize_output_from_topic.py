import matplotlib.pyplot as plt
import json

# File paths
input_file = 'output_pid_control_topic_raw.txt'
output_file = 'output.json'

# Function to add commas after each line in a file
def add_commas_to_file(input_file, output_file):
    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        lines = infile.readlines()
        for line in lines:
            line = line.strip()  # Remove any leading/trailing whitespace
            outfile.write(f'{line},\n')
    print(f'Added commas after each line in {input_file} and saved to {output_file}')

# Function to read JSON objects from a file
def read_json_objects(file_path):
    with open(file_path, 'r') as file:
        data = file.read().splitlines()
    return [json.loads(line.rstrip(',')) for line in data]

# Function to visualize the data
def visualize_data(data):
    Ca_values = [item['Ca'] for item in data]
    T_values = [item['T'] for item in data]
    u_values = [item['u'] for item in data]
    setpoint_values = [item['setpoint'] for item in data]
    ie_values = [item['ie'] for item in data]

    time = list(range(len(data)))

    plt.figure(figsize=(12, 8))

    plt.subplot(3, 1, 1)
    plt.plot(time, Ca_values, label='Ca')
    plt.xlabel('Time')
    plt.ylabel('Ca')
    plt.legend()

    plt.subplot(3, 1, 2)
    plt.plot(time, T_values, label='T')
    plt.plot(time, setpoint_values, label='Setpoint')
    plt.xlabel('Time')
    plt.ylabel('T and Setpoint')
    plt.legend()

    plt.subplot(3, 1, 3)
    plt.plot(time, u_values, label='u')
    plt.xlabel('Time')
    plt.ylabel('u')
    plt.legend()

    plt.tight_layout()
    plt.show()

# Add commas to input file and save to output file
add_commas_to_file(input_file, output_file)

# Read data from the output file
data = read_json_objects(output_file)

# Visualize the data
visualize_data(data)