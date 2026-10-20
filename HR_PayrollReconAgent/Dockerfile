# ===========================================================================
# Stage 1 — Build React/Vite/Tailwind Frontend (HR_PayrollReconAgent)
# ===========================================================================
FROM node:22-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci && npm install --no-save @rolldown/binding-linux-x64-gnu @tailwindcss/oxide-linux-x64-gnu

COPY frontend/ ./
RUN npm run build

# ===========================================================================
# Stage 2 — Python 3.12 Runtime (FastAPI + SPA on Port 8080)
# ===========================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    GOOGLE_GENAI_USE_VERTEXAI=1 \
    GOOGLE_CLOUD_PROJECT=gemini-enterprise-demo-498212 \
    GOOGLE_CLOUD_LOCATION=us-central1 \
    GEMINI_FLASH_MODEL=gemini-2.5-flash

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

RUN useradd --create-home --uid 1001 appuser && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend

EXPOSE 8080

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
