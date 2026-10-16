import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from src.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


# Ensure related models are registered in Base mapper registry
import src.modules.jobs.models  # noqa: F401


class Source(Base):
    __tablename__ = "sources"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name = Column(String(255), nullable=False)
    connector_type = Column(String(64), nullable=False)  # e.g. "greenhouse"
    config = Column(JSON, nullable=False, default=dict)
    # config example: {"board_token": "stripe", "domain": "boards-api.greenhouse.io"}

    is_active = Column(Boolean, nullable=False, default=True)
    poll_interval_seconds = Column(Integer, nullable=False, default=3600)

    # Scheduler and backoff state
    next_run_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    raw_jobs = relationship("RawJob", back_populates="source", cascade="all, delete-orphan")
    canonical_jobs = relationship("Job", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Source(id={self.id}, name='{self.name}', connector='{self.connector_type}')>"
