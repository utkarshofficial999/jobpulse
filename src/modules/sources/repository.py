from datetime import datetime, timezone, timedelta
import random
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.sources.models import Source


class SourceRepository:
    """Handles source scheduling, concurrency leasing, and failure backoff."""

    @staticmethod
    def get_by_id(db: Session, source_id: str) -> Optional[Source]:
        return db.get(Source, source_id)

    @staticmethod
    def create(
        db: Session,
        name: str,
        connector_type: str,
        config: dict,
        poll_interval_seconds: int = 3600,
    ) -> Source:
        source = Source(
            name=name,
            connector_type=connector_type,
            config=config,
            poll_interval_seconds=poll_interval_seconds,
            next_run_at=datetime.now(timezone.utc),
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    @staticmethod
    def get_due_sources(db: Session, limit: int = 50) -> list[Source]:
        """
        Retrieves active sources where next_run_at <= NOW().
        Temporarily leases the source by setting next_run_at 10 minutes ahead
        to prevent race conditions among multiple scheduler ticks.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(Source)
            .where(
                Source.is_active == True,
                Source.next_run_at <= now,
            )
            .order_by(Source.next_run_at.asc())
            .limit(limit)
        )
        # In Postgres, with_for_update(skip_locked=True) can be chained
        if db.bind and db.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        sources = list(db.execute(stmt).scalars().all())

        # Optimistically lease
        lease_until = now + timedelta(minutes=10)
        for s in sources:
            s.next_run_at = lease_until
        db.commit()

        return sources

    @staticmethod
    def record_success(db: Session, source: Source) -> None:
        """Resets failures and schedules next run based on poll interval."""
        now = datetime.now(timezone.utc)
        source.consecutive_failures = 0
        source.last_error = None
        source.last_run_at = now
        source.next_run_at = now + timedelta(seconds=source.poll_interval_seconds)
        db.commit()

    @staticmethod
    def record_failure(db: Session, source: Source, error_msg: str) -> None:
        """Increments failures and computes exponential backoff with jitter."""
        now = datetime.now(timezone.utc)
        source.consecutive_failures += 1
        source.last_error = error_msg[:1000]  # truncate if very long
        source.last_run_at = now

        # Exponential backoff: min(interval * 2^failures, 24 hours) + random jitter
        multiplier = 2 ** min(source.consecutive_failures, 8)
        base_backoff = min(source.poll_interval_seconds * multiplier, 86400)
        jitter = random.uniform(5.0, 30.0)
        backoff_seconds = int(base_backoff + jitter)

        source.next_run_at = now + timedelta(seconds=backoff_seconds)
        db.commit()
