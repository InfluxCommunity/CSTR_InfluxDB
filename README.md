# CSTR_InfluxDB
This project aims to use Kafka, Faust, and InfluxDB to monitor a digital twin of a CSTR (continous stirred tank reactor) and a PID controller for a cooling jacket for the CSTR. 



`dockerized` contains a working example and integration with InfluxDB but the CSTR and controller logic is wrong. 

`dockerized2` contains the correct CSTR logic but there are issues with  

Both repos contain this structure:
├── docker-compose.yml
├── faust_app
│   ├── Dockerfile
│   ├── faust_app.py
│   └── requirements.txt
├── python-script
│   ├── Dockerfile
│   ├── cstr_controller.py
│   ├── kafka_consumer_test.py
│   ├── kafka_producer_test.py
│   └── requirements.txt
├── telegraf
│   └── telegraf.conf

You can also run the CSTR logic sperately with `python3 pid_control.py`
