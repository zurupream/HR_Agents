FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY scheduler /app/scheduler
COPY README.md /app/README.md

EXPOSE 8080

CMD ["sh", "-c", "uvicorn scheduler.webapp:app --host 0.0.0.0 --port ${PORT:-8080}"]
