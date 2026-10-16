import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import select
import httpx

from src.modules.sources.models import Source
from src.modules.sources.repository import SourceRepository
from src.modules.jobs.models import RawJob, Job
from src.modules.discovery.service import crawl_source


def load_fixture(name: str) -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / name
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_crawl_flow_with_recorded_fixture(db_session):
    fixture_data = load_fixture("greenhouse_stripe.json")

    # 1. Create Source in database
    source = SourceRepository.create(
        db=db_session,
        name="Stripe",
        connector_type="greenhouse",
        config={"board_token": "stripe", "company_name": "Stripe"},
        poll_interval_seconds=3600,
    )

    # 2. Mock httpx.Client response to serve the recorded fixture
    mock_response = httpx.Response(
        status_code=200,
        json=fixture_data,
        request=httpx.Request("GET", "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true"),
    )

    with patch("httpx.Client.get", return_value=mock_response):
        metrics = crawl_source(source_id=source.id, db=db_session)

    # 3. Verify metrics
    assert metrics.discovered == 3
    assert metrics.raw_saved == 3
    assert metrics.new_upserted == 3
    assert metrics.failed is False

    # 4. Verify raw_jobs table
    raw_records = db_session.execute(
        select(RawJob).where(RawJob.source_id == source.id)
    ).scalars().all()
    assert len(raw_records) == 3
    raw_ext_ids = {r.external_id for r in raw_records}
    assert raw_ext_ids == {"500101", "500102", "500103"}

    # 5. Verify canonical jobs table
    canonical_jobs = db_session.execute(
        select(Job).where(Job.source_id == source.id)
    ).scalars().all()
    assert len(canonical_jobs) == 3

    jobs_by_id = {j.external_id: j for j in canonical_jobs}

    # Verify Job 1 (Senior Backend Engineer - Remote)
    job1 = jobs_by_id["500101"]
    assert job1.title == "Senior Backend Engineer - Core Infrastructure"
    assert job1.company == "Stripe"
    assert job1.seniority == "senior"
    assert job1.remote_type == "remote"
    assert job1.status == "open"
    assert "Design distributed systems" in job1.description

    # Verify Job 2 (Intern)
    job2 = jobs_by_id["500102"]
    assert job2.title == "Software Engineering Intern (Summer 2027)"
    assert job2.seniority == "intern"
    assert job2.employment_type == "internship"
    assert job2.remote_type == "onsite"

    # Verify Job 3 (Staff - Hybrid)
    job3 = jobs_by_id["500103"]
    assert job3.title == "Staff AI Research Engineer - Hybrid"
    assert job3.seniority == "staff"
    assert job3.remote_type == "hybrid"

    # 6. Verify Source scheduling state was updated
    db_session.refresh(source)
    assert source.consecutive_failures == 0
    assert source.last_error is None
    assert source.last_run_at is not None
    assert source.next_run_at > source.last_run_at


def test_crawl_failure_and_backoff(db_session):
    source = SourceRepository.create(
        db=db_session,
        name="Broken Company",
        connector_type="greenhouse",
        config={"board_token": "broken_board"},
        poll_interval_seconds=3600,
    )

    mock_error_response = httpx.Response(
        status_code=500,
        request=httpx.Request("GET", "https://boards-api.greenhouse.io/v1/boards/broken_board/jobs?content=true"),
    )

    with patch("httpx.Client.get", return_value=mock_error_response), patch("time.sleep"):
        try:
            crawl_source(source_id=source.id, db=db_session)
        except Exception:
            pass

    # Source should register failure and backoff
    failed_source = SourceRepository.get_by_id(db_session, source.id)
    assert failed_source.consecutive_failures == 1
    assert failed_source.last_error is not None
    assert "500" in failed_source.last_error
    assert failed_source.next_run_at > failed_source.last_run_at
