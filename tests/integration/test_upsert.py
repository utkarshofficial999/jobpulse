from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from src.core.metrics import CrawlMetrics
from src.modules.sources.models import Source
from src.modules.jobs.models import Job
from src.modules.jobs.schemas import NormalizedJob, RemoteType, Seniority, EmploymentType
from src.modules.jobs.repository import JobRepository


def test_upsert_lifecycle(db_session):
    # Setup source
    source = Source(
        id="src-test-1",
        name="Test Company",
        connector_type="greenhouse",
        config={"board_token": "testco"},
    )
    db_session.add(source)
    db_session.commit()

    time_1 = datetime(2026, 10, 16, 9, 0, 0, tzinfo=timezone.utc)

    job_a = NormalizedJob(
        external_id="ext-1",
        title="Software Engineer",
        company="Test Company",
        locations=["Remote"],
        remote_type=RemoteType.REMOTE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Write code.",
        apply_url="https://test.com/apply/1",
    )
    job_b = NormalizedJob(
        external_id="ext-2",
        title="Product Manager",
        company="Test Company",
        locations=["San Francisco, CA"],
        remote_type=RemoteType.ONSITE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Manage roadmaps.",
        apply_url="https://test.com/apply/2",
    )

    # --- Run 1: First crawl with jobs A and B ---
    metrics_1 = CrawlMetrics(source_id=source.id, source_name=source.name, connector="greenhouse")
    JobRepository.reconcile_jobs(
        db=db_session,
        source=source,
        normalized_jobs=[job_a, job_b],
        crawl_start_time=time_1,
        metrics=metrics_1,
    )
    db_session.commit()

    assert metrics_1.new_upserted == 2
    assert metrics_1.unchanged == 0
    assert metrics_1.updated == 0
    assert metrics_1.closed == 0

    all_jobs = db_session.execute(select(Job)).scalars().all()
    assert len(all_jobs) == 2
    for j in all_jobs:
        assert j.status == "open"
        assert j.first_seen_at.replace(tzinfo=None) == time_1.replace(tzinfo=None)
        assert j.last_seen_at.replace(tzinfo=None) == time_1.replace(tzinfo=None)
        assert j.closed_at is None

    # --- Run 2: Second crawl 1 hour later ---
    # Job A is unchanged
    # Job B had description updated
    # Job C is a new job
    time_2 = time_1 + timedelta(hours=1)
    job_b_updated = job_b.model_copy(update={"description": "Manage AI and data product roadmaps."})
    job_c = NormalizedJob(
        external_id="ext-3",
        title="DevOps Engineer",
        company="Test Company",
        locations=["Austin, TX"],
        remote_type=RemoteType.ONSITE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Kubernetes infra.",
        apply_url="https://test.com/apply/3",
    )

    metrics_2 = CrawlMetrics(source_id=source.id, source_name=source.name, connector="greenhouse")
    JobRepository.reconcile_jobs(
        db=db_session,
        source=source,
        normalized_jobs=[job_a, job_b_updated, job_c],
        crawl_start_time=time_2,
        metrics=metrics_2,
    )
    db_session.commit()

    assert metrics_2.unchanged == 1  # Job A
    assert metrics_2.updated == 1    # Job B
    assert metrics_2.new_upserted == 1 # Job C
    assert metrics_2.closed == 0

    # Verify Job A: first_seen_at preserved, last_seen_at bumped
    db_job_a = db_session.execute(select(Job).where(Job.external_id == "ext-1")).scalar_one()
    assert db_job_a.first_seen_at.replace(tzinfo=None) == time_1.replace(tzinfo=None)
    assert db_job_a.last_seen_at.replace(tzinfo=None) == time_2.replace(tzinfo=None)

    # Verify Job B: updated description & last_seen_at bumped
    db_job_b = db_session.execute(select(Job).where(Job.external_id == "ext-2")).scalar_one()
    assert "AI and data product" in db_job_b.description
    assert db_job_b.last_seen_at.replace(tzinfo=None) == time_2.replace(tzinfo=None)

    # --- Run 3: Disappearance Detection ---
    # Feed now only contains Job A. (Jobs B and C disappeared from the feed)
    time_3 = time_2 + timedelta(hours=1)
    metrics_3 = CrawlMetrics(source_id=source.id, source_name=source.name, connector="greenhouse")
    JobRepository.reconcile_jobs(
        db=db_session,
        source=source,
        normalized_jobs=[job_a],
        crawl_start_time=time_3,
        metrics=metrics_3,
    )
    db_session.commit()

    assert metrics_3.unchanged == 1  # Job A
    assert metrics_3.closed == 2     # Jobs B and C marked closed

    db_job_b = db_session.execute(select(Job).where(Job.external_id == "ext-2")).scalar_one()
    db_job_c = db_session.execute(select(Job).where(Job.external_id == "ext-3")).scalar_one()
    assert db_job_b.status == "closed"
    assert db_job_b.closed_at.replace(tzinfo=None) == time_3.replace(tzinfo=None)
    assert db_job_c.status == "closed"
    assert db_job_c.closed_at.replace(tzinfo=None) == time_3.replace(tzinfo=None)

    # --- Run 4: Reopen closed job if it reappears ---
    time_4 = time_3 + timedelta(hours=1)
    metrics_4 = CrawlMetrics(source_id=source.id, source_name=source.name, connector="greenhouse")
    JobRepository.reconcile_jobs(
        db=db_session,
        source=source,
        normalized_jobs=[job_a, job_b_updated],
        crawl_start_time=time_4,
        metrics=metrics_4,
    )
    db_session.commit()

    db_job_b = db_session.execute(select(Job).where(Job.external_id == "ext-2")).scalar_one()
    assert db_job_b.status == "open"
    assert db_job_b.closed_at is None
    assert db_job_b.last_seen_at.replace(tzinfo=None) == time_4.replace(tzinfo=None)
