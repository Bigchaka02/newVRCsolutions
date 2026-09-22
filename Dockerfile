# One container runs the whole store: the built site and the API on one port.
# Works on Render, Railway, Fly.io or any VPS. Mount a volume at /data so the
# SQLite database (orders, messages) survives redeploys.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    SERVE_STATIC=true \
    DATABASE_URL=sqlite:////data/vrc.db

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .
RUN python build.py && mkdir -p /data

WORKDIR /app/backend
EXPOSE 8000
# Seeding is idempotent: it upserts the catalog from data/products.json.
CMD ["sh", "-c", "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
