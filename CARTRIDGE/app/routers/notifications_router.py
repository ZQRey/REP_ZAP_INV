from SHARED.authentication import require_authenticated_user
from typing import Dict, Any
import os
import redis
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import Cartridge, CartridgeStatus, AppUser
from SHARED.notification_service import enqueue, make_idempotency_key
from app.schemas import NotifyWhatsAppRequest
from app.services.settings_service import SettingsService
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.post("/whatsapp/ready")
def notify_ready_cartridges(
    payload: NotifyWhatsAppRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
) -> Dict[str, Any]:
    """Queue ready-cartridge WhatsApp notifications without blocking on Evolution API."""
    settings = SettingsService.get_all(db)
    template = settings.get(
        "wa_message_template",
        "Здравствуйте, {name}! Ваш картридж {marker} ({model}) для кабинета {cabinet} успешно заправлен и ожидает выдачи в {it_office}."
    )
    it_office = settings.get("it_office", "Кабинет IT")
    instance_name, sender_desc = WhatsAppService.get_instance_for_user(db, current_user)

    query = db.query(Cartridge).options(joinedload(Cartridge.current_user), joinedload(Cartridge.branch))
    if payload.cartridge_ids:
        query = query.filter(Cartridge.id.in_(payload.cartridge_ids))
    else:
        query = query.filter(Cartridge.status == CartridgeStatus.READY_FOR_PICKUP)
    cartridges = query.all()

    results = []
    queued_count = 0
    duplicate_count = 0
    failed_count = 0

    for cart in cartridges:
        user = cart.current_user
        phone = user.phone if user else None
        user_name = user.display_name if user else "Коллега"
        cart_branch = cart.branch or (current_user.branch if current_user.branch_id else None)
        branch_it_office = (
            cart_branch.it_office.strip()
            if cart_branch and cart_branch.it_office and cart_branch.it_office.strip()
            else None
        ) or it_office
        branch_template = (
            cart_branch.wa_message_template.strip()
            if cart_branch and cart_branch.wa_message_template and cart_branch.wa_message_template.strip()
            else None
        ) or template

        clean_phone = WhatsAppService.clean_phone(phone or "")
        if not clean_phone:
            failed_count += 1
            results.append({"cartridge_id": cart.id, "marker": cart.marker_label, "queued": False, "error": "У сотрудника не указан корректный номер телефона."})
            continue

        message = WhatsAppService.format_message(
            template=branch_template,
            name=user_name,
            marker=cart.marker_label,
            model=cart.model,
            cabinet=cart.cabinet,
            it_office=branch_it_office,
        )
        notification_payload = {
            "message": message,
            "user_name": user_name,
            "marker": cart.marker_label,
            "sender": sender_desc,
        }
        key = make_idempotency_key(
            channel="whatsapp",
            recipient=clean_phone,
            event="cartridge_ready",
            entity_id=cart.id,
            payload=notification_payload,
        )
        item, created = enqueue(
            db,
            branch_id=cart.branch_id,
            cartridge_id=cart.id,
            recipient=clean_phone,
            payload=notification_payload,
            idempotency_key=key,
            instance_name=instance_name,
        )
        queued_count += int(created)
        duplicate_count += int(not created)
        results.append({
            "cartridge_id": cart.id,
            "marker": cart.marker_label,
            "notification_id": item.id,
            "queued": created,
            "duplicate": not created,
            "status": item.status.value if hasattr(item.status, "value") else item.status,
        })

    db.commit()
    if queued_count:
        try:
            redis.Redis.from_url(os.environ["REDIS_URL"]).lpush("notifications:wakeup", str(queued_count))
        except Exception:
            # PostgreSQL outbox remains authoritative; worker polling will still deliver.
            pass
    return {
        "success": failed_count == 0,
        "total": len(cartridges),
        "queued_count": queued_count,
        "duplicate_count": duplicate_count,
        "failed_count": failed_count,
        "sender": sender_desc,
        "instance_name": instance_name,
        "message": f"Поставлено в очередь: {queued_count}; уже было в очереди/отправлено: {duplicate_count}; ошибок данных: {failed_count}.",
        "results": results,
    }
