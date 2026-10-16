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
    skill_score: float
    final_score: float
    matched_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


class MultiFactorRanker:
    """
    Multi-factor ranking combining semantic vector similarity (candidate experience),
    explicit user skills overlap, title alignment, and 3-day recency.
    """

    W_VECTOR = 0.35
    W_SKILLS = 0.35
    W_TITLE = 0.20
    W_RECENCY = 0.10

    @classmethod
    def check_hard_filters(cls, profile: CandidateProfile, job: Job) -> bool:
        """
        Enforces strict constraints:
        1. Seniority constraint (e.g. intern/entry-level candidates should not receive staff roles).
        2. Remote workplace preference (e.g. remote-only candidates).
        3. Recency constraint: at max 3 days older.
        """
        # 1. Recency hard cutoff: at max 3 days older
        if job.first_seen_at:
            now = datetime.now(timezone.utc)
            first_seen = job.first_seen_at.replace(tzinfo=timezone.utc) if job.first_seen_at.tzinfo is None else job.first_seen_at
            age_days = (now - first_seen).total_seconds() / 86400.0
            if age_days > 3.0:
                return False

        # 2. Seniority Filter
        if profile.target_seniorities:
            allowed_seniorities = {s.lower() for s in profile.target_seniorities}
            job_sen = job.seniority.lower() if job.seniority else "unspecified"
            # If job seniority is known and candidate specified a strict list, enforce it
            if job_sen != "unspecified" and job_sen not in allowed_seniorities:
                return False

        # 3. Remote Type Filter
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
        """Recency score for jobs up to 3 days old."""
        now = datetime.now(timezone.utc)
        if first_seen_at.tzinfo is None:
            first_seen_at = first_seen_at.replace(tzinfo=timezone.utc)
        age = (now - first_seen_at).total_seconds() / 86400.0  # age in days
        age = max(0.0, age)
        if age > 3.0:
            return 0.0
        return float(max(0.5, 1.0 - (0.07 * age)))

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
    def calibrate_vector_score(cls, raw_cos: float) -> float:
        """Calibrates dense cosine similarity (typically 0.30 - 0.70) into 0.0 - 1.0 range."""
        return float(min(1.0, max(0.0, (raw_cos - 0.25) / 0.30)))

    @classmethod
    def compute_skill_score(cls, user_skills: list[str], job_description: str, job_title: str) -> tuple[float, list[str]]:
        """Calculates explicit skill overlap between candidate's selected skills and job."""
        if not user_skills:
            return 0.5, []

        job_text = f"{job_title} {job_description}".lower()
        matched: list[str] = []
        for skill in user_skills:
            pattern = rf"\b{re.escape(skill.lower())}\b"
            if re.search(pattern, job_text):
                matched.append(skill)

        if not matched:
            return 0.1, []

        target_count = max(1, min(len(user_skills), 3))
        ratio = len(matched) / target_count
        score = min(1.0, ratio)
        return float(score), matched

    @classmethod
    def score(cls, profile: CandidateProfile, job: Job) -> MatchBreakdown:
        # Check hard filters
        if not cls.check_hard_filters(profile, job):
            return MatchBreakdown(0.0, 0.0, 0.0, 0.0, 0.0, [], ["Failed hard criteria filter or older than 3 days"])

        # 1. Semantic Vector Score (Experience Background)
        raw_vec = cls.compute_vector_similarity(
            profile.profile_embedding, job.embedding
        )
        vec_score = cls.calibrate_vector_score(raw_vec)

        # 2. User-Selected Skills Match Score
        user_skills = profile.parsed_skills or []
        skill_score, matched_skills = cls.compute_skill_score(
            user_skills, job.description or "", job.title
        )

        # 3. Title Keyword Score
        title_score = cls.compute_title_score(profile.target_roles or [], job.title)

        # 4. Recency Score (<= 3 days)
        recency_score = cls.compute_recency_score(job.first_seen_at)

        # Multi-factor weighted sum (vector experience + skills + title + recency)
        final_score = (
            (cls.W_VECTOR * vec_score)
            + (cls.W_SKILLS * skill_score)
            + (cls.W_TITLE * title_score)
            + (cls.W_RECENCY * recency_score)
        )

        reasons = []
        if final_score >= 0.70:
            reasons.append(f"⚡ Strong match ({int(final_score * 100)}%) matching your skills & experience")
        if matched_skills:
            reasons.append(f"Matched Skills: {', '.join(matched_skills[:4])}")
        if title_score >= 0.75:
            reasons.append(f"Target role match for '{job.title}'")
        if job.remote_type == "remote":
            reasons.append("100% Remote Opportunity")

        return MatchBreakdown(
            vector_score=round(raw_vec, 4),
            title_score=round(title_score, 4),
            recency_score=round(recency_score, 4),
            skill_score=round(skill_score, 4),
            final_score=round(final_score, 4),
            matched_skills=matched_skills[:8],
            reasons=reasons,
        )
