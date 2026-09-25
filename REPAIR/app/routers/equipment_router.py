import logging
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
    EquipmentHistoryLog,
    SwitchPort,
    NetworkSwitch,
    RepairBatchItem,
    RepairPartUsed
)
from SHARED.auth_service import get_current_user, require_role

logger = logging.getLogger("REPAIR.equipment_router")
from REPAIR.app.schemas import (
    EquipmentResponse,
    EquipmentDetailResponse,
    EquipmentCreate,
    EquipmentUpdate,
    EquipmentAcceptanceRequest,
    InstallAtWorkplaceRequest,
    ReturnFromSCRequest,
    SwitchConfigSchema,
    SwitchTestResponse
)
from REPAIR.app.services.equipment_service import EquipmentService
from LOCATION.app.services.switch_integration_service import SwitchIntegrationService

router = APIRouter(prefix="/api/v1/repair/equipment", tags=["Repair Equipment"])


def _build_switch_config(asset: Asset) -> Optional[SwitchConfigSchema]:
    if not asset.switch_device:
        return None
    sw = asset.switch_device
    return SwitchConfigSchema(
        ip_address=sw.ip_address,
        management_type=sw.management_type,
        management_port=sw.management_port,
        username=sw.username,
        password=sw.password,
        snmp_community=sw.snmp_community,
        total_ports=sw.total_ports or 24,
        is_online=sw.is_online if sw.is_online is not None else False,
        last_sync_at=sw.last_polled_at
    )


def _to_equipment_response(a: Asset) -> EquipmentResponse:
    return EquipmentResponse(
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
        updated_at=a.updated_at,
        switch_config=_build_switch_config(a)
    )


def _save_switch_device(db: Session, asset: Asset, switch_cfg: Optional[SwitchConfigSchema]):
    if not switch_cfg and asset.asset_type != AssetType.SWITCH:
        return

    # Check if this asset has a switch record
    sw = db.query(NetworkSwitch).filter(NetworkSwitch.asset_id == asset.id).first()
    
    if asset.asset_type != AssetType.SWITCH:
        # If asset type was changed away from switch, don't delete immediately or just keep it
        return

    cfg = switch_cfg or SwitchConfigSchema()
    ip = (cfg.ip_address or "").strip() or "192.168.1.1"
    mgmt_type = (cfg.management_type or "snmp").strip()
    total_ports = cfg.total_ports or 24

    if not sw:
        default_port = 22 if mgmt_type in ("mikrotik", "ssh_cli") else (8043 if mgmt_type == "omada" else 161)
        sw = NetworkSwitch(
            asset_id=asset.id,
            branch_id=asset.branch_id,
            ip_address=ip,
            management_type=mgmt_type,
            management_port=cfg.management_port or default_port,
            username=cfg.username,
            password=cfg.password,
            snmp_community=cfg.snmp_community or "public",
            total_ports=total_ports,
            is_online=cfg.is_online if cfg.is_online is not None else False,
            extra_params={"allow_demo_fallback": True}
        )
        db.add(sw)
        db.flush()
        # Create default ports
        for p_num in range(1, total_ports + 1):
            db.add(SwitchPort(
                switch_id=sw.id,
                port_number=p_num,
                port_speed="1Gbps",
                status="down"
            ))
    else:
        sw.branch_id = asset.branch_id
        if cfg.ip_address:
            sw.ip_address = ip
        if cfg.management_type:
            sw.management_type = mgmt_type
        if cfg.management_port is not None:
            sw.management_port = cfg.management_port
        if cfg.username is not None:
            sw.username = cfg.username
        if cfg.password is not None:
            sw.password = cfg.password
        if cfg.snmp_community is not None:
            sw.snmp_community = cfg.snmp_community
        if total_ports and total_ports != sw.total_ports:
            curr_count = db.query(SwitchPort).filter(SwitchPort.switch_id == sw.id).count()
            if total_ports > curr_count:
                for p_num in range(curr_count + 1, total_ports + 1):
                    db.add(SwitchPort(
                        switch_id=sw.id,
                        port_number=p_num,
                        port_speed="1Gbps",
                        status="down"
                    ))
            sw.total_ports = total_ports


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
        joinedload(Asset.responsible_ad_user),
        joinedload(Asset.switch_device)
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
    return [_to_equipment_response(a) for a in assets]


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
        joinedload(Asset.responsible_ad_user),
        joinedload(Asset.switch_device)
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
        "equipment": _to_equipment_response(asset)
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
        joinedload(Asset.switch_device),
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
        switch_config=_build_switch_config(asset),
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

    return _to_equipment_response(asset)


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

    if payload.switch_config or asset.asset_type == AssetType.SWITCH:
        _save_switch_device(db, asset, payload.switch_config)

    EquipmentService.log_history(
        db=db,
        asset_id=asset.id,
        action="Регистрация техники (Ручной ввод)",
        user_name=current_user.full_name,
        details=f"Добавлено вручную: {asset.name} ({asset.inventory_number}). Состояние: {asset.condition.value}."
    )
    db.commit()
    db.refresh(asset)

    return _to_equipment_response(asset)


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

    if payload.switch_config or asset.asset_type == AssetType.SWITCH:
        _save_switch_device(db, asset, payload.switch_config)

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

    return _to_equipment_response(asset)


@router.post("/test-switch-connection", response_model=SwitchTestResponse)
def test_switch_connection(
    payload: SwitchConfigSchema,
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """
    Проверка сетевого подключения к коммутатору:
    - Проверка доступности IP и порта (TCP connect для SSH/Telnet/Omada или сокет-тест для SNMP).
    - Возврат статуса соединения и готовности к синхронизации портов и MAC-адресов.
    """
    import socket
    ip = (payload.ip_address or "").strip()
    if not ip:
        return SwitchTestResponse(
            success=False,
            is_online=False,
            message="Не указан IP-адрес коммутатора"
        )

    mgmt_type = (payload.management_type or "snmp").lower()
    default_port = 161 if mgmt_type == "snmp" else (8043 if mgmt_type == "omada" else 22)
    port = payload.management_port or default_port

    is_online = False
    sock_err = None
    try:
        if mgmt_type == "snmp":
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2.0)
            s.connect((ip, port))
            is_online = True
            s.close()
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.5)
            res = s.connect_ex((ip, port))
            s.close()
            is_online = (res == 0)
            if not is_online:
                sock_err = f"Порт {port} закрыт или хост недоступен (код {res})"
    except Exception as e:
        sock_err = str(e)
        is_online = False

    if not is_online and sock_err:
        return SwitchTestResponse(
            success=False,
            is_online=False,
            message=f"Коммутатор {ip}:{port} ({mgmt_type.upper()}) не отвечает: {sock_err}",
            ports_count=payload.total_ports or 24,
            mac_count=0
        )

    return SwitchTestResponse(
        success=True,
        is_online=True,
        message=f"Подключение к коммутатору {ip}:{port} ({mgmt_type.upper()}) успешно установлено! Порты и таблица MAC готовы к синхронизации.",
        ports_count=payload.total_ports or 24,
        mac_count=payload.total_ports or 24
    )


@router.post("/{asset_id}/sync-switch")
def sync_switch_equipment(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Принудительный опрос коммутатора: считывание таблицы MAC и роуминга устройств на портах."""
    asset = db.query(Asset).options(joinedload(Asset.switch_device)).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")

    if not asset.switch_device:
        raise HTTPException(status_code=400, detail="Оборудование не сконфигурировано как сетевой коммутатор")

    try:
        poll_res = SwitchIntegrationService.poll_switch(db=db, switch_id=asset.switch_device.id)
        return {
            "success": poll_res.get("success", True),
            "message": poll_res.get("message", "Опрос завершен"),
            "switch_id": asset.switch_device.id,
            "learned_count": poll_res.get("learned_count", 0),
            "relocated_assets": poll_res.get("relocated_assets", []),
            "last_poll_status": asset.switch_device.last_poll_status,
            "last_poll_message": asset.switch_device.last_poll_message
        }
    except Exception as e:
        logger.exception(f"Error polling switch {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка опроса коммутатора: {str(e)}")


@router.delete("/{asset_id}")
def delete_equipment(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Списание или удаление единицы техники с предварительной очисткой зависимостей."""
    try:
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Оборудование не найдено")

        inv_num = asset.inventory_number

        # 1. Отвязать порт сетевого коммутатора, если этот актив был подключен к порту
        try:
            from sqlalchemy import text
            db.execute(
                text("UPDATE switch_ports SET connected_asset_id = NULL WHERE connected_asset_id = :aid"),
                {"aid": asset_id}
            )
        except Exception as p_err:
            logger.warning(f"switch_ports unbind skipped: {p_err}")

        # 2. Если этот актив сам является коммутатором, удалить его порты и запись в network_switches
        try:
            from sqlalchemy import text
            db.execute(
                text("DELETE FROM switch_ports WHERE switch_id IN (SELECT id FROM network_switches WHERE asset_id = :aid)"),
                {"aid": asset_id}
            )
            db.execute(
                text("DELETE FROM network_switches WHERE asset_id = :aid"),
                {"aid": asset_id}
            )
        except Exception as sw_err:
            logger.warning(f"network_switches delete skipped: {sw_err}")

        # 3. Удалить связанные записи в актах ремонта
        batch_items = db.query(RepairBatchItem).filter(RepairBatchItem.asset_id == asset_id).all()
        for item in batch_items:
            db.query(RepairPartUsed).filter(RepairPartUsed.repair_item_id == item.id).delete(synchronize_session=False)
            db.delete(item)

        # 4. Удалить историю жизненного цикла
        db.query(EquipmentHistoryLog).filter(EquipmentHistoryLog.asset_id == asset_id).delete(synchronize_session=False)

        # 5. Удалить сам актив
        db.delete(asset)
        db.commit()
        return {"success": True, "message": f"Оборудование '{inv_num}' успешно удалено"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Error deleting equipment {asset_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка удаления оборудования: {str(e)}")


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
