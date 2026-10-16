from sqlalchemy import select
from src.modules.sources.models import Source
from src.modules.jobs.models import Job
from src.modules.deduplication.models import JobCluster
from src.modules.deduplication.fingerprint import (
    normalize_company_name,
    normalize_job_title,
    compute_dedup_fingerprint,
)
from src.modules.deduplication.service import DeduplicationService


def test_normalize_company_name():
    assert normalize_company_name("Stripe, Inc.") == "stripe"
    assert normalize_company_name("Cloudflare LLC") == "cloudflare"
    assert normalize_company_name("Datadog Technologies Corporation") == "datadog"
    assert normalize_company_name("Airbnb, Inc.") == "airbnb"


def test_normalize_job_title():
    assert normalize_job_title("Senior Backend Engineer (Remote - US)") == "senior backend engineer"
    assert normalize_job_title("Staff Software Engineer [Core Infrastructure]") == "staff software engineer"
    assert normalize_job_title("Data Scientist - Applied ML / Risk") == "data scientist"


def test_fingerprint_matches_cross_source_duplicates():
    # Source A (Greenhouse) posting
    _, _, fp1 = compute_dedup_fingerprint(
        company="Stripe, Inc.",
        title="Senior Backend Engineer - Core Infrastructure (Remote - US)",
        locations=["Remote - US"],
        remote_type="remote",
    )

    # Source B (Ashby or Job board) posting
    _, _, fp2 = compute_dedup_fingerprint(
        company="Stripe",
        title="Senior Backend Engineer - Core Infrastructure",
        locations=["San Francisco, CA; Remote"],
        remote_type="remote",
    )

    assert fp1 == fp2


def test_deduplication_clustering(db_session):
    src1 = Source(id="s1", name="Stripe GH", connector_type="greenhouse", config={})
    src2 = Source(id="s2", name="Stripe Ashby", connector_type="ashby", config={})
    db_session.add_all([src1, src2])
    db_session.commit()

    # Job from Source 1
    job1 = Job(
        id="j1",
        source_id="s1",
        external_id="gh-101",
        content_hash="h1",
        title="Senior Backend Engineer (Remote - US)",
        company="Stripe, Inc.",
        locations=["Remote"],
        remote_type="remote",
        seniority="senior",
        employment_type="full_time",
        description="Build payment infra",
        apply_url="https://boards.greenhouse.io/stripe/jobs/101",
    )
    db_session.add(job1)
    db_session.commit()

    cluster1 = DeduplicationService.deduplicate_job(db_session, job1)
    db_session.commit()

    assert cluster1.job_count == 1
    assert cluster1.primary_job_id == "j1"
    assert job1.cluster_id == cluster1.id
    assert job1.is_primary_in_cluster is True

    # Duplicate Job from Source 2
    job2 = Job(
        id="j2",
        source_id="s2",
        external_id="ashby-202",
        content_hash="h2",
        title="Senior Backend Engineer",
        company="Stripe",
        locations=["Remote - US"],
        remote_type="remote",
        seniority="senior",
        employment_type="full_time",
        description="Build scalable payment infra",
        apply_url="https://jobs.ashbyhq.com/stripe/202",
    )
    db_session.add(job2)
    db_session.commit()

    cluster2 = DeduplicationService.deduplicate_job(db_session, job2)
    db_session.commit()

    # Should join the existing cluster!
    assert cluster1.id == cluster2.id
    assert cluster2.job_count == 2
    assert cluster2.primary_job_id == "j1"
    assert job2.cluster_id == cluster1.id
    assert job2.is_primary_in_cluster is False
