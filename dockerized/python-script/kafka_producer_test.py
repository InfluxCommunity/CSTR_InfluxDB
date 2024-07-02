# kafka_producer_test.py
import logging
import json
from kafka import KafkaProducer
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Kafka setup
producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BROKER_ADDRESS'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Send a test message to Kafka
test_data = {"Tc": 300.0}
producer.send('cstr_control', value=test_data)
producer.flush()
logger.info(f"Sent test data to Kafka: {test_data}")
