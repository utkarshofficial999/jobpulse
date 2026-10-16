from src.core.database import SessionLocal
from src.core.logging import logger
from src.modules.sources.repository import SourceRepository
from src.modules.discovery.service import crawl_source
from src.modules.deduplication.service import DeduplicationService
from src.modules.verification.service import VerificationService
from src.modules.embeddings.service import EmbeddingService
from src.workers.celery_app import celery_app


@celery_app.task(name="src.workers.tasks.schedule_due_sources_task")
def schedule_due_sources_task():
    """
    Periodic scheduler task:
    Picks sources whose next_run_at <= NOW(), leases them, and enqueues individual crawl tasks.
    """
    db = SessionLocal()
    try:
        due_sources = SourceRepository.get_due_sources(db, limit=50)
        logger.info("Scheduler checked due sources", count=len(due_sources))

        for source in due_sources:
            crawl_source_task.delay(source_id=source.id)

        return {"dispatched": len(due_sources)}
    except Exception as e:
        logger.error("Scheduler task failed", error=str(e))
        raise
    finally:
        db.close()


@celery_app.task(
    name="src.workers.tasks.crawl_source_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def crawl_source_task(self, source_id: str):
    """
    Worker task to crawl a specific source.
    """
    logger.info("Executing crawl task", task_id=self.request.id, source_id=source_id)
    try:
        metrics = crawl_source(source_id)
        # Chain post-ingestion processing
        deduplicate_jobs_task.delay()
        generate_embeddings_task.delay()
        return metrics.to_dict()
    except Exception as exc:
        logger.error("Crawl task encountered error", task_id=self.request.id, source_id=source_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="src.workers.tasks.deduplicate_jobs_task")
def deduplicate_jobs_task():
    """
    Worker task to cluster unclustered jobs across sources.
    """
    db = SessionLocal()
    try:
        count = DeduplicationService.batch_deduplicate(db, limit=200)
        logger.info("Deduplication task completed", count=count)
        return {"clustered": count}
    finally:
        db.close()


@celery_app.task(name="src.workers.tasks.verify_jobs_task")
def verify_jobs_task():
    """
    Worker task to verify if active jobs are still open on company career sites.
    """
    db = SessionLocal()
    try:
        summary = VerificationService.batch_verify(db, limit=50)
        logger.info("Verification task completed", **summary)
        return summary
    finally:
        db.close()


@celery_app.task(name="src.workers.tasks.generate_embeddings_task")
def generate_embeddings_task():
    """
    Worker task to generate pgvector embeddings for newly ingested jobs.
    """
    db = SessionLocal()
    try:
        count = EmbeddingService.generate_batch(db, batch_size=100)
        logger.info("Embedding generation task completed", count=count)
        return {"embedded": count}
    finally:
        db.close()


@celery_app.task(name="src.workers.tasks.dispatch_outbox_task")
def dispatch_outbox_task():
    """
    Worker task to drain the notification outbox and dispatch pending alerts.
    """
    from src.modules.notifications.outbox import OutboxService
    db = SessionLocal()
    try:
        summary = OutboxService.drain_outbox(db, batch_size=50)
        return summary
    finally:
        db.close()


@celery_app.task(name="src.workers.tasks.run_9am_daily_digest_task")
def run_9am_daily_digest_task():
    """
    Worker task scheduled at 9:00 AM daily: matches fresh jobs and queues candidate alerts.
    """
    from src.modules.notifications.outbox import OutboxService
    db = SessionLocal()
    try:
        summary = OutboxService.run_daily_digest(db, since_hours=24)
        logger.info("Daily 9:00 AM digest completed", **summary)
        # Immediately drain outbox
        dispatch_outbox_task.delay()
        return summary
    finally:
        db.close()
