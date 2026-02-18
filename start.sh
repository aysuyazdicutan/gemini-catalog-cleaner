#!/usr/bin/env bash
# Tek container'da API + Celery worker (Railway vb. için)
# Celery arka planda, uvicorn ön planda (PORT'u tutar)
set -e
PORT="${PORT:-8000}"
celery -A celery_app.celery_app worker --loglevel=info &
exec uvicorn api:app --host 0.0.0.0 --port "$PORT"
