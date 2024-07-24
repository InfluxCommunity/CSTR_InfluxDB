# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Ensure both scripts are executable
RUN chmod +x pid_controller.py cstr_model.py

# Copy the entrypoint script into the image
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Use the entrypoint script to run both scripts
ENTRYPOINT ["/app/entrypoint.sh"]

