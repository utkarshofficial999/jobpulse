from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.modules.jobs.models import Job
from src.modules.deduplication.models import JobCluster
from src.modules.deduplication.fingerprint import compute_dedup_fingerprint


class DeduplicationService:
    """Service to cluster duplicate jobs across different sources."""

    @staticmethod
    def deduplicate_job(db: Session, job: Job) -> JobCluster:
        """
        Assigns the job to an existing JobCluster if matched by fingerprint,
        or creates a new JobCluster making this job the primary.
        """
        norm_company, norm_title, fingerprint = compute_dedup_fingerprint(
            company=job.company,
            title=job.title,
            locations=job.locations or [],
            remote_type=job.remote_type,
        )

        # Lookup cluster by fingerprint
        stmt = select(JobCluster).where(JobCluster.dedup_fingerprint == fingerprint)
        cluster: Optional[JobCluster] = db.execute(stmt).scalars().first()

        if cluster is None:
            # Create new cluster with this job as the primary
            cluster = JobCluster(
                company_normalized=norm_company,
                title_normalized=norm_title,
                dedup_fingerprint=fingerprint,
                primary_job_id=job.id,
                job_count=1,
            )
            db.add(cluster)
            db.flush()

            job.cluster_id = cluster.id
            job.is_primary_in_cluster = True
            logger.debug(
                "Created new job cluster",
                cluster_id=cluster.id,
                company=norm_company,
                title=norm_title,
                job_id=job.id,
            )
        else:
            # Add to existing cluster
            if job.cluster_id != cluster.id:
                job.cluster_id = cluster.id
                job.is_primary_in_cluster = False
                cluster.job_count += 1
                logger.info(
                    "Deduplicated job into existing cluster",
                    cluster_id=cluster.id,
                    job_id=job.id,
                    total_in_cluster=cluster.job_count,
                    source_id=job.source_id,
                )

        db.flush()
        return cluster

    @classmethod
    def batch_deduplicate(cls, db: Session, limit: int = 100) -> int:
        """
        Processes unclustered open jobs in batches.
        """
        stmt = (
            select(Job)
            .where(Job.cluster_id.is_(None), Job.status == "open")
            .limit(limit)
        )
        unclustered = list(db.execute(stmt).scalars().all())

        for job in unclustered:
            cls.deduplicate_job(db, job)

        db.commit()
        return len(unclustered)
