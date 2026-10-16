from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.modules.users.models import User
from src.modules.matching.models import JobFeedback
from src.modules.matching.engine import MatchingEngine
from src.modules.notifications.models import NotificationOutbox
from src.modules.notifications.channels.telegram import TelegramDispatcher
from src.modules.notifications.channels.email import EmailDispatcher

_telegram = TelegramDispatcher()
_email = EmailDispatcher()


class OutboxService:
    """Manages transactional notification queuing, retry backoff, and delivery."""

    @staticmethod
    def queue_notification(
        db: Session,
        user_id: str,
        channel: str,
        recipient: str,
        subject: Optional[str],
        payload: dict,
    ) -> NotificationOutbox:
        """Enqueues an alert into the outbox within the caller's database transaction."""
        outbox_item = NotificationOutbox(
            user_id=user_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            payload=payload,
            status="pending",
            next_retry_at=datetime.now(timezone.utc),
        )
        db.add(outbox_item)
        db.flush()
        return outbox_item

    @classmethod
    def drain_outbox(cls, db: Session, batch_size: int = 50) -> dict:
        """
        Processes pending outbox items ready for dispatch.
        Updates status to 'sent' or applies exponential backoff on errors.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == "pending",
                NotificationOutbox.next_retry_at <= now,
            )
            .order_by(NotificationOutbox.created_at.asc())
            .limit(batch_size)
        )
        pending_items = list(db.execute(stmt).scalars().all())

        summary = {"processed": len(pending_items), "sent": 0, "failed": 0, "retried": 0}

        for item in pending_items:
            try:
                if item.channel == "telegram":
                    success = _telegram.send(item.recipient, item.payload)
                elif item.channel == "email":
                    success = _email.send(item.recipient, item.subject or "Pulse AI Job Alert", item.payload)
                else:
                    raise ValueError(f"Unknown notification channel: '{item.channel}'")

                if success:
                    item.status = "sent"
                    item.sent_at = datetime.now(timezone.utc)
                    item.last_error = None
                    summary["sent"] += 1

            except Exception as e:
                item.retry_count += 1
                item.last_error = str(e)[:1000]

                if item.retry_count >= 5:
                    item.status = "failed"
                    summary["failed"] += 1
                    logger.error("Outbox item permanently failed", outbox_id=item.id, retries=item.retry_count, error=str(e))
                else:
                    # Exponential backoff: 30s * 2^retries
                    backoff_secs = min(30 * (2 ** item.retry_count), 3600)
                    item.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_secs)
                    summary["retried"] += 1
                    logger.warning("Outbox item scheduled for retry", outbox_id=item.id, next_retry=item.next_retry_at, error=str(e))

        db.commit()
        return summary

    @classmethod
    def run_daily_digest(cls, db: Session, since_hours: int = 24) -> dict:
        """
        Scheduled 9:00 AM runner:
        Matches newly ingested jobs against all active subscribers and queues alerts.
        """
        stmt = select(User).where(User.is_active == True, User.alert_frequency == "daily_9am")
        users = list(db.execute(stmt).scalars().all())

        queued_count = 0
        now = datetime.now(timezone.utc)

        for user in users:
            matches = MatchingEngine.match_candidate(
                db=db,
                user_id=user.id,
                limit=5,
                only_recent_hours=since_hours,
            )

            if not matches:
                continue

            # Format match payload
            cards = []
            for m in matches:
                job = m.job
                cards.append({
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "locations": job.locations,
                    "remote_type": job.remote_type,
                    "seniority": job.seniority,
                    "apply_url": job.apply_url,
                    "match_score": m.breakdown.final_score,
                    "matched_skills": m.breakdown.matched_skills,
                })
                # Record alerted feedback so we don't spam the same job tomorrow
                feedback = JobFeedback(
                    user_id=user.id,
                    job_id=job.id,
                    cluster_id=job.cluster_id,
                    action="alerted",
                )
                db.add(feedback)

            payload = {
                "user_name": user.full_name or "Candidate",
                "matches": cards,
                "generated_at": now.isoformat(),
            }

            # Enqueue preferred channel: Telegram if chat_id present, else Email
            if user.telegram_chat_id:
                cls.queue_notification(
                    db=db,
                    user_id=user.id,
                    channel="telegram",
                    recipient=user.telegram_chat_id,
                    subject="Pulse AI Job Alert",
                    payload=payload,
                )
                queued_count += 1
            elif user.email:
                cls.queue_notification(
                    db=db,
                    user_id=user.id,
                    channel="email",
                    recipient=user.email,
                    subject="Pulse AI: Your Daily Job Opportunities",
                    payload=payload,
                )
                queued_count += 1

        db.commit()
        logger.info("Daily 9:00 AM digest matching completed", users_evaluated=len(users), alerts_queued=queued_count)
        return {"users_evaluated": len(users), "alerts_queued": queued_count}
