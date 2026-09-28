"""Notification outbox worker.

Runs as a separate container. PostgreSQL is the source of truth; Redis is used only as a
short wake-up/backoff primitive so a Redis restart cannot lose queued notifications.
"""
import asyncio
import os
from datetime import datetime, timedelta

import redis

from SHARED.database import SessionLocal
from SHARED.models import HistoryLog, Notification, NotificationStatus
from SHARED.notification_service import mark_failed, mark_sent
from CARTRIDGE.app.services.whatsapp_service import WhatsAppService

POLL_SECONDS = int(os.getenv("NOTIFICATION_POLL_SECONDS", "5"))
BATCH_SIZE = int(os.getenv("NOTIFICATION_BATCH_SIZE", "25"))
PROCESSING_LEASE_SECONDS = int(os.getenv("NOTIFICATION_PROCESSING_LEASE_SECONDS", "120"))


def _redis_client():
    return redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def _claim_batch(db):
    now = datetime.utcnow()
    stale_before = now - timedelta(seconds=PROCESSING_LEASE_SECONDS)
    # PROCESSING uses next_attempt_at as a lease timestamp. If a worker dies after
    # committing the claim but before delivery, another worker may reclaim it once
    # the lease expires instead of leaving the notification stuck forever.
    items = (
        db.query(Notification)
        .filter(
            (
                Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.RETRY])
                & ((Notification.next_attempt_at.is_(None)) | (Notification.next_attempt_at <= now))
            )
            | (
                (Notification.status == NotificationStatus.PROCESSING)
                & (Notification.next_attempt_at.is_not(None))
                & (Notification.next_attempt_at <= stale_before)
            )
        )
        .order_by(Notification.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(BATCH_SIZE)
        .all()
    )
    for item in items:
        item.status = NotificationStatus.PROCESSING
        item.attempts += 1
        item.next_attempt_at = now
    return items


async def process_once() -> int:
    db = SessionLocal()
    try:
        items = _claim_batch(db)
        db.commit()

        processed = 0
        for item in items:
            # Refresh after commit so each delivery has current persisted state.
            item = db.query(Notification).filter(Notification.id == item.id).first()
            if not item:
                continue
            try:
                if item.channel != "whatsapp":
                    raise RuntimeError(f"Unsupported notification channel: {item.channel}")
                result = await WhatsAppService.send_text_message(
                    db,
                    phone=item.recipient,
                    message=(item.payload or {}).get("message", ""),
                    instance_name=item.instance_name,
                )
                if result.get("success"):
                    provider_id = (result.get("data") or {}).get("message_id")
                    mark_sent(item, provider_id)
                    if item.cartridge_id:
                        db.add(HistoryLog(
                            cartridge_id=item.cartridge_id,
                            action="Оповещение WhatsApp",
                            user_name=(item.payload or {}).get("user_name"),
                            details=f"Уведомление #{item.id} отправлено асинхронным worker.",
                        ))
                else:
                    mark_failed(item, result.get("message") or "Provider rejected notification")
            except Exception as exc:
                mark_failed(item, f"{type(exc).__name__}: {exc}")
            db.commit()
            processed += 1
        return processed
    finally:
        db.close()


async def main():
    redis_client = _redis_client()
    while True:
        processed = await process_once()
        if processed:
            continue
        try:
            await asyncio.to_thread(redis_client.blpop, "notifications:wakeup", POLL_SECONDS)
        except Exception:
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
