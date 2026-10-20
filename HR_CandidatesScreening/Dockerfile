FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY screening_agent/requirements.txt /app/screening_agent/requirements.txt
COPY screening_webapp/requirements.txt /app/screening_webapp/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/screening_agent/requirements.txt -r /app/screening_webapp/requirements.txt

COPY screening_agent /app/screening_agent
COPY screening_webapp /app/screening_webapp

RUN mkdir -p /app/screening_webapp/data/jobs /app/screening_agent/output

EXPOSE 8080

CMD ["sh", "-c", "uvicorn screening_webapp.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
