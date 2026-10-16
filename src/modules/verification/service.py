from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.modules.jobs.models import Job
from src.modules.verification.checker import JobLinkChecker, VerificationResult


class VerificationService:
    """Orchestrates job posting availability checks and status updates."""

    @staticmethod
    def verify_job(db: Session, job: Job, checker: Optional[JobLinkChecker] = None) -> VerificationResult:
        checker = checker or JobLinkChecker()
        result = checker.check(job.apply_url)

        now = datetime.now(timezone.utc)
        job.verification_status = result.status
        job.verified_at = now
        job.verification_error = result.error

        if result.status == "verified_closed":
            job.status = "closed"
            job.closed_at = now
            logger.info(
                "Job verified as closed",
                job_id=job.id,
                title=job.title,
                company=job.company,
                reason=result.error,
            )

        db.flush()
        return result

    @classmethod
    def batch_verify(cls, db: Session, limit: int = 50, recheck_days: int = 3) -> dict:
        """
        Verifies jobs that are either unverified or haven't been verified in `recheck_days`.
        """
        stale_threshold = datetime.now(timezone.utc) - timedelta(days=recheck_days)

        stmt = (
            select(Job)
            .where(
                Job.status == "open",
                or_(
                    Job.verification_status == "unverified",
                    Job.verified_at < stale_threshold,
                ),
            )
            .limit(limit)
        )
        jobs_to_verify = list(db.execute(stmt).scalars().all())

        if not jobs_to_verify:
            return {"verified": 0, "active": 0, "closed": 0, "unknown": 0}

        checker = JobLinkChecker()
        summary = {"verified": len(jobs_to_verify), "active": 0, "closed": 0, "unknown": 0}

        for job in jobs_to_verify:
            res = cls.verify_job(db, job, checker)
            if res.status == "verified_active":
                summary["active"] += 1
            elif res.status == "verified_closed":
                summary["closed"] += 1
            else:
                summary["unknown"] += 1

        db.commit()
        logger.info("Batch verification completed", **summary)
        return summary
