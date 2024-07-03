# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install numpy
RUN pip install numpy

# Copy the current directory contents into the container at /app
COPY . .

# Run faust_app.py when the container launches
CMD ["faust", "-A", "faust_app", "worker", "-l", "info"]

