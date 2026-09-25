from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import (
    Asset,
    Zone,
    Floor,
    AppUser,
    AssetStatus,
    AssetType,
    AssetCondition,
    SwitchPort,
    NetworkSwitch
)
from SHARED.auth_service import get_current_user, require_role
from LOCATION.app.schemas import (
    PlacedAssetResponse,
    AssetPositionUpdate,
    AssetCreateAndPlace,
    AssignCabinetRequest
)

router = APIRouter(prefix="/api/v1/location", tags=["Location Assets Placement"])


def enrich_assets_with_network_and_locations(db: Session, assets: List[Asset]) -> List[PlacedAssetResponse]:
    """Пакетное обогащение активов данными о портах коммутаторов L2, роуминге и комнатах."""
    if not assets:
        return []

    asset_ids = [a.id for a in assets]
    mac_map = {a.mac_address.lower().strip(): a.id for a in assets if a.mac_address}

    ports = db.query(SwitchPort).options(
        joinedload(SwitchPort.switch).joinedload(NetworkSwitch.asset),
        joinedload(SwitchPort.zone)
    ).filter(
        (SwitchPort.connected_asset_id.in_(asset_ids)) |
        (SwitchPort.last_mac.in_(list(mac_map.keys())) if mac_map else False)
    ).all()

    port_for_asset: Dict[int, SwitchPort] = {}
    for p in ports:
        target_aid = p.connected_asset_id
        if not target_aid and p.last_mac:
            target_aid = mac_map.get(p.last_mac.lower().strip())
        if target_aid and target_aid not in port_for_asset:
            port_for_asset[target_aid] = p

    floor_ids = {a.floor_id for a in assets if a.floor_id}
    zone_ids = {a.zone_id for a in assets if a.zone_id}
    floors_dict = {f.id: f.name for f in db.query(Floor).filter(Floor.id.in_(floor_ids)).all()} if floor_ids else {}
    zones_dict = {z.id: z.name for z in db.query(Zone).filter(Zone.id.in_(zone_ids)).all()} if zone_ids else {}

    result = []
    for a in assets:
        p = port_for_asset.get(a.id)
        sw_name = None
        sw_ip = None
        port_num = None
        socket_label = None
        conn_cabinet = None
        net_status = "disconnected"

        if p:
            if p.switch:
                sw_name = p.switch.asset.name if p.switch.asset else (p.switch.model or "Коммутатор")
                sw_ip = p.switch.ip_address
            port_num = p.port_number
            socket_label = p.socket_label
            conn_cabinet = p.cabinet or (p.zone.name if p.zone else None)

            if p.status == "up":
                if conn_cabinet and a.cabinet and conn_cabinet.strip().lower() != a.cabinet.strip().lower():
                    net_status = "roaming"
                else:
                    net_status = "online"
            else:
                net_status = "offline"

        result.append(PlacedAssetResponse(
            id=a.id,
            inventory_number=a.inventory_number,
            name=a.name,
            asset_type=a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
            condition=a.condition.value if hasattr(a.condition, "value") else str(a.condition),
            coords_x=a.coords_x,
            coords_y=a.coords_y,
            zone_id=a.zone_id,
            floor_id=a.floor_id,
            floor_name=floors_dict.get(a.floor_id),
            zone_name=zones_dict.get(a.zone_id),
            cabinet=a.cabinet,
            current_user_name=a.responsible_ad_user.display_name if a.responsible_ad_user else None,
            hostname=a.hostname,
            ip_address=a.ip_address,
            mac_address=a.mac_address,
            connected_switch_name=sw_name,
            connected_switch_ip=sw_ip,
            connected_port_number=port_num,
            connected_socket_label=socket_label,
            connected_cabinet=conn_cabinet,
            network_location_status=net_status
        ))
    return result


@router.get("/floors/{floor_id}/assets", response_model=List[PlacedAssetResponse])
def get_floor_placed_assets(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Список оборудования, размещенного на указанном поэтажном плане."""
    assets = db.query(Asset).options(
        joinedload(Asset.responsible_ad_user)
    ).filter(
        Asset.floor_id == floor_id,
        Asset.coords_x != None,
        Asset.coords_y != None
    ).all()

    return enrich_assets_with_network_and_locations(db, assets)


@router.get("/placed-assets", response_model=List[PlacedAssetResponse])
def get_all_placed_assets(
    branch_id: Optional[int] = Query(None),
    floor_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Список всех размещенных на карте объектов для филиала/этажа с информацией о подключении к сети L2."""
    query = db.query(Asset).options(
        joinedload(Asset.responsible_ad_user)
    ).filter(
        Asset.coords_x != None,
        Asset.coords_y != None
    )

    if current_user.role != "superadmin" and current_user.branch_id:
        query = query.filter(Asset.branch_id == current_user.branch_id)
    elif branch_id:
        query = query.filter(Asset.branch_id == branch_id)

    if floor_id:
        query = query.filter(Asset.floor_id == floor_id)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (Asset.name.ilike(s)) |
            (Asset.inventory_number.ilike(s)) |
            (Asset.cabinet.ilike(s)) |
            (Asset.hostname.ilike(s)) |
            (Asset.ip_address.ilike(s)) |
            (Asset.mac_address.ilike(s))
        )

    assets = query.all()
    return enrich_assets_with_network_and_locations(db, assets)


@router.get("/unplaced-assets", response_model=List[PlacedAssetResponse])
def get_unplaced_assets_pool(
    branch_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """
    Пул неразмещенных активов (компьютеры из AD, принтеры, коммутаторы),
    доступных для перемещения в кабинет или на холст.
    """
    query = db.query(Asset).options(
        joinedload(Asset.responsible_ad_user)
    ).filter(
        (Asset.coords_x == None) | (Asset.coords_y == None)
    )

    if current_user.role != "superadmin" and current_user.branch_id:
        query = query.filter(Asset.branch_id == current_user.branch_id)
    elif branch_id:
        query = query.filter(Asset.branch_id == branch_id)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (Asset.name.ilike(s)) |
            (Asset.inventory_number.ilike(s)) |
            (Asset.cabinet.ilike(s)) |
            (Asset.hostname.ilike(s)) |
            (Asset.ip_address.ilike(s)) |
            (Asset.mac_address.ilike(s))
        )

    assets = query.limit(200).all()
    return enrich_assets_with_network_and_locations(db, assets)


@router.post("/assets/{asset_id}/position", response_model=PlacedAssetResponse)
def update_asset_position(
    asset_id: int,
    payload: AssetPositionUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Обновление нормализованных координат (0.0-1.0) и привязки актива к комнате/этажу."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    asset.coords_x = max(0.0, min(1.0, payload.coords_x))
    asset.coords_y = max(0.0, min(1.0, payload.coords_y))
    if payload.floor_id:
        asset.floor_id = payload.floor_id
    if payload.zone_id:
        asset.zone_id = payload.zone_id
        zone = db.query(Zone).filter(Zone.id == payload.zone_id).first()
        if zone and zone.room_number:
            asset.cabinet = f"Кабинет {zone.room_number}"

    db.commit()
    db.refresh(asset)
    return enrich_assets_with_network_and_locations(db, [asset])[0]


@router.post("/assets/{asset_id}/assign-cabinet", response_model=PlacedAssetResponse)
def assign_cabinet_and_place(
    asset_id: int,
    payload: AssignCabinetRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """Назначение кабинета и автоматическое позиционирование актива в зоне кабинета."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    if payload.cabinet:
        asset.cabinet = payload.cabinet.strip()

    target_zone = None
    if payload.zone_id:
        target_zone = db.query(Zone).filter(Zone.id == payload.zone_id).first()
    elif payload.floor_id and payload.cabinet:
        cab_clean = payload.cabinet.replace("Кабинет", "").strip()
        target_zone = db.query(Zone).filter(
            Zone.floor_id == payload.floor_id,
            (Zone.name.ilike(f"%{cab_clean}%")) | (Zone.room_number == cab_clean)
        ).first()

    if target_zone:
        asset.zone_id = target_zone.id
        asset.floor_id = target_zone.floor_id
        if target_zone.polygon_coords and len(target_zone.polygon_coords) >= 3:
            pts = target_zone.polygon_coords
            cx = sum(p.get("x", 0.5) for p in pts) / len(pts)
            cy = sum(p.get("y", 0.5) for p in pts) / len(pts)
            asset.coords_x = round(cx, 4)
            asset.coords_y = round(cy, 4)
        else:
            asset.coords_x = payload.coords_x if payload.coords_x is not None else 0.5
            asset.coords_y = payload.coords_y if payload.coords_y is not None else 0.5
    else:
        if payload.floor_id:
            asset.floor_id = payload.floor_id
            if asset.coords_x is None or asset.coords_y is None:
                asset.coords_x = payload.coords_x if payload.coords_x is not None else 0.5
                asset.coords_y = payload.coords_y if payload.coords_y is not None else 0.5

    db.commit()
    db.refresh(asset)
    return enrich_assets_with_network_and_locations(db, [asset])[0]


@router.post("/assets/{asset_id}/unplace", response_model=PlacedAssetResponse)
def unplace_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Снять актив с поэтажного плана (переместить в неразмещенные)."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Актив не найден")

    asset.coords_x = None
    asset.coords_y = None
    asset.floor_id = None
    asset.zone_id = None
    db.commit()
    db.refresh(asset)
    return enrich_assets_with_network_and_locations(db, [asset])[0]

@router.post("/assets/create-and-place", response_model=PlacedAssetResponse)
def create_and_place_asset(
    payload: AssetCreateAndPlace,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician", "operator"]))
):
    """
    Создание нового актива напрямую на интерактивной карте
    (синхронизируется с реестром техники и ремонтом).
    """
    inv = payload.inventory_number.strip()
    existing = db.query(Asset).filter(Asset.inventory_number == inv).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Оборудование с инвентарным номером '{inv}' уже существует")

    floor = db.query(Floor).filter(Floor.id == payload.floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    branch_id = payload.branch_id or floor.branch_id

    try:
        atype = AssetType(payload.asset_type)
    except Exception:
        atype = AssetType.OTHER

    try:
        acond = AssetCondition(payload.condition)
    except Exception:
        acond = AssetCondition.WORKING

    asset = Asset(
        inventory_number=inv,
        name=payload.name.strip(),
        asset_type=atype,
        serial_number=payload.serial_number.strip() if payload.serial_number else None,
        condition=acond,
        status=AssetStatus.AT_WORKPLACE,
        floor_id=floor.id,
        branch_id=branch_id,
        cabinet=payload.cabinet.strip() if payload.cabinet else None,
        coords_x=max(0.0, min(1.0, payload.coords_x)),
        coords_y=max(0.0, min(1.0, payload.coords_y)),
        zone_id=payload.zone_id,
        notes=payload.notes
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return PlacedAssetResponse(
        id=asset.id,
        inventory_number=asset.inventory_number,
        name=asset.name,
        asset_type=asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type),
        status=asset.status.value if hasattr(asset.status, "value") else str(asset.status),
        condition=asset.condition.value if hasattr(asset.condition, "value") else str(asset.condition),
        coords_x=asset.coords_x,
        coords_y=asset.coords_y,
        zone_id=asset.zone_id,
        floor_id=asset.floor_id,
        cabinet=asset.cabinet,
        hostname=asset.hostname,
        ip_address=asset.ip_address,
        mac_address=asset.mac_address
    )
