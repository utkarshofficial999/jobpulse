import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class NotificationOutbox(Base):
    """
    Transactional Outbox for candidate notifications.
    Ensures at-least-once alert delivery even during third-party API outages.
    """
    __tablename__ = "notification_outbox"

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
    channel = Column(String(32), nullable=False)  # 'telegram', 'email'
    recipient = Column(String(255), nullable=False)
    subject = Column(String(512), nullable=True)
    payload = Column(JSON, nullable=False)  # list of matched job cards, match scores, links

    status = Column(String(32), nullable=False, default="pending")  # pending, sent, failed
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("idx_outbox_pending", "status", "next_retry_at"),
    )

    def __repr__(self):
        return f"<NotificationOutbox(id={self.id}, channel='{self.channel}', status='{self.status}')>"
