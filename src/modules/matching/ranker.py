import math
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
import numpy as np

from src.modules.jobs.models import Job
from src.modules.users.models import CandidateProfile


@dataclass
class MatchBreakdown:
    vector_score: float
    title_score: float
    recency_score: float
    final_score: float
    matched_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


class MultiFactorRanker:
    """
    Multi-factor ranking combining semantic vector similarity,
    title keyword overlap, and posting recency decay.
    """

    W_VECTOR = 0.60
    W_TITLE = 0.25
    W_RECENCY = 0.15

    @classmethod
    def check_hard_filters(cls, profile: CandidateProfile, job: Job) -> bool:
        """
        Enforces strict constraints:
        1. Seniority constraint (e.g. intern/entry-level candidates should not receive staff roles).
        2. Remote workplace preference (e.g. remote-only candidates).
        """
        # 1. Seniority Filter
        if profile.target_seniorities:
            allowed_seniorities = {s.lower() for s in profile.target_seniorities}
            job_sen = job.seniority.lower() if job.seniority else "unspecified"
            # If job seniority is known and candidate specified a strict list, enforce it
            if job_sen != "unspecified" and job_sen not in allowed_seniorities:
                return False

        # 2. Remote Type Filter
        if profile.preferred_remote_types:
            allowed_remote = {r.lower() for r in profile.preferred_remote_types}
            job_remote = job.remote_type.lower() if job.remote_type else "unknown"
            if job_remote != "unknown" and job_remote not in allowed_remote:
                return False

        return True

    @classmethod
    def compute_title_score(cls, target_roles: list[str], job_title: str) -> float:
        """Calculates token overlap between candidate target roles and job title."""
        if not target_roles:
            return 0.5  # Neutral default

        title_lower = job_title.lower()
        best_score = 0.0

        for role in target_roles:
            role_clean = role.lower().strip()
            # Exact phrase match in title
            if role_clean in title_lower:
                return 1.0

            # Token overlap (e.g. 'Backend' and 'Engineer')
            tokens = [t for t in re.split(r"\W+", role_clean) if len(t) > 2]
            if tokens:
                matches = sum(1 for t in tokens if t in title_lower)
                overlap = matches / len(tokens)
                if overlap > best_score:
                    best_score = overlap

        return best_score

    @classmethod
    def compute_recency_score(cls, first_seen_at: datetime) -> float:
        """Exponential decay based on age in days: e^(-0.1 * days)."""
        now = datetime.now(timezone.utc)
        if first_seen_at.tzinfo is None:
            first_seen_at = first_seen_at.replace(tzinfo=timezone.utc)
        age = (now - first_seen_at).total_seconds() / 86400.0  # age in days
        age = max(0.0, age)
        # 0 days -> 1.0, 7 days -> 0.50, 14 days -> 0.25
        return float(math.exp(-0.1 * age))

    @classmethod
    def compute_vector_similarity(cls, profile_vec: list[float], job_vec: list[float]) -> float:
        """Cosine similarity between two normalized vectors."""
        if not profile_vec or not job_vec:
            return 0.0
        pv = np.array(profile_vec, dtype=np.float32)
        jv = np.array(job_vec, dtype=np.float32)
        norm_p = np.linalg.norm(pv)
        norm_j = np.linalg.norm(jv)
        if norm_p == 0 or norm_j == 0:
            return 0.0
        return float(np.dot(pv, jv) / (norm_p * norm_j))

    @classmethod
    def score(cls, profile: CandidateProfile, job: Job) -> MatchBreakdown:
        # Check hard filters
        if not cls.check_hard_filters(profile, job):
            return MatchBreakdown(0.0, 0.0, 0.0, 0.0, [], ["Failed hard criteria filter"])

        # 1. Semantic Vector Score
        vec_score = cls.compute_vector_similarity(
            profile.profile_embedding, job.embedding
        )

        # 2. Title Keyword Score
        title_score = cls.compute_title_score(profile.target_roles or [], job.title)

        # 3. Recency Score
        recency_score = cls.compute_recency_score(job.first_seen_at)

        # Multi-factor weighted sum
        final_score = (
            (cls.W_VECTOR * vec_score)
            + (cls.W_TITLE * title_score)
            + (cls.W_RECENCY * recency_score)
        )

        # Extract matching skills for explainability
        matched_skills = []
        job_desc_lower = job.description.lower()
        for skill in (profile.parsed_skills or []):
            if skill.lower() in job_desc_lower or skill.lower() in job.title.lower():
                matched_skills.append(skill)

        reasons = []
        if vec_score >= 0.70:
            reasons.append("High semantic alignment with your resume experience")
        if title_score >= 0.80:
            reasons.append(f"Matches your target title '{job.title}'")
        if job.remote_type == "remote":
            reasons.append("100% Remote Opportunity")

        return MatchBreakdown(
            vector_score=round(vec_score, 4),
            title_score=round(title_score, 4),
            recency_score=round(recency_score, 4),
            final_score=round(final_score, 4),
            matched_skills=matched_skills[:8],
            reasons=reasons,
        )
