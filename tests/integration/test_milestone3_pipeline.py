from sqlalchemy import select
from src.modules.sources.models import Source
from src.modules.jobs.models import Job
from src.modules.users.models import User
from src.modules.users.repository import UserRepository
from src.modules.users.schemas import ProfileCreateOrUpdate
from src.modules.matching.engine import MatchingEngine
from src.modules.notifications.models import NotificationOutbox
from src.modules.notifications.outbox import OutboxService
from tests.unit.test_embeddings import MockEmbeddingProvider


def test_milestone3_end_to_end_matching_and_outbox(db_session):
    mock_provider = MockEmbeddingProvider()

    # 1. Register Candidate Alex
    alex = UserRepository.create_user(
        db=db_session,
        email="alex@example.com",
        telegram_chat_id="telegram_alex_999",
        full_name="Alex Backend",
        alert_frequency="daily_9am",
    )

    # 2. Upload Profile & Resume
    alex_profile = ProfileCreateOrUpdate(
        target_roles=["Backend Engineer", "Platform Engineer"],
        target_seniorities=["senior"],
        preferred_remote_types=["remote"],
        preferred_locations=["Remote - US"],
        raw_resume_text="Senior engineer with 6 years building distributed backend APIs in Python, PostgreSQL, Redis, and Docker.",
        min_similarity_score=0.40,
    )
    UserRepository.update_profile(db_session, alex.id, alex_profile, embedding_provider=mock_provider)

    db_session.refresh(alex)
    assert "Python" in alex.profile.parsed_skills
    assert "Redis" in alex.profile.parsed_skills
    assert alex.profile.profile_embedding is not None

    # 3. Create Source and Jobs
    source = Source(id="src-stripe", name="Stripe", connector_type="greenhouse", config={})
    db_session.add(source)
    db_session.commit()

    # Job A: Matches Alex's criteria (Senior, Remote, Backend)
    job_match = Job(
        id="job-a",
        source_id=source.id,
        external_id="stripe-101",
        content_hash="hash_a",
        title="Senior Backend Engineer - Core Payments",
        company="Stripe",
        locations=["Remote - US"],
        remote_type="remote",
        seniority="senior",
        employment_type="full_time",
        description="Build high-reliability payment infrastructure using Python and Redis.",
        apply_url="https://stripe.com/jobs/101",
        embedding=alex.profile.profile_embedding,  # Identical vector for perfect 1.0 similarity
        status="open",
    )

    # Job B: Mismatch on Seniority and Remote (Intern, Onsite)
    job_mismatch = Job(
        id="job-b",
        source_id=source.id,
        external_id="stripe-102",
        content_hash="hash_b",
        title="Software Engineering Intern",
        company="Stripe",
        locations=["Seattle, WA"],
        remote_type="onsite",
        seniority="intern",
        employment_type="internship",
        description="Learn backend development.",
        apply_url="https://stripe.com/jobs/102",
        embedding=alex.profile.profile_embedding,
        status="open",
    )

    db_session.add_all([job_match, job_mismatch])
    db_session.commit()

    # -------------------------------------------------------------
    # Stage 1: Reverse Matching
    # -------------------------------------------------------------
    matches = MatchingEngine.match_candidate(db_session, alex.id, limit=5)
    assert len(matches) == 1
    top_match = matches[0]

    assert top_match.job.id == "job-a"
    assert top_match.breakdown.final_score > 0.80
    assert "Python" in top_match.breakdown.matched_skills or "Redis" in top_match.breakdown.matched_skills

    # -------------------------------------------------------------
    # Stage 2: Scheduled 9:00 AM Daily Digest & Outbox Queue
    # -------------------------------------------------------------
    digest_summary = OutboxService.run_daily_digest(db_session, since_hours=24)
    assert digest_summary["users_evaluated"] == 1
    assert digest_summary["alerts_queued"] == 1

    # Check pending outbox item in DB
    outbox_records = db_session.execute(select(NotificationOutbox)).scalars().all()
    assert len(outbox_records) == 1
    outbox_item = outbox_records[0]

    assert outbox_item.user_id == alex.id
    assert outbox_item.channel == "telegram"
    assert outbox_item.recipient == "telegram_alex_999"
    assert outbox_item.status == "pending"
    assert len(outbox_item.payload["matches"]) == 1

    # -------------------------------------------------------------
    # Stage 3: Outbox Drain & Delivery
    # -------------------------------------------------------------
    from unittest.mock import patch
    with patch("src.modules.notifications.outbox._telegram.send", return_value=True):
        drain_summary = OutboxService.drain_outbox(db_session)
        assert drain_summary["sent"] == 1

    db_session.refresh(outbox_item)
    assert outbox_item.status == "sent"
    assert outbox_item.sent_at is not None

    # -------------------------------------------------------------
    # Stage 4: User Feedback Loop (Dismiss Job)
    # -------------------------------------------------------------
    MatchingEngine.record_feedback(db_session, alex.id, job_match.id, action="dismissed")

    # Re-running match ensures dismissed job is never recommended again
    matches_after_dismiss = MatchingEngine.match_candidate(db_session, alex.id, limit=5)
    assert len(matches_after_dismiss) == 0
