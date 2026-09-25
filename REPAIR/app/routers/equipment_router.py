from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc

from SHARED.database import get_db
from SHARED.models import (
    Asset,
    AssetType,
    AssetStatus,
    AssetCondition,
    Branch,
    ADUser,
    AppUser,
    EquipmentHistoryLog
)
from SHARED.auth_service import get_current_user, require_role
from REPAIR.app.schemas import (
    EquipmentResponse,
    EquipmentDetailResponse,
    EquipmentCreate,
    EquipmentUpdate,
    EquipmentAcceptanceRequest,
    InstallAtWorkplaceRequest,
    ReturnFromSCRequest
)
from REPAIR.app.services.equipment_service import EquipmentService

router = APIRouter(prefix="/api/v1/repair/equipment", tags=["Repair Equipment"])


@router.get("", response_model=List[EquipmentResponse])
def list_equipment(
    branch_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    condition_filter: Optional[str] = Query(None), # "working", "broken"
    type_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Список оборудования с фильтрацией по филиалам, статусу, типу и состоянию."""
    query = db.query(Asset).options(
        joinedload(Asset.branch),
        joinedload(Asset.responsible_ad_user)
    )

    # Ограничение по филиалу
    if current_user.role != "superadmin" and current_user.branch_id:
        query = query.filter(Asset.branch_id == current_user.branch_id)
    elif branch_id:
        query = query.filter(Asset.branch_id == branch_id)

    if status_filter:
        try:
            st = AssetStatus(status_filter)
            query = query.filter(Asset.status == st)
        except Exception:
            pass

    if condition_filter:
        try:
            cond = AssetCondition(condition_filter)
            query = query.filter(Asset.condition == cond)
        except Exception:
            pass

    if type_filter:
        try:
            t = AssetType(type_filter)
            query = query.filter(Asset.asset_type == t)
        except Exception:
            pass

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Asset.inventory_number.ilike(term),
                Asset.serial_number.ilike(term),
                Asset.name.ilike(term),
                Asset.hostname.ilike(term),
                Asset.cabinet.ilike(term)
            )
        )

    assets = query.order_by(desc(Asset.updated_at)).all()
    
    result = []
    for a in assets:
        result.append(EquipmentResponse(
            id=a.id,
            inventory_number=a.inventory_number,
            serial_number=a.serial_number,
            name=a.name,
            asset_type=a.asset_type,
            status=a.status,
            condition=a.condition,
            cabinet=a.cabinet,
            branch_id=a.branch_id,
            branch_name=a.branch.name if a.branch else "Все филиалы",
            current_user_id=a.current_user_id,
            current_user_name=a.responsible_ad_user.display_name if a.responsible_ad_user else None,
            hostname=a.hostname,
            os_name=a.os_name,
            ad_guid=a.ad_guid,
            specs=a.specs,
            notes=a.notes,
            updated_at=a.updated_at
        ))
    return result


@router.get("/find-by-inv")
def find_by_inv_or_serial(
    query_str: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Поиск оборудования по инвентарному или серийному номеру для быстрого ввода."""
    term = query_str.strip()
    asset = db.query(Asset).options(
        joinedload(Asset.branch),
        joinedload(Asset.responsible_ad_user)
    ).filter(
        or_(
            Asset.inventory_number.ilike(term),
            Asset.serial_number.ilike(term),
            Asset.hostname.ilike(term)
        )
    ).first()

    if not asset:
        return {"found": False, "equipment": None}

    return {
        "found": True,
        "equipment": EquipmentResponse(
            id=asset.id,
            inventory_number=asset.inventory_number,
            serial_number=asset.serial_number,
            name=asset.name,
            asset_type=asset.asset_type,
            status=asset.status,
            condition=asset.condition,
            cabinet=asset.cabinet,
            branch_id=asset.branch_id,
            branch_name=asset.branch.name if asset.branch else None,
            current_user_id=asset.current_user_id,
            current_user_name=asset.responsible_ad_user.display_name if asset.responsible_ad_user else None,
            hostname=asset.hostname,
            os_name=asset.os_name,
            specs=asset.specs,
            notes=asset.notes,
            updated_at=asset.updated_at
        )
    }


@router.get("/{asset_id}", response_model=EquipmentDetailResponse)
def get_equipment_detail(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Детальная карточка оборудования с историей операций."""
    asset = db.query(Asset).options(
        joinedload(Asset.branch),
        joinedload(Asset.responsible_ad_user),
        joinedload(Asset.history)
    ).filter(Asset.id == asset_id).first()

    if not asset:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")

    history_items = [
        {
            "id": h.id,
            "asset_id": h.asset_id,
            "action": h.action,
            "user_name": h.user_name,
            "timestamp": h.timestamp,
            "details": h.details
        }
        for h in asset.history
    ]

    return EquipmentDetailResponse(
        id=asset.id,
        inventory_number=asset.inventory_number,
        serial_number=asset.serial_number,
        name=asset.name,
        asset_type=asset.asset_type,
        status=asset.status,
        condition=asset.condition,
        cabinet=asset.cabinet,
        branch_id=asset.branch_id,
        branch_name=asset.branch.name if asset.branch else None,
        current_user_id=asset.current_user_id,
        current_user_name=asset.responsible_ad_user.display_name if asset.responsible_ad_user else None,
        hostname=asset.hostname,
        os_name=asset.os_name,
        ad_guid=asset.ad_guid,
        specs=asset.specs,
        notes=asset.notes,
        updated_at=asset.updated_at,
        history=history_items
    )


@router.post("/accept", response_model=EquipmentResponse)
def accept_broken_equipment(
    payload: EquipmentAcceptanceRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    ЭТАП 1: Приемка неисправной техники в IT-отдел.
    Оборудование переходит в статус pending_sc (Ожидает СЦ) и состояние BROKEN (В нерабочем состоянии).
    """
    asset = EquipmentService.accept_equipment(
        db=db,
        inventory_number=payload.inventory_number,
        name=payload.name,
        asset_type=payload.asset_type,
        cabinet=payload.cabinet,
        branch_id=payload.branch_id or current_user.branch_id,
        current_user_id=payload.current_user_id,
        serial_number=payload.serial_number,
        reported_issue=payload.reported_issue,
        condition=payload.condition,
        notes=payload.notes,
        operator_name=current_user.full_name
    )

    return EquipmentResponse(
        id=asset.id,
        inventory_number=asset.inventory_number,
        serial_number=asset.serial_number,
        name=asset.name,
        asset_type=asset.asset_type,
        status=asset.status,
        condition=asset.condition,
        cabinet=asset.cabinet,
        branch_id=asset.branch_id,
        branch_name=asset.branch.name if asset.branch else None,
        current_user_id=asset.current_user_id,
        hostname=asset.hostname,
        os_name=asset.os_name,
        specs=asset.specs,
        notes=asset.notes,
        updated_at=asset.updated_at
    )


@router.post("", response_model=EquipmentResponse)
def create_manual_equipment(
    payload: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """Ручной ввод техники (мониторы, принтеры, ИБП и сетевое оборудование)."""
    inv = payload.inventory_number.strip()
    existing = db.query(Asset).filter(Asset.inventory_number.ilike(inv)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Оборудование с инвентарным номером '{inv}' уже зарегистрировано")

    now = datetime.utcnow()
    asset = Asset(
        inventory_number=inv,
        serial_number=payload.serial_number.strip() if payload.serial_number else None,
        name=payload.name.strip(),
        asset_type=payload.asset_type,
        status=payload.status,
        condition=payload.condition,
        cabinet=payload.cabinet.strip() if payload.cabinet else None,
        branch_id=payload.branch_id or current_user.branch_id,
        current_user_id=payload.current_user_id,
        specs=payload.specs or {},
        notes=payload.notes,
        created_at=now,
        updated_at=now
    )
    db.add(asset)
    db.flush()

    EquipmentService.log_history(
        db=db,
        asset_id=asset.id,
        action="Регистрация техники (Ручной ввод)",
        user_name=current_user.full_name,
        details=f"Добавлено вручную: {asset.name} ({asset.inventory_number}). Состояние: {asset.condition.value}."
    )
    db.commit()
    db.refresh(asset)

    return EquipmentResponse(
        id=asset.id,
        inventory_number=asset.inventory_number,
        serial_number=asset.serial_number,
        name=asset.name,
        asset_type=asset.asset_type,
        status=asset.status,
        condition=asset.condition,
        cabinet=asset.cabinet,
        branch_id=asset.branch_id,
        branch_name=asset.branch.name if asset.branch else None,
        current_user_id=asset.current_user_id,
        hostname=asset.hostname,
        os_name=asset.os_name,
        specs=asset.specs,
        notes=asset.notes,
        updated_at=asset.updated_at
    )


@router.put("/{asset_id}", response_model=EquipmentResponse)
def update_equipment(
    asset_id: int,
    payload: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """Обновление параметров и состояния оборудования."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")

    changes = []
    if payload.inventory_number and payload.inventory_number.strip() != asset.inventory_number:
        changes.append(f"Инв. №: {asset.inventory_number} -> {payload.inventory_number.strip()}")
        asset.inventory_number = payload.inventory_number.strip()

    if payload.serial_number is not None:
        asset.serial_number = payload.serial_number.strip() if payload.serial_number else None

    if payload.name and payload.name.strip() != asset.name:
        changes.append(f"Название: {asset.name} -> {payload.name.strip()}")
        asset.name = payload.name.strip()

    if payload.asset_type and payload.asset_type != asset.asset_type:
        changes.append(f"Тип: {asset.asset_type.value} -> {payload.asset_type.value}")
        asset.asset_type = payload.asset_type

    if payload.condition and payload.condition != asset.condition:
        changes.append(f"Состояние: {asset.condition.value} -> {payload.condition.value}")
        asset.condition = payload.condition

    if payload.status and payload.status != asset.status:
        changes.append(f"Статус: {asset.status.value} -> {payload.status.value}")
        asset.status = payload.status

    if payload.cabinet is not None:
        asset.cabinet = payload.cabinet.strip() if payload.cabinet else None

    if payload.branch_id is not None:
        asset.branch_id = payload.branch_id if payload.branch_id > 0 else None

    if payload.current_user_id is not None:
        asset.current_user_id = payload.current_user_id if payload.current_user_id else None

    if payload.notes is not None:
        asset.notes = payload.notes

    asset.updated_at = datetime.utcnow()

    if changes:
        EquipmentService.log_history(
            db=db,
            asset_id=asset.id,
            action="Редактирование",
            user_name=current_user.full_name,
            details="; ".join(changes)
        )

    db.commit()
    db.refresh(asset)

    return EquipmentResponse(
        id=asset.id,
        inventory_number=asset.inventory_number,
        serial_number=asset.serial_number,
        name=asset.name,
        asset_type=asset.asset_type,
        status=asset.status,
        condition=asset.condition,
        cabinet=asset.cabinet,
        branch_id=asset.branch_id,
        branch_name=asset.branch.name if asset.branch else None,
        current_user_id=asset.current_user_id,
        hostname=asset.hostname,
        os_name=asset.os_name,
        specs=asset.specs,
        notes=asset.notes,
        updated_at=asset.updated_at
    )


@router.delete("/{asset_id}")
def delete_equipment(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin"]))
):
    """Списание или удаление единицы техники."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")

    db.delete(asset)
    db.commit()
    return {"success": True, "message": f"Оборудование '{asset.inventory_number}' успешно удалено"}


# ==========================================
# СТАДИИ РЕМОНТА БЕЗ WHATSAPP
# ==========================================

@router.post("/return-sc")
def return_equipment_from_sc(
    payload: ReturnFromSCRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    ЭТАП 3: Принятие техники из СЦ в IT-отдел.
    Простая отметка о принятии из сервисного центра:
    - Статус переходит в returned_it (Принято из СЦ в IT-отдел, готово к установке).
    - Состояние переходит в WORKING (В рабочем состоянии 🟢).
    - Никаких WhatsApp-сообщений не отправляется!
    """
    target_asset_ids = payload.asset_ids or []
    now = datetime.utcnow()

    assets = db.query(Asset).filter(Asset.id.in_(target_asset_ids)).all()
    count = 0
    for a in assets:
        a.status = AssetStatus.RETURNED_IT
        a.condition = payload.condition or AssetCondition.WORKING
        a.updated_at = now
        EquipmentService.log_history(
            db=db,
            asset_id=a.id,
            action="Принято из СЦ в IT-отдел",
            user_name=current_user.full_name,
            details=f"Возвращено из ремонта. Результат: {payload.diagnostic_result}. Работы: {payload.work_performed}. Стоимость: {payload.cost} руб."
        )
        count += 1

    db.commit()
    return {
        "success": True,
        "count": count,
        "message": f"Успешно принято из сервисного центра в IT-отдел: {count} единиц техники."
    }


@router.post("/install-workplace")
def install_equipment_at_workplace(
    payload: InstallAtWorkplaceRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    ЭТАП 4: Установка техники на рабочее место.
    Отметка об установке и вводе в эксплуатацию:
    - Статус переходит в at_workplace (На рабочем месте).
    - Состояние: WORKING (В рабочем состоянии 🟢).
    - Кабинет и ответственный сотрудник закрепляются.
    - Никаких WhatsApp-сообщений!
    """
    now = datetime.utcnow()
    assets = db.query(Asset).filter(Asset.id.in_(payload.asset_ids)).all()
    count = 0

    for a in assets:
        a.status = AssetStatus.AT_WORKPLACE
        a.condition = AssetCondition.WORKING
        if payload.cabinet:
            a.cabinet = payload.cabinet.strip()
        if payload.current_user_id:
            a.current_user_id = payload.current_user_id
        a.updated_at = now

        EquipmentService.log_history(
            db=db,
            asset_id=a.id,
            action="Установка на рабочее место",
            user_name=current_user.full_name,
            details=f"Техника установлена и введена в эксплуатацию в кабинете {a.cabinet or '—'}. {payload.notes or ''}"
        )
        count += 1

    db.commit()
    return {
        "success": True,
        "count": count,
        "message": f"Успешно установлено на рабочие места: {count} единиц техники."
    }
