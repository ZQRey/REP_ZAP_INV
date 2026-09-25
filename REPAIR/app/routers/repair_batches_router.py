from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from SHARED.database import get_db
from SHARED.models import (
    RepairBatch,
    RepairBatchItem,
    Asset,
    AssetStatus,
    AssetCondition,
    Branch,
    AppUser
)
from SHARED.auth_service import get_current_user, require_role
from REPAIR.app.schemas import (
    RepairBatchResponse,
    RepairBatchItemResponse,
    RepairBatchCreate,
    EquipmentResponse
)
from REPAIR.app.services.equipment_service import EquipmentService

router = APIRouter(prefix="/api/v1/repair/batches", tags=["Repair Batches"])


@router.get("", response_model=List[RepairBatchResponse])
def list_repair_batches(
    status_filter: Optional[str] = Query(None), # open / closed
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Список актов передачи техники в сервисный центр."""
    query = db.query(RepairBatch).options(
        joinedload(RepairBatch.branch),
        joinedload(RepairBatch.items).joinedload(RepairBatchItem.asset)
    )

    if current_user.role != "superadmin" and current_user.branch_id:
        query = query.filter(RepairBatch.branch_id == current_user.branch_id)
    elif branch_id:
        query = query.filter(RepairBatch.branch_id == branch_id)

    if status_filter:
        query = query.filter(RepairBatch.status == status_filter)

    batches = query.order_by(desc(RepairBatch.created_at)).all()

    result = []
    for b in batches:
        items_out = []
        for it in b.items:
            asset_out = None
            if it.asset:
                asset_out = EquipmentResponse(
                    id=it.asset.id,
                    inventory_number=it.asset.inventory_number,
                    serial_number=it.asset.serial_number,
                    name=it.asset.name,
                    asset_type=it.asset.asset_type,
                    status=it.asset.status,
                    condition=it.asset.condition,
                    cabinet=it.asset.cabinet,
                    branch_id=it.asset.branch_id,
                    branch_name=it.asset.branch.name if it.asset.branch else None,
                    hostname=it.asset.hostname,
                    os_name=it.asset.os_name,
                    notes=it.asset.notes,
                    updated_at=it.asset.updated_at
                )
            items_out.append(RepairBatchItemResponse(
                id=it.id,
                batch_id=it.batch_id,
                asset_id=it.asset_id,
                reported_issue=it.reported_issue,
                diagnostic_result=it.diagnostic_result,
                work_performed=it.work_performed,
                cost=float(it.cost or 0.0),
                status=it.status,
                asset=asset_out,
                returned_at=it.returned_at,
                installed_at=it.installed_at
            ))

        result.append(RepairBatchResponse(
            id=b.id,
            act_number=b.act_number,
            vendor_name=b.vendor_name,
            branch_id=b.branch_id,
            branch_name=b.branch.name if b.branch else None,
            status=b.status,
            created_at=b.created_at,
            closed_at=b.closed_at,
            notes=b.notes,
            items_count=len(b.items),
            items=items_out
        ))
    return result


@router.get("/{batch_id}", response_model=RepairBatchResponse)
def get_repair_batch_detail(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Детальная информация об акте передачи техники в СЦ."""
    batch = db.query(RepairBatch).options(
        joinedload(RepairBatch.branch),
        joinedload(RepairBatch.items).joinedload(RepairBatchItem.asset)
    ).filter(RepairBatch.id == batch_id).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Акт передачи не найден")

    items_out = []
    for it in batch.items:
        asset_out = None
        if it.asset:
            asset_out = EquipmentResponse(
                id=it.asset.id,
                inventory_number=it.asset.inventory_number,
                serial_number=it.asset.serial_number,
                name=it.asset.name,
                asset_type=it.asset.asset_type,
                status=it.asset.status,
                condition=it.asset.condition,
                cabinet=it.asset.cabinet,
                branch_id=it.asset.branch_id,
                branch_name=it.asset.branch.name if it.asset.branch else None,
                hostname=it.asset.hostname,
                os_name=it.asset.os_name,
                notes=it.asset.notes,
                updated_at=it.asset.updated_at
            )
        items_out.append(RepairBatchItemResponse(
            id=it.id,
            batch_id=it.batch_id,
            asset_id=it.asset_id,
            reported_issue=it.reported_issue,
            diagnostic_result=it.diagnostic_result,
            work_performed=it.work_performed,
            cost=float(it.cost or 0.0),
            status=it.status,
            asset=asset_out,
            returned_at=it.returned_at,
            installed_at=it.installed_at
        ))

    return RepairBatchResponse(
        id=batch.id,
        act_number=batch.act_number,
        vendor_name=batch.vendor_name,
        branch_id=batch.branch_id,
        branch_name=batch.branch.name if batch.branch else None,
        status=batch.status,
        created_at=batch.created_at,
        closed_at=batch.closed_at,
        notes=batch.notes,
        items_count=len(batch.items),
        items=items_out
    )


@router.post("", response_model=RepairBatchResponse)
def create_repair_batch(
    payload: RepairBatchCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    ЭТАП 2: Формирование акта и отправка партии техники в сервисный центр.
    - Генерирует уникальный номер акта АКТ-РЕМ-YYYY-XXXX.
    - Переводит выбранную технику в статус AT_SC (В сервисном центре).
    - Записывает операцию в историю каждого устройства.
    """
    if not payload.asset_ids:
        raise HTTPException(status_code=400, detail="Необходимо выбрать хотя бы одну единицу техники для отправки в СЦ")

    # Проверяем технику
    assets = db.query(Asset).filter(Asset.id.in_(payload.asset_ids)).all()
    if not assets:
        raise HTTPException(status_code=400, detail="Выбранная техника не найдена в системе")

    act_number = EquipmentService.generate_act_number(db)
    now = datetime.utcnow()
    branch_id = payload.branch_id or current_user.branch_id

    batch = RepairBatch(
        act_number=act_number,
        vendor_name=payload.vendor_name.strip(),
        branch_id=branch_id,
        status="open",
        created_at=now,
        notes=payload.notes
    )
    db.add(batch)
    db.flush()

    issues_map = payload.issues_map or {}
    items_out = []

    for a in assets:
        issue = issues_map.get(a.id) or "Диагностика и ремонт"
        item = RepairBatchItem(
            batch_id=batch.id,
            asset_id=a.id,
            reported_issue=issue,
            status="in_repair",
            cost=0.0
        )
        db.add(item)

        # Переводим статус оборудования
        a.status = AssetStatus.AT_SC
        a.condition = AssetCondition.BROKEN
        a.updated_at = now

        EquipmentService.log_history(
            db=db,
            asset_id=a.id,
            action="Передача в сервисный центр",
            user_name=current_user.full_name,
            details=f"Передано в СЦ '{payload.vendor_name}' по акту {act_number}. Неисправность: {issue}."
        )

    db.commit()
    db.refresh(batch)

    return get_repair_batch_detail(batch_id=batch.id, db=db, current_user=current_user)


@router.post("/{batch_id}/close")
def close_repair_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """Закрыть акт передачи в СЦ (все позиции приняты обратно)."""
    batch = db.query(RepairBatch).filter(RepairBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Акт не найден")

    batch.status = "closed"
    batch.closed_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": f"Акт {batch.act_number} успешно закрыт"}
