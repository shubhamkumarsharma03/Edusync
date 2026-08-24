from celery import Celery
from celery.schedules import crontab

from api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "edusync_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["ingestion.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
)

# Setup Celery Beat
celery_app.conf.beat_schedule = {
    "reingest-all-documents-every-interval": {
        "task": "ingestion.tasks.reingest_all_documents",
        "schedule": crontab(minute=0, hour=f"*/{settings.REINGEST_INTERVAL_HOURS}"),
    },
}
