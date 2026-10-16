import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Text,
    JSON,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from src.core.database import Base
from src.modules.jobs.models import VectorColumn


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    """Platform user who receives matching job alerts."""
    __tablename__ = "users"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    telegram_chat_id = Column(String(64), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    alert_frequency = Column(String(32), nullable=False, default="daily_9am")  # daily_9am, realtime, paused
    timezone = Column(String(64), nullable=False, default="UTC")

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    profile = relationship("CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    feedback = relationship("JobFeedback", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("NotificationOutbox", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class CandidateProfile(Base):
    """Candidate job search criteria, resume text, extracted skills, and vector embedding."""
    __tablename__ = "candidate_profiles"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Search preferences
    target_roles = Column(JSON, nullable=False, default=list)  # e.g. ["Backend Engineer", "Platform Engineer"]
    target_seniorities = Column(JSON, nullable=False, default=list)  # e.g. ["entry", "intern", "mid"]
    preferred_remote_types = Column(JSON, nullable=False, default=list)  # e.g. ["remote", "hybrid"]
    preferred_locations = Column(JSON, nullable=False, default=list)

    # Resume data & skills
    raw_resume_text = Column(Text, nullable=True)
    parsed_skills = Column(JSON, nullable=False, default=list)  # e.g. ["Python", "Docker", "PostgreSQL"]
    min_similarity_score = Column(Float, nullable=False, default=0.65)

    # Vector embedding of candidate intent + resume
    profile_embedding = Column(VectorColumn, nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="profile")

    @property
    def has_embedding(self) -> bool:
        return self.profile_embedding is not None

    def __repr__(self):
        return f"<CandidateProfile(id={self.id}, user_id={self.user_id}, roles={self.target_roles})>"
