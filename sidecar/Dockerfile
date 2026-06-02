FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache docker-cli
RUN pip install --no-cache-dir paho-mqtt
COPY sidecar.py .
CMD ["python", "-u", "sidecar.py"]
