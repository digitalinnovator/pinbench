FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
# Harbor's installed-agent adapters need these; baking them in avoids a per-trial apt install
# (which exceeded Harbor's 360 s agent-setup timeout in spike 0001).
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates procps nodejs npm \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pytest==8.4.2
WORKDIR /app
COPY app/ /app/
