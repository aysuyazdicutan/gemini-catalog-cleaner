from celery import Celery
import os


def make_celery() -> Celery:
    """
    Create and configure Celery application.

    Broker and backend are read from environment variables to make
    local/remote configuration flexible:

    - CELERY_BROKER_URL (default: redis://localhost:6379/0)
    - CELERY_RESULT_BACKEND (default: redis://localhost:6379/1)
    """
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    app = Celery(
        "catalog_worker",
        broker=broker_url,
        backend=result_backend,
    )

    # Basic serializer configuration – we mostly pass primitive types / JSON.
    # include: worker must import these modules so tasks (e.g. process_catalog_job) are registered
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Europe/Istanbul",
        enable_utc=True,
        include=["tasks"],
    )

    return app


celery_app = make_celery()

