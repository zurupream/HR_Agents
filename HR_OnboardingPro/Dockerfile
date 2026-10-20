FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Pre-seed the initial HR demo database and offer PDFs inside the image for instant startup
RUN python3 -c "from app.seed import seed_demo_data; seed_demo_data(force_reset=True, base_url='https://hr-onboarding-259388273008.us-central1.run.app')"

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
