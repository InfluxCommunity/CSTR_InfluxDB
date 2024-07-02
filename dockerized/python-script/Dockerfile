FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Debugging: List the contents of the /app directory
RUN ls -al /app

# CMD ["python", "kafka_producer_test.py"]  # Change this to test the producer
# CMD ["python", "kafka_consumer_test.py"]  # Change this to test the consumer
CMD ["python", "cstr_controller.py"]

# Keep the container running for debugging
# CMD ["tail", "-f", "/dev/null"]
