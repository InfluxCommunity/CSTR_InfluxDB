#!/bin/bash

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
until /opt/bitnami/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list; do
  echo "Kafka is not ready yet..."
  sleep 5
done

# Creating topics
echo "Creating Kafka topics..."
/opt/kafka/bin/kafka-topics.sh --delete --topic cstr --bootstrap-server localhost:9092
/opt/kafka/bin/kafka-topics.sh --delete --topic pid_control --bootstrap-server localhost:9092

echo "Kafka topics created successfully!"