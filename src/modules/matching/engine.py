from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.modules.users.models import User, CandidateProfile
from src.modules.jobs.models import Job
from src.modules.matching.models import JobFeedback
from src.modules.matching.ranker import MultiFactorRanker, MatchBreakdown


@dataclass
class MatchResult:
    job: Job
    breakdown: MatchBreakdown


class MatchingEngine:
    """Matches candidate profile vectors and criteria against active canonical jobs."""

    @classmethod
    def get_dismissed_job_ids(cls, db: Session, user_id: str) -> set[str]:
        """Returns set of job IDs that the user has explicitly dismissed."""
        stmt = select(JobFeedback.job_id).where(
            JobFeedback.user_id == user_id,
            JobFeedback.action == "dismissed",
        )
        return set(db.execute(stmt).scalars().all())

    @classmethod
    def match_candidate(
        cls,
        db: Session,
        user_id: str,
        limit: int = 10,
        min_score: Optional[float] = 0.70,
        only_recent_hours: Optional[int] = None,
        max_days: Optional[int] = 3,
    ) -> list[MatchResult]:
        """
        Retrieves, ranks, and filters top matching jobs for a candidate profile.
        Strictly enforces max_days (at max 3 days older) and min_score (70% match).
        """
        user = db.get(User, user_id)
        if not user or not user.profile:
            logger.warning("Matching requested for user without profile", user_id=user_id)
            return []

        profile: CandidateProfile = user.profile
        threshold = min_score if min_score is not None else (profile.min_similarity_score or 0.70)

        dismissed_ids = cls.get_dismissed_job_ids(db, user_id)

        # Base query for active, open jobs that have vector embeddings
        stmt = select(Job).where(
            Job.status == "open",
            Job.embedding.isnot(None),
        )

        now = datetime.now(timezone.utc)
        if only_recent_hours:
            cutoff = now - timedelta(hours=only_recent_hours)
            stmt = stmt.where(Job.first_seen_at >= cutoff)
        elif max_days:
            cutoff = now - timedelta(days=max_days)
            stmt = stmt.where(Job.first_seen_at >= cutoff)

        jobs = list(db.execute(stmt).scalars().all())

        results: list[MatchResult] = []
        seen_clusters: set[str] = set()

        for job in jobs:
            # Skip dismissed jobs
            if job.id in dismissed_ids:
                continue

            # Deduplicate by cluster: if a cluster has multiple jobs, only match once per candidate
            if job.cluster_id:
                if job.cluster_id in seen_clusters:
                    continue
                # Prefer the primary job in the cluster
                if not job.is_primary_in_cluster:
                    continue

            breakdown = MultiFactorRanker.score(profile, job)
            if breakdown.final_score >= threshold:
                if job.cluster_id:
                    seen_clusters.add(job.cluster_id)
                results.append(MatchResult(job=job, breakdown=breakdown))

        # Sort descending by final multi-factor score
        results.sort(key=lambda r: r.breakdown.final_score, reverse=True)
        top_results = results[:limit]

        # Enrich top matches with Gemini AI insights if available
        try:
            from src.modules.llm.gemini import GeminiService
            if GeminiService.is_available() and top_results:
                target_role = (profile.target_roles or ["Software Engineer"])[0]
                for r in top_results[:3]:
                    ai_pitch = GeminiService.generate_match_pitch(
                        job_title=r.job.title,
                        company=r.job.company,
                        job_description=r.job.description or "",
                        candidate_skills=r.breakdown.matched_skills,
                        candidate_role=target_role,
                    )
                    if ai_pitch:
                        r.breakdown.reasons.insert(0, f"🤖 AI Insight: {ai_pitch}")
        except Exception:
            pass

        return top_results

    @classmethod
    def record_feedback(
        cls,
        db: Session,
        user_id: str,
        job_id: str,
        action: str,
    ) -> JobFeedback:
        """Records candidate reaction (viewed, applied, dismissed, saved)."""
        job = db.get(Job, job_id)
        cluster_id = job.cluster_id if job else None

        stmt = select(JobFeedback).where(
            JobFeedback.user_id == user_id,
            JobFeedback.job_id == job_id,
            JobFeedback.action == action,
        )
        existing = db.execute(stmt).scalars().first()
        if existing:
            return existing

        feedback = JobFeedback(
            user_id=user_id,
            job_id=job_id,
            cluster_id=cluster_id,
            action=action,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        logger.info("Recorded candidate job feedback", user_id=user_id, job_id=job_id, action=action)
        return feedback
