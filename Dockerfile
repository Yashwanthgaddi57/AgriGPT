# Root Dockerfile — FastAPI backend container
#
# NOTE: run exactly ONE uvicorn worker — APScheduler must execute once.
# Multiple workers would duplicate weather/market alert notifications.
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

# Schema is ensured at startup by app.core.database.init_db()
# (creates missing tables and applies additive column migrations),
# so no separate alembic step is needed here.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
