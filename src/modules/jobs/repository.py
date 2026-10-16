from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.core.metrics import CrawlMetrics
from src.modules.discovery.base import RawJobData
from src.modules.sources.models import Source
from src.modules.jobs.models import RawJob, Job
from src.modules.jobs.schemas import NormalizedJob
from src.modules.jobs.hashing import compute_content_hash


class JobRepository:
    """Repository handling persistence of raw audit payloads and canonical job reconciliation."""

    @staticmethod
    def store_raw_jobs(db: Session, source_id: str, raw_jobs: Sequence[RawJobData]) -> int:
        """Stores unparsed raw payloads in raw_jobs table for replayability and audit."""
        if not raw_jobs:
            return 0

        now = datetime.now(timezone.utc)
        db_records = [
            RawJob(
                source_id=source_id,
                external_id=item.external_id,
                payload=item.payload,
                fetched_at=now,
            )
            for item in raw_jobs
        ]
        db.bulk_save_objects(db_records)
        db.flush()
        return len(db_records)

    @classmethod
    def reconcile_jobs(
        cls,
        db: Session,
        source: Source,
        normalized_jobs: list[NormalizedJob],
        crawl_start_time: datetime,
        metrics: CrawlMetrics,
    ) -> None:
        """
        Reconciles normalized jobs with canonical DB records:
        1. Skips unchanged jobs (matching content_hash) while touching last_seen_at.
        2. Updates changed jobs (different content_hash).
        3. Inserts new jobs.
        4. Closes missing jobs (open jobs with last_seen_at < crawl_start_time).
        """
        metrics.discovered = len(normalized_jobs)

        if not normalized_jobs:
            # Safeguard: If feed returned 0 jobs, verify before closing everything
            stmt_active_count = select(Job.id).where(Job.source_id == source.id, Job.status == "open")
            active_count = len(db.execute(stmt_active_count).scalars().all())

            if active_count > 5:
                logger.warning(
                    "Empty feed safeguard triggered: Feed returned 0 jobs but source has active jobs. Skipping mass closure.",
                    source_id=source.id,
                    source_name=source.name,
                    active_count=active_count,
                )
                return

        # Fetch existing canonical jobs for these external IDs
        external_ids = [j.external_id for j in normalized_jobs]
        existing_jobs_map: dict[str, Job] = {}

        if external_ids:
            # Query in batches of 1000 if necessary
            for i in range(0, len(external_ids), 1000):
                batch_ids = external_ids[i:i + 1000]
                stmt = select(Job).where(
                    Job.source_id == source.id,
                    Job.external_id.in_(batch_ids),
                )
                for job in db.execute(stmt).scalars().all():
                    existing_jobs_map[job.external_id] = job

        new_jobs: list[Job] = []

        for item in normalized_jobs:
            new_hash = compute_content_hash(item)
            existing = existing_jobs_map.get(item.external_id)

            if existing is None:
                # 1. New Job
                new_job = Job(
                    source_id=source.id,
                    external_id=item.external_id,
                    content_hash=new_hash,
                    title=item.title,
                    company=item.company,
                    locations=item.locations,
                    remote_type=item.remote_type.value,
                    seniority=item.seniority.value,
                    employment_type=item.employment_type.value,
                    description=item.description,
                    apply_url=item.apply_url,
                    posted_at=item.posted_at,
                    status="open",
                    first_seen_at=crawl_start_time,
                    last_seen_at=crawl_start_time,
                )
                new_jobs.append(new_job)
                metrics.new_upserted += 1

            elif existing.content_hash == new_hash:
                # 2. Unchanged Job -> Just bump last_seen_at and reopen if closed
                existing.last_seen_at = crawl_start_time
                if existing.status == "closed":
                    existing.status = "open"
                    existing.closed_at = None
                metrics.unchanged += 1

            else:
                # 3. Changed Job -> Update attributes and content_hash
                existing.content_hash = new_hash
                existing.title = item.title
                existing.company = item.company
                existing.locations = item.locations
                existing.remote_type = item.remote_type.value
                existing.seniority = item.seniority.value
                existing.employment_type = item.employment_type.value
                existing.description = item.description
                existing.apply_url = item.apply_url
                existing.posted_at = item.posted_at
                existing.last_seen_at = crawl_start_time
                existing.status = "open"
                existing.closed_at = None
                metrics.updated += 1

        if new_jobs:
            db.bulk_save_objects(new_jobs)
        db.flush()

        # 4. Mark jobs closed when they disappear from the source feed
        # Any job for this source that was 'open' but not seen during this crawl run
        close_stmt = (
            update(Job)
            .where(
                Job.source_id == source.id,
                Job.status == "open",
                Job.last_seen_at < crawl_start_time,
            )
            .values(
                status="closed",
                closed_at=crawl_start_time,
            )
            .execution_options(synchronize_session=False)
        )
        result = db.execute(close_stmt)
        metrics.closed = result.rowcount or 0

        db.flush()
