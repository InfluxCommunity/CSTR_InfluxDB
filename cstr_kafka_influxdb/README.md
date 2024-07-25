# cstr_kafka 
This directory contains an example of how to model a CSTR with just kafka. 

## Run 
1. Sign up for a free InfluxDB trial here. 
2. Provide your InfluxDB credentials in the [telegraf/telegraf.conf](telegraf/telegraf.conf). 
3.  Start the docker container. Pull this repo, cd into this directory, and run:
    ```
    docker-compose up -d
    ```
4. Visualize your timeseries in InfluxDB. 

## Useful Commands
To delete topics:
```
docker exec -it cstr_kafka_influxdb-kafka-1 /bin/sh

/opt/kafka/bin/kafka-topics.sh --delete --topic cstr --bootstrap-server kafka:9092

/opt/kafka/bin/kafka-topics.sh --delete --topic pid_control --bootstrap-server kafka:9092
```

To create topics:
```
/opt/kafka/bin/kafka-topics.sh --create --topic cstr --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1

/opt/kafka/bin/kafka-topics.sh --create --topic pid_control --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
```

To run apps:
```
faust -A pid_controller worker -l info

faust -A cstr_model  worker -l info
```

Tail the topics:
```
/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic cstr --from-beginning

/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic pid_control --from-beginning
```
