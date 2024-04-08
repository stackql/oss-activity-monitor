## Building the container

```bash
docker build --no-cache -t oss-activity-monitor .
```

## Running the container

```bash
docker run --env-file .env oss-activity-monitor
```

docker run -e  your-container-name



## Stopping the container

```bash
docker stop $(docker ps -a -q --filter ancestor=oss-activity-monitor)
```