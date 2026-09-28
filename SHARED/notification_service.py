"""Durable notification outbox and retry policy."""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from SHARED.models import Notification, NotificationStatus

RETRY_DELAYS_SECONDS = (60, 300, 900, 3600, 21600)
MAX_ATTEMPTS = len(RETRY_DELAYS_SECONDS) + 1


def make_idempotency_key(*, channel: str, recipient: str, event: str, entity_id: int, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"{channel}:{event}:{entity_id}:{recipient}:{digest}"


def enqueue(
    db: Session,
    *,
    branch_id: int | None,
    cartridge_id: int | None,
    recipient: str,
    payload: dict,
    idempotency_key: str,
    instance_name: str | None = None,
) -> tuple[Notification, bool]:
    existing = db.query(Notification).filter(Notification.idempotency_key == idempotency_key).first()
    if existing:
        return existing, False
    # A nested transaction contains the uniqueness race without rolling back other
    # notifications already queued by the same HTTP request.
    try:
        with db.begin_nested():
            item = Notification(
                branch_id=branch_id,
                cartridge_id=cartridge_id,
                channel="whatsapp",
                recipient=recipient,
                payload=payload,
                status=NotificationStatus.PENDING,
                attempts=0,
                idempotency_key=idempotency_key,
                instance_name=instance_name,
            )
            db.add(item)
            db.flush()
        return item, True
    except Exception:
        existing = db.query(Notification).filter(Notification.idempotency_key == idempotency_key).first()
        if existing:
            return existing, False
        raise


def mark_sent(item: Notification, provider_message_id: str | None = None) -> None:
    item.status = NotificationStatus.SENT
    item.sent_at = datetime.utcnow()
    item.provider_message_id = provider_message_id
    item.last_error = None
    item.next_attempt_at = None


def mark_failed(item: Notification, error: str) -> None:
    item.last_error = (error or "Unknown provider error")[:4000]
    if item.attempts >= MAX_ATTEMPTS:
        item.status = NotificationStatus.DEAD
        item.next_attempt_at = None
        return
    delay_index = min(max(item.attempts - 1, 0), len(RETRY_DELAYS_SECONDS) - 1)
    item.status = NotificationStatus.RETRY
    item.next_attempt_at = datetime.utcnow() + timedelta(seconds=RETRY_DELAYS_SECONDS[delay_index])
