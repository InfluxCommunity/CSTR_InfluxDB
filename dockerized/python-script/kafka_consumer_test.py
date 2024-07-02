# kafka_consumer_test.py
import logging
import json
from kafka import KafkaConsumer
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Kafka setup
consumer = KafkaConsumer(
    'cstr_control',
    bootstrap_servers=os.getenv('KAFKA_BROKER_ADDRESS'),
    auto_offset_reset='earliest',
    enable_auto_commit=False,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
    consumer_timeout_ms=10000,  # Increased timeout
)

# Function to receive a test message from Kafka
def receive_test_message_from_kafka():
    logger.info("Waiting to receive test message from Kafka...")
    for message in consumer:
        logger.debug(f"Raw message from Kafka: {message}")
        if message.value is not None:
            logger.info(f"Received test message from Kafka: {message.value}")
            return message.value
        else:
            logger.warning("Received an empty message or invalid JSON")

# Receive the test message
test_message = receive_test_message_from_kafka()
logger.info(f"Test message received: {test_message}")

