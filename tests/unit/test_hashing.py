from datetime import datetime, timezone
from src.modules.jobs.schemas import NormalizedJob, RemoteType, Seniority, EmploymentType
from src.modules.jobs.hashing import compute_content_hash


def test_hash_determinism():
    job1 = NormalizedJob(
        external_id="101",
        title="Backend Engineer",
        company="Stripe",
        locations=["San Francisco, CA", "Remote"],
        remote_type=RemoteType.REMOTE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Build scalable APIs.",
        apply_url="https://stripe.com/jobs/101",
        posted_at=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
    )

    job2 = NormalizedJob(
        external_id="101",
        title="Backend Engineer",
        company="Stripe",
        locations=["San Francisco, CA", "Remote"],
        remote_type=RemoteType.REMOTE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Build scalable APIs.",
        apply_url="https://stripe.com/jobs/101",
        posted_at=datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc),  # shifted timestamp
    )

    # Hash should be identical despite different posted_at timestamp
    assert compute_content_hash(job1) == compute_content_hash(job2)


def test_hash_location_order_invariance():
    job_a = NormalizedJob(
        external_id="101",
        title="Backend Engineer",
        company="Stripe",
        locations=["Seattle, WA", "San Francisco, CA"],
        remote_type=RemoteType.ONSITE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Build APIs",
        apply_url="https://stripe.com/jobs/101",
    )

    job_b = NormalizedJob(
        external_id="101",
        title="Backend Engineer",
        company="Stripe",
        locations=["San Francisco, CA", "Seattle, WA"],  # reordered locations
        remote_type=RemoteType.ONSITE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Build APIs",
        apply_url="https://stripe.com/jobs/101",
    )

    assert compute_content_hash(job_a) == compute_content_hash(job_b)


def test_hash_detects_changes():
    job = NormalizedJob(
        external_id="101",
        title="Backend Engineer",
        company="Stripe",
        locations=["Remote"],
        remote_type=RemoteType.REMOTE,
        seniority=Seniority.MID,
        employment_type=EmploymentType.FULL_TIME,
        description="Build APIs",
        apply_url="https://stripe.com/jobs/101",
    )

    job_modified_title = job.model_copy(update={"title": "Senior Backend Engineer"})
    job_modified_desc = job.model_copy(update={"description": "Build APIs using Rust"})

    original_hash = compute_content_hash(job)
    assert compute_content_hash(job_modified_title) != original_hash
    assert compute_content_hash(job_modified_desc) != original_hash
