from celery import Celery
from celery.schedules import crontab
from src.config import settings

celery_app = Celery(
    "pulseai_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "schedule-due-sources-every-minute": {
            "task": "src.workers.tasks.schedule_due_sources_task",
            "schedule": 60.0,
        },
        "deduplicate-unclustered-jobs-every-5-minutes": {
            "task": "src.workers.tasks.deduplicate_jobs_task",
            "schedule": 300.0,
        },
        "verify-active-jobs-every-15-minutes": {
            "task": "src.workers.tasks.verify_jobs_task",
            "schedule": 900.0,
        },
        "generate-embeddings-every-2-minutes": {
            "task": "src.workers.tasks.generate_embeddings_task",
            "schedule": 120.0,
        },
        "drain-notification-outbox-every-30-seconds": {
            "task": "src.workers.tasks.dispatch_outbox_task",
            "schedule": 30.0,
        },
        "send-daily-job-alerts-at-9am": {
            "task": "src.workers.tasks.run_9am_daily_digest_task",
            "schedule": crontab(hour=9, minute=0),  # 9:00 AM UTC daily
        },
    },
)
