# heartbeat-forwarder/Dockerfile
FROM python:3.12-alpine

# install dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev \
 && pip install --no-cache-dir paho-mqtt requests

# copy bridge script
WORKDIR /app
COPY bridge.py .

# run in foreground, unbuffered
CMD ["python", "-u", "bridge.py"]
