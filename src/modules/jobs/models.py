import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from src.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# Register JobCluster in Base mapper registry
import src.modules.deduplication.models  # noqa: F401


class VectorColumn(TypeDecorator):
    """
    Dialect-aware vector column.
    Uses pgvector's Vector(384) on PostgreSQL, falls back to JSON on SQLite/others.
    """
    impl = Vector(384)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(384))
        return dialect.type_descriptor(JSON())


class RawJob(Base):
    """Immutable audit record of raw payload straight from ATS feed."""
    __tablename__ = "raw_jobs"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    source_id = Column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    # Relationships
    source = relationship("Source", back_populates="raw_jobs")

    __table_args__ = (
        Index("idx_raw_jobs_source_ext", "source_id", "external_id"),
    )

    def __repr__(self):
        return f"<RawJob(id={self.id}, source_id={self.source_id}, external_id='{self.external_id}')>"


class Job(Base):
    """Canonical, normalized job entity."""
    __tablename__ = "jobs"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    source_id = Column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id = Column(String(255), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)

    # Deduplication & Clustering (Milestone 2)
    cluster_id = Column(String(36), ForeignKey("job_clusters.id", ondelete="SET NULL"), nullable=True, index=True)
    is_primary_in_cluster = Column(Boolean, nullable=False, default=True)

    # Canonical attributes
    title = Column(String(512), nullable=False)
    company = Column(String(255), nullable=False)
    locations = Column(JSON, nullable=False, default=list)  # list of strings e.g. ["San Francisco, CA"]
    remote_type = Column(String(32), nullable=False, default="unknown")  # remote, hybrid, onsite, unknown
    seniority = Column(String(32), nullable=False, default="unspecified")  # intern, entry, mid, senior, lead, staff, executive, unspecified
    employment_type = Column(String(32), nullable=False, default="unknown")  # full_time, part_time, contract, internship, temporary, unknown
    description = Column(Text, nullable=False)
    apply_url = Column(Text, nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=True)

    # Lifecycle state
    status = Column(String(32), nullable=False, default="open")  # open, closed
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Verification state (Milestone 2)
    verification_status = Column(String(32), nullable=False, default="unverified")  # unverified, verified_active, verified_closed
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_error = Column(Text, nullable=True)

    # Semantic Vector Embedding (Milestone 2)
    embedding = Column(VectorColumn, nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    source = relationship("Source", back_populates="canonical_jobs")
    cluster = relationship("JobCluster", back_populates="jobs", foreign_keys=[cluster_id])

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_jobs_source_external"),
        Index("idx_jobs_source_status", "source_id", "status"),
        Index("idx_jobs_last_seen", "source_id", "last_seen_at"),
        Index("idx_jobs_verification", "status", "verification_status"),
        Index("idx_jobs_unembedded", "status", "embedded_at"),
    )

    def __repr__(self):
        return f"<Job(id={self.id}, company='{self.company}', title='{self.title}', status='{self.status}')>"
