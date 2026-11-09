FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    SHARD_INDEX=0 \
    SHARD_COUNT=2 \
    OLLAMA_HOST="http://ollama.pipeline.svc.cluster.local:11434"

COPY worker.py .
COPY clean.py .

CMD ["python3", "worker.py"]
