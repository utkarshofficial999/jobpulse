from datetime import datetime, timezone, timedelta
from src.modules.users.models import CandidateProfile
from src.modules.jobs.models import Job
from src.modules.matching.ranker import MultiFactorRanker


def test_hard_filter_seniority_rejection():
    # Intern candidate
    profile = CandidateProfile(
        target_seniorities=["intern", "entry"],
        preferred_remote_types=["remote", "hybrid", "onsite"],
    )

    job_staff = Job(seniority="staff", remote_type="remote")
    job_intern = Job(seniority="intern", remote_type="remote")
    job_entry = Job(seniority="entry", remote_type="remote")

    # Staff role should be strictly rejected
    assert MultiFactorRanker.check_hard_filters(profile, job_staff) is False
    assert MultiFactorRanker.check_hard_filters(profile, job_intern) is True
    assert MultiFactorRanker.check_hard_filters(profile, job_entry) is True


def test_hard_filter_remote_rejection():
    # Candidate strictly wants remote
    profile = CandidateProfile(
        target_seniorities=["mid", "senior"],
        preferred_remote_types=["remote"],
    )

    job_onsite = Job(seniority="senior", remote_type="onsite")
    job_remote = Job(seniority="senior", remote_type="remote")

    assert MultiFactorRanker.check_hard_filters(profile, job_onsite) is False
    assert MultiFactorRanker.check_hard_filters(profile, job_remote) is True


def test_title_score_exact_and_token_overlap():
    target_roles = ["Backend Engineer", "Platform Engineer"]

    assert MultiFactorRanker.compute_title_score(target_roles, "Senior Backend Engineer") == 1.0
    assert MultiFactorRanker.compute_title_score(target_roles, "Platform Engineer, Core Infra") == 1.0
    # Partial token overlap
    partial_score = MultiFactorRanker.compute_title_score(target_roles, "Senior Software Engineer")
    assert 0.0 < partial_score < 1.0
    # No match
    assert MultiFactorRanker.compute_title_score(target_roles, "Account Executive") == 0.0


def test_recency_score_decay():
    now = datetime.now(timezone.utc)
    fresh_time = now - timedelta(hours=2)
    old_time = now - timedelta(days=20)

    score_fresh = MultiFactorRanker.compute_recency_score(fresh_time)
    score_old = MultiFactorRanker.compute_recency_score(old_time)

    assert score_fresh > 0.95
    assert score_old < 0.20
