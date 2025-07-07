FROM python:3.11-slim
WORKDIR /app
COPY shelly_event_relay.py .
RUN pip install --no-cache-dir paho-mqtt python-dotenv requests
ENTRYPOINT ["python", "shelly_event_relay.py"]
