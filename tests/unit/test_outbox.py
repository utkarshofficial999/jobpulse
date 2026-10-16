from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from src.modules.users.models import User
from src.modules.notifications.models import NotificationOutbox
from src.modules.notifications.outbox import OutboxService


def test_outbox_queue_and_drain_success(db_session):
    user = User(email="test@example.com", full_name="Test Candidate")
    db_session.add(user)
    db_session.commit()

    # 1. Enqueue item
    item = OutboxService.queue_notification(
        db=db_session,
        user_id=user.id,
        channel="email",
        recipient="test@example.com",
        subject="Test Job Alert",
        payload={"matches": [{"title": "Software Engineer", "company": "Stripe"}]},
    )
    db_session.commit()

    assert item.status == "pending"
    assert item.retry_count == 0

    # 2. Drain outbox
    summary = OutboxService.drain_outbox(db_session, batch_size=10)

    assert summary["processed"] == 1
    assert summary["sent"] == 1
    assert summary["failed"] == 0

    db_session.refresh(item)
    assert item.status == "sent"
    assert item.sent_at is not None


def test_outbox_retry_exponential_backoff(db_session):
    user = User(email="retry@example.com")
    db_session.add(user)
    db_session.commit()

    item = OutboxService.queue_notification(
        db=db_session,
        user_id=user.id,
        channel="telegram",
        recipient="999888",
        subject=None,
        payload={"matches": []},
    )
    db_session.commit()

    # Simulate dispatch failure (e.g. Telegram 502 error)
    with patch("src.modules.notifications.outbox._telegram.send", side_effect=Exception("Telegram connection timeout")):
        summary = OutboxService.drain_outbox(db_session)

    assert summary["retried"] == 1
    db_session.refresh(item)
    assert item.status == "pending"
    assert item.retry_count == 1
    assert item.last_error is not None
    retry_time = item.next_retry_at.replace(tzinfo=timezone.utc) if item.next_retry_at.tzinfo is None else item.next_retry_at
    assert retry_time > datetime.now(timezone.utc)


def test_outbox_max_retries_transition_to_failed(db_session):
    user = User(email="fail@example.com")
    db_session.add(user)
    db_session.commit()

    item = OutboxService.queue_notification(
        db=db_session,
        user_id=user.id,
        channel="email",
        recipient="fail@example.com",
        subject=None,
        payload={"matches": []},
    )
    # Pre-set retry count to 4 (so next failure hits 5)
    item.retry_count = 4
    db_session.commit()

    with patch("src.modules.notifications.outbox._email.send", side_effect=Exception("SMTP Authentication Error")):
        summary = OutboxService.drain_outbox(db_session)

    assert summary["failed"] == 1
    db_session.refresh(item)
    assert item.status == "failed"
    assert item.retry_count == 5
