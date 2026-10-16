from unittest.mock import patch
from sqlalchemy import select
import httpx

from src.modules.sources.models import Source
from src.modules.sources.repository import SourceRepository
from src.modules.jobs.models import Job
from src.modules.deduplication.models import JobCluster
from src.modules.deduplication.service import DeduplicationService
from src.modules.embeddings.service import EmbeddingService
from src.modules.verification.service import VerificationService
from src.modules.verification.checker import JobLinkChecker
from tests.unit.test_embeddings import MockEmbeddingProvider


def test_milestone2_end_to_end_pipeline(db_session):
    # 1. Create two distinct ATS sources
    source_gh = SourceRepository.create(
        db=db_session,
        name="Stripe Greenhouse",
        connector_type="greenhouse",
        config={"board_token": "stripe"},
    )
    source_ashby = SourceRepository.create(
        db=db_session,
        name="Stripe Ashby",
        connector_type="ashby",
        config={"board_token": "stripe_ashby"},
    )

    # 2. Add Job 1 (from Greenhouse)
    job_gh = Job(
        source_id=source_gh.id,
        external_id="gh-101",
        content_hash="hash_gh",
        title="Senior Distributed Systems Engineer (Remote - US)",
        company="Stripe, Inc.",
        locations=["Remote - US"],
        remote_type="remote",
        seniority="senior",
        employment_type="full_time",
        description="Design and operate core distributed payment ledgers and Redis clusters.",
        apply_url="https://boards.greenhouse.io/stripe/jobs/101",
        status="open",
    )

    # Add Job 2 (from Ashby - duplicate of Job 1)
    job_ashby = Job(
        source_id=source_ashby.id,
        external_id="ashby-201",
        content_hash="hash_ashby",
        title="Senior Distributed Systems Engineer",
        company="Stripe",
        locations=["San Francisco, CA; Remote"],
        remote_type="remote",
        seniority="senior",
        employment_type="full_time",
        description="Design and operate core distributed payment ledgers.",
        apply_url="https://jobs.ashbyhq.com/stripe/201",
        status="open",
    )

    # Add Job 3 (from Ashby - unique role)
    job_unique = Job(
        source_id=source_ashby.id,
        external_id="ashby-301",
        content_hash="hash_pm",
        title="Lead Product Designer - Payments",
        company="Stripe",
        locations=["Seattle, WA"],
        remote_type="onsite",
        seniority="lead",
        employment_type="full_time",
        description="Design user experience for developer dashboard.",
        apply_url="https://jobs.ashbyhq.com/stripe/301",
        status="open",
    )

    db_session.add_all([job_gh, job_ashby, job_unique])
    db_session.commit()

    # -------------------------------------------------------------
    # Stage 1: Cross-Source Deduplication & Clustering
    # -------------------------------------------------------------
    clustered_count = DeduplicationService.batch_deduplicate(db_session, limit=10)
    assert clustered_count == 3

    # Check clusters in DB
    clusters = db_session.execute(select(JobCluster)).scalars().all()
    assert len(clusters) == 2  # One for the 2 backend jobs, one for the design job

    # Verify duplicate clustering
    db_session.refresh(job_gh)
    db_session.refresh(job_ashby)
    db_session.refresh(job_unique)

    assert job_gh.cluster_id is not None
    assert job_gh.cluster_id == job_ashby.cluster_id
    assert job_unique.cluster_id != job_gh.cluster_id

    # Primary vs secondary
    assert job_gh.is_primary_in_cluster is True
    assert job_ashby.is_primary_in_cluster is False

    cluster_backend = db_session.get(JobCluster, job_gh.cluster_id)
    assert cluster_backend.job_count == 2
    assert cluster_backend.primary_job_id == job_gh.id

    # -------------------------------------------------------------
    # Stage 2: Semantic Vector Embedding Generation & Search
    # -------------------------------------------------------------
    mock_provider = MockEmbeddingProvider()
    embedded_count = EmbeddingService.generate_batch(db_session, batch_size=10, provider=mock_provider)
    assert embedded_count == 3

    db_session.refresh(job_gh)
    assert job_gh.embedding is not None
    assert len(job_gh.embedding) == 384
    assert job_gh.embedded_at is not None

    # Test Semantic Vector Search
    search_results = EmbeddingService.search_similar_jobs(
        db=db_session,
        query="distributed systems ledger backend",
        limit=5,
        provider=mock_provider,
    )
    assert len(search_results) == 3
    # Top results should have similarity scores
    top_job, score = search_results[0]
    assert score > 0.0

    # -------------------------------------------------------------
    # Stage 3: Verification (Still Open Check)
    # -------------------------------------------------------------
    # Test 3a: Verify job_unique is active (HTTP 200)
    active_response = httpx.Response(
        status_code=200,
        text="<html><body><h1>Lead Product Designer</h1><button>Apply</button></body></html>",
        request=httpx.Request("GET", job_unique.apply_url),
    )
    with patch("httpx.Client.get", return_value=active_response):
        res_active = VerificationService.verify_job(db_session, job_unique)

    assert res_active.status == "verified_active"
    assert job_unique.status == "open"
    assert job_unique.verified_at is not None

    # Test 3b: Verify job_ashby has closed (HTTP 404)
    closed_response = httpx.Response(
        status_code=404,
        request=httpx.Request("GET", job_ashby.apply_url),
    )
    with patch("httpx.Client.get", return_value=closed_response):
        res_closed = VerificationService.verify_job(db_session, job_ashby)

    assert res_closed.status == "verified_closed"
    assert job_ashby.status == "closed"
    assert job_ashby.closed_at is not None
