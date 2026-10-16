from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from src.core.database import SessionLocal
from src.core.logging import logger
from src.core.metrics import CrawlMetrics
from src.modules.sources.models import Source
from src.modules.sources.repository import SourceRepository
from src.modules.discovery.base import BaseConnector
from src.modules.discovery.greenhouse import GreenhouseConnector
from src.modules.discovery.ashby import AshbyConnector
from src.modules.jobs.normalizer import GreenhouseNormalizer
from src.modules.jobs.ashby_normalizer import AshbyNormalizer
from src.modules.jobs.repository import JobRepository
from src.modules.jobs.schemas import NormalizedJob


def get_connector(connector_type: str) -> BaseConnector:
    ct = connector_type.lower()
    if ct == "greenhouse":
        return GreenhouseConnector()
    if ct == "ashby":
        return AshbyConnector()
    raise ValueError(f"Unsupported connector type: '{connector_type}'")


def normalize_raw_job(raw_item, source: Source) -> NormalizedJob:
    ct = source.connector_type.lower()
    if ct == "ashby":
        return AshbyNormalizer.normalize(raw_item, source)
    return GreenhouseNormalizer.normalize(raw_item, source)


def crawl_source(source_id: str, db: Optional[Session] = None) -> CrawlMetrics:
    """
    Executes an end-to-end crawl for a single source:
    1. Fetches raw jobs via registered connector.
    2. Stores verbatim raw payload for audit/replayability.
    3. Normalizes payload into canonical schema.
    4. Reconciles with canonical jobs (insert new, update changed, touch unchanged, close missing).
    5. Updates source schedule and records metrics.
    """
    should_close_session = False
    if db is None:
        db = SessionLocal()
        should_close_session = True

    source: Optional[Source] = SourceRepository.get_by_id(db, source_id)
    if not source:
        if should_close_session:
            db.close()
        raise ValueError(f"Source with id '{source_id}' not found")

    metrics = CrawlMetrics(
        source_id=source.id,
        source_name=source.name,
        connector=source.connector_type,
    )

    crawl_start_time = datetime.now(timezone.utc)

    logger.info(
        "Starting crawl for source",
        source_id=source.id,
        source_name=source.name,
        connector=source.connector_type,
    )

    try:
        connector = get_connector(source.connector_type)

        # 1. Fetch raw jobs from upstream ATS
        raw_jobs = connector.fetch(source)
        metrics.discovered = len(raw_jobs)

        # Atomic transaction savepoint for crawl writes
        with db.begin_nested():
            # 2. Store raw jobs for audit and future replay
            saved_raw_count = JobRepository.store_raw_jobs(db, source.id, raw_jobs)
            metrics.raw_saved = saved_raw_count

            # 3. Normalize jobs
            normalized_jobs: list[NormalizedJob] = []
            for raw_item in raw_jobs:
                try:
                    norm_job = normalize_raw_job(raw_item, source)
                    normalized_jobs.append(norm_job)
                except Exception as norm_err:
                    logger.warning(
                        "Job normalization failed for item",
                        source_id=source.id,
                        external_id=raw_item.external_id,
                        error=str(norm_err),
                    )

            # 4. Reconcile with canonical jobs table
            JobRepository.reconcile_jobs(
                db=db,
                source=source,
                normalized_jobs=normalized_jobs,
                crawl_start_time=crawl_start_time,
                metrics=metrics,
            )

        # 5. Record success and update next run schedule
        SourceRepository.record_success(db, source)
        metrics.finish(failed=False)

        logger.info("Crawl completed successfully", **metrics.to_dict())
        return metrics

    except Exception as e:
        error_msg = str(e)
        SourceRepository.record_failure(db, source, error_msg)
        metrics.finish(failed=True, error=error_msg)

        logger.error("Crawl execution failed", **metrics.to_dict())
        raise

    finally:
        if should_close_session:
            db.close()
