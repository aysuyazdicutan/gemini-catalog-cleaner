#!/bin/bash
set -e
PORT="${PORT:-8000}"
celery -A celery_app.celery_app worker --loglevel=info --concurrency=2 &
exec uvicorn api:app --host 0.0.0.0 --port "$PORT"
