FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc

COPY server.py .

EXPOSE 8080

CMD ["python", "server.py"]
