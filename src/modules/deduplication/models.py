import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class JobCluster(Base):
    """
    Cluster grouping identical jobs across multiple sources (e.g. Greenhouse + Ashby + YC).
    """
    __tablename__ = "job_clusters"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    company_normalized = Column(String(255), nullable=False)
    title_normalized = Column(String(512), nullable=False)
    dedup_fingerprint = Column(String(64), nullable=False, unique=True, index=True)

    primary_job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL", use_alter=True), nullable=True)
    job_count = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="cluster", foreign_keys="Job.cluster_id")
    primary_job = relationship("Job", foreign_keys=[primary_job_id], post_update=True)

    def __repr__(self):
        return f"<JobCluster(id={self.id}, company='{self.company_normalized}', title='{self.title_normalized}', count={self.job_count})>"
