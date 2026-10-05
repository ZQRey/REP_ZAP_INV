from SHARED.authentication import require_authenticated_user
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from SHARED.database import get_db
from SHARED.domain_transitions import InvalidTransition, transition_cartridge
from SHARED.models import Cartridge, CartridgeStatus, ADUser, HistoryLog, Branch, AppUser
from CARTRIDGE.app.schemas import (
    CartridgeResponse,
    CartridgeDetailResponse,
    CartridgeCreate,
    CartridgeUpdate,
    CartridgeAcceptanceRequest,
    ReturnFromVendorRequest,
    CartridgeIssueRequest,
    BulkIssueRequest
)

router = APIRouter(prefix="/api/cartridges", tags=["Cartridges"])


@router.get("", response_model=List[CartridgeResponse])
def get_cartridges(
    status_filter: Optional[CartridgeStatus] = Query(None, alias="status"),
    branch_id: Optional[int] = Query(None, description="Фильтр по филиалу"),
    q: Optional[str] = Query(None, description="Поиск по метке, модели или кабинету"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Optional[AppUser] = Depends(require_authenticated_user)
):
    """Список картриджей с фильтрацией по статусу, филиалу и роли пользователя."""
    query = db.query(Cartridge).options(
        joinedload(Cartridge.current_user),
        joinedload(Cartridge.branch)
    )

    # 2. Фильтр по статусу
    if status_filter:
        query = query.filter(Cartridge.status == status_filter)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Cartridge.marker_label.ilike(term),
                Cartridge.qr_code.ilike(term),
                Cartridge.model.ilike(term),
                Cartridge.cabinet.ilike(term),
            )
        )

    carts = query.order_by(Cartridge.updated_at.desc()).offset(offset).limit(limit).all()
    if current_user.role == "user":
        return [CartridgeResponse.model_validate(cart).model_copy(update={"notes": None}) for cart in carts]
    return carts


@router.get("/search/quick")
def quick_search(
    marker: Optional[str] = Query(None),
    qr: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Быстрый поиск картриджа по метке маркером или QR-коду."""
    if not marker and not qr:
        raise HTTPException(status_code=400, detail="Необходимо передать маркерную метку или QR-код.")

    query = db.query(Cartridge).options(
        joinedload(Cartridge.current_user),
        joinedload(Cartridge.branch)
    )
    if qr and qr.strip():
        cart = query.filter(Cartridge.qr_code == qr.strip()).first()
        if cart:
            return {"found": True, "cartridge": CartridgeResponse.model_validate(cart)}

    if marker and marker.strip():
        cart = query.filter(Cartridge.marker_label.ilike(marker.strip())).first()
        if cart:
            return {"found": True, "cartridge": CartridgeResponse.model_validate(cart)}

    return {"found": False, "cartridge": None}


@router.get("/{cartridge_id}", response_model=CartridgeDetailResponse)
def get_cartridge_detail(
    cartridge_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[AppUser] = Depends(require_authenticated_user)
):
    """Получить подробную информацию о картридже и полную историю перемещений."""
    cart = db.query(Cartridge).options(
        joinedload(Cartridge.current_user),
        joinedload(Cartridge.branch),
        joinedload(Cartridge.history)
    ).filter(Cartridge.id == cartridge_id).first()

    if not cart:
        raise HTTPException(status_code=404, detail="Картридж не найден.")

    return cart


@router.post("", response_model=CartridgeResponse, status_code=status.HTTP_201_CREATED)
def create_cartridge(
    payload: CartridgeCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Создать новый картридж в системе."""
    # Проверка уникальности маркера
    existing = db.query(Cartridge).filter(Cartridge.marker_label.ilike(payload.marker_label.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Картридж с меткой '{payload.marker_label}' уже существует.")

    cart = Cartridge(
        marker_label=payload.marker_label.strip(),
        qr_code=payload.qr_code.strip() if payload.qr_code else None,
        model=payload.model.strip(),
        cabinet=payload.cabinet.strip(),
        branch_id=payload.branch_id if current_user.role == "superadmin" else current_user.branch_id,
        status=payload.status,
        current_user_id=payload.current_user_id or None,
        notes=payload.notes,
        updated_at=datetime.utcnow()
    )
    db.add(cart)
    db.flush()

    # Запись в историю
    log = HistoryLog(
        cartridge_id=cart.id,
        action="Создание картриджа",
        user_name=current_user.full_name or current_user.username,
        details=f"Зарегистрирован в системе. Модель: {cart.model}, Кабинет: {cart.cabinet}."
    )
    db.add(log)
    db.commit()

    return db.query(Cartridge).options(
        joinedload(Cartridge.current_user),
        joinedload(Cartridge.branch)
    ).filter(Cartridge.id == cart.id).first()


@router.put("/{cartridge_id}", response_model=CartridgeResponse)
def update_cartridge(
    cartridge_id: int,
    payload: CartridgeUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Редактировать параметры картриджа."""
    cart = db.query(Cartridge).filter(Cartridge.id == cartridge_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Картридж не найден.")

    changes = []
    if payload.marker_label and payload.marker_label.strip() != cart.marker_label:
        changes.append(f"Метка: {cart.marker_label} -> {payload.marker_label.strip()}")
        cart.marker_label = payload.marker_label.strip()

    if payload.qr_code is not None:
        cart.qr_code = payload.qr_code.strip() if payload.qr_code else None

    if payload.model and payload.model.strip() != cart.model:
        changes.append(f"Модель: {cart.model} -> {payload.model.strip()}")
        cart.model = payload.model.strip()

    if payload.cabinet and payload.cabinet.strip() != cart.cabinet:
        changes.append(f"Кабинет: {cart.cabinet} -> {payload.cabinet.strip()}")
        cart.cabinet = payload.cabinet.strip()

    if payload.branch_id is not None:
        cart.branch_id = payload.branch_id if payload.branch_id > 0 else None

    if payload.current_user_id != cart.current_user_id:
        cart.current_user_id = payload.current_user_id

    if payload.notes is not None:
        cart.notes = payload.notes

    if payload.status and payload.status != cart.status:
        changes.append(f"Статус: {cart.status.value} -> {payload.status.value}")
        try:
            transition_cartridge(cart, payload.status)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    cart.updated_at = datetime.utcnow()

    if changes:
        db.add(
            HistoryLog(
                cartridge_id=cart.id,
                action="Редактирование",
                details="; ".join(changes)
            )
        )

    db.commit()
    return db.query(Cartridge).options(
        joinedload(Cartridge.current_user),
        joinedload(Cartridge.branch)
    ).filter(Cartridge.id == cart.id).first()


@router.delete("/{cartridge_id}")
def delete_cartridge(
    cartridge_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Удалить картридж из системы (Администратор или Супер администратор)."""
    cart = db.query(Cartridge).filter(Cartridge.id == cartridge_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Картридж не найден.")
    db.delete(cart)
    db.commit()
    return {"success": True, "message": "Картридж успешно удален."}


@router.post("/accept", response_model=CartridgeResponse)
def accept_cartridge(
    payload: CartridgeAcceptanceRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """
    ЭТАП 1: ПРИЕМКА (только операторы и администраторы)
    Оператор ищет/добавляет картридж по маркерной надписи, выбирает сотрудника из AD.
    """
    marker = payload.marker_label.strip()
    cart = db.query(Cartridge).filter(Cartridge.marker_label.ilike(marker)).first()

    user_obj = None
    user_name = "Не указан"
    if payload.current_user_id:
        user_obj = db.query(ADUser).filter(ADUser.samaccountname == payload.current_user_id).first()
        if user_obj:
            user_name = f"{user_obj.display_name} ({user_obj.samaccountname})"

    now = datetime.utcnow()

    if not cart:
        # Новый картридж
        cart = Cartridge(
            marker_label=marker,
            qr_code=payload.qr_code.strip() if payload.qr_code else None,
            model=payload.model.strip(),
            cabinet=payload.cabinet.strip(),
            branch_id=payload.branch_id if current_user.role == "superadmin" else current_user.branch_id,
            status=CartridgeStatus.PENDING_VENDOR,
            condition=payload.condition or "broken",
            current_user_id=payload.current_user_id or None,
            notes=payload.notes,
            updated_at=now
        )
        db.add(cart)
        db.flush()
        action_msg = "Новый картридж принят на заправку"
    else:
        # Существующий картридж
        try:
            transition_cartridge(cart, CartridgeStatus.PENDING_VENDOR)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        cart.condition = payload.condition or "broken"
        cart.current_user_id = payload.current_user_id
        if payload.model:
            cart.model = payload.model.strip()
        if payload.cabinet:
            cart.cabinet = payload.cabinet.strip()
        if payload.qr_code:
            cart.qr_code = payload.qr_code.strip()
        if payload.branch_id is not None:
            cart.branch_id = payload.branch_id
        cart.notes = payload.notes.strip() if payload.notes and payload.notes.strip() else None
        cart.updated_at = now
        action_msg = "Принят на заправку"

    details = (
        f"Принято от сотрудника: {user_name}. Кабинет: {cart.cabinet}. "
        f"Требуемое действие: {payload.action_required or 'Заправка'}. "
        f"Примечание: {payload.notes or 'нет'}"
    )

    log = HistoryLog(
        cartridge_id=cart.id,
        action=action_msg,
        user_name=current_user.full_name or current_user.username,
        details=details
    )
    db.add(log)
    db.commit()

    return db.query(Cartridge).options(
        joinedload(Cartridge.current_user),
        joinedload(Cartridge.branch)
    ).filter(Cartridge.id == cart.id).first()


@router.post("/{cartridge_id}/issue")
def issue_cartridge(
    cartridge_id: int,
    payload: Optional[CartridgeIssueRequest] = None,
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """
    ЭТАП 4: ВЫДАЧА (только операторы и администраторы)
    Сотрудник забирает готовый картридж. Оператор нажимает 'Выдан' -> статус 'in_use' (В работе).
    """
    cart = db.query(Cartridge).filter(Cartridge.id == cartridge_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Картридж не найден.")

    user_name = "Сотрудник"
    if cart.current_user:
        user_name = cart.current_user.display_name

    try:
        transition_cartridge(cart, CartridgeStatus.IN_USE)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    cart.updated_at = datetime.utcnow()

    actual_notes = (payload.notes if payload and payload.notes else None) or notes

    log = HistoryLog(
        cartridge_id=cart.id,
        action="Выдача в работу",
        user_name=current_user.full_name or current_user.username,
        details=f"Картридж выдан в кабинет {cart.cabinet} сотруднику {user_name}. {actual_notes or ''}"
    )
    db.add(log)
    db.commit()

    return {"success": True, "message": f"Картридж '{cart.marker_label}' успешно выдан в работу."}


@router.post("/bulk-issue")
def bulk_issue_cartridges(
    payload: BulkIssueRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """
    Массовая выдача готовых картриджей в работу (для ручной выдачи из отчета рассылки).
    """
    if not payload.cartridge_ids:
        raise HTTPException(status_code=400, detail="Не указаны картриджи для выдачи.")

    cartridges = db.query(Cartridge).filter(Cartridge.id.in_(payload.cartridge_ids)).all()
    count = 0
    now = datetime.utcnow()

    for cart in cartridges:
        user_name = "Сотрудник"
        if cart.current_user:
            user_name = cart.current_user.display_name

        try:
            transition_cartridge(cart, CartridgeStatus.IN_USE)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=f"{cart.marker_label}: {exc}") from exc
        cart.updated_at = now

        log = HistoryLog(
            cartridge_id=cart.id,
            action="Выдача в работу (массовая)",
            user_name=current_user.full_name or current_user.username,
            details=f"Картридж выдан в кабинет {cart.cabinet} сотруднику {user_name}. {payload.notes or ''}"
        )
        db.add(log)
        count += 1

    db.commit()
    return {
        "success": True,
        "issued_count": count,
        "message": f"Успешно выдано в работу {count} картридж(ей)."
    }


@router.post("/return-vendor")
def return_cartridges_from_vendor(
    payload: ReturnFromVendorRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """
    ЭТАП 3: ВОЗВРАТ С ЗАПРАВКИ (только операторы и администраторы)
    Курьер привозит заправленные позиции -> статус 'ready_for_pickup' (Готов к выдаче).
    """
    if not payload.cartridge_ids:
        raise HTTPException(status_code=400, detail="Не выбраны картриджи для возврата.")

    cartridges = db.query(Cartridge).filter(Cartridge.id.in_(payload.cartridge_ids)).all()
    count = 0
    now = datetime.utcnow()

    for cart in cartridges:
        try:
            transition_cartridge(cart, CartridgeStatus.READY_FOR_PICKUP)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=f"{cart.marker_label}: {exc}") from exc
        cart.condition = "working"
        cart.updated_at = now
        log = HistoryLog(
            cartridge_id=cart.id,
            action="Возврат с заправки",
            details=f"Возвращен заправщиком. Готов к выдаче. {payload.notes or ''}"
        )
        db.add(log)
        count += 1

    db.commit()
    return {
        "success": True,
        "returned_count": count,
        "message": f"Успешно переведено в 'Готов к выдаче': {count} картридж(ей)."
    }

