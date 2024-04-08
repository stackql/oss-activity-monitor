FROM python:3.11.9-alpine3.19

RUN apk update

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV LOG_LEVEL=INFO

CMD ["python", "./run_monitor.py"]
