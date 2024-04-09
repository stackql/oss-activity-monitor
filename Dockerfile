FROM stackql/stackql:latest AS stackql
FROM python:3.11.9-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV LOG_LEVEL=INFO

# copy stackql binary from stackql container
COPY --from=stackql /srv/stackql/stackql /srv/stackql/stackql
RUN chmod +x /srv/stackql/stackql

RUN ls -la /srv/stackql/ && \
    ls -la /srv/stackql/stackql && \
    /srv/stackql/stackql --version

CMD ["python", "./run_monitor.py"]