from datetime import datetime

from SHARED.models import Notification, NotificationStatus
from SHARED.notification_service import make_idempotency_key, mark_failed, mark_sent, MAX_ATTEMPTS


def test_idempotency_key_is_stable_for_payload_order():
    a = make_idempotency_key(channel="whatsapp", recipient="7701", event="ready", entity_id=1, payload={"b": 2, "a": 1})
    b = make_idempotency_key(channel="whatsapp", recipient="7701", event="ready", entity_id=1, payload={"a": 1, "b": 2})
    assert a == b


def test_retry_eventually_becomes_dead():
    item = Notification(
        recipient="7701", channel="whatsapp", payload={}, idempotency_key="k",
        status=NotificationStatus.PROCESSING, attempts=1,
    )
    mark_failed(item, "temporary")
    assert item.status == NotificationStatus.RETRY
    assert item.next_attempt_at is not None

    item.attempts = MAX_ATTEMPTS
    mark_failed(item, "permanent")
    assert item.status == NotificationStatus.DEAD
    assert item.next_attempt_at is None


def test_mark_sent_clears_retry_state():
    item = Notification(
        recipient="7701", channel="whatsapp", payload={}, idempotency_key="k2",
        status=NotificationStatus.RETRY, attempts=2, last_error="x", next_attempt_at=datetime.utcnow(),
    )
    mark_sent(item, "provider-1")
    assert item.status == NotificationStatus.SENT
    assert item.provider_message_id == "provider-1"
    assert item.sent_at is not None
    assert item.last_error is None
    assert item.next_attempt_at is None


def test_worker_reclaims_stale_processing_lease(monkeypatch):
    from datetime import timedelta
    from SHARED.database import SessionLocal
    import SHARED.notification_worker as worker

    with SessionLocal() as db:
        item = Notification(
            recipient="7702", channel="whatsapp", payload={"message": "x"},
            idempotency_key="stale-worker-test", status=NotificationStatus.PROCESSING,
            attempts=1, next_attempt_at=datetime.utcnow() - timedelta(minutes=10),
        )
        db.add(item)
        db.commit()
        item_id = item.id

    monkeypatch.setattr(worker, "PROCESSING_LEASE_SECONDS", 60)
    with SessionLocal() as db:
        claimed = worker._claim_batch(db)
        assert [item.id for item in claimed if item.id == item_id] == [item_id]
        reclaimed = db.get(Notification, item_id)
        assert reclaimed.status == NotificationStatus.PROCESSING
        assert reclaimed.attempts == 2
        assert reclaimed.next_attempt_at is not None
