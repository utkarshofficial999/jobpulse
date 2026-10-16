import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from src.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class JobFeedback(Base):
    """
    Tracks candidate interactions with specific jobs:
    'alerted'   -> Sent in an alert
    'viewed'    -> Clicked or viewed details
    'saved'     -> Bookmarked for later
    'applied'   -> Clicked direct apply link
    'dismissed' -> Marked not relevant (never alert again)
    """
    __tablename__ = "job_feedback"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id = Column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_id = Column(
        String(36),
        ForeignKey("job_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(String(32), nullable=False)  # alerted, viewed, saved, applied, dismissed
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="feedback")
    job = relationship("Job")
    cluster = relationship("JobCluster")

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "action", name="uq_user_job_action"),
        Index("idx_user_feedback_action", "user_id", "action"),
        Index("idx_user_cluster_action", "user_id", "cluster_id", "action"),
    )

    def __repr__(self):
        return f"<JobFeedback(user_id={self.user_id}, job_id={self.job_id}, action='{self.action}')>"
