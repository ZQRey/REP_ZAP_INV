from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import Asset, Zone, Floor, AppUser, AssetStatus
from SHARED.auth_service import get_current_user, require_role
from LOCATION.app.schemas import PlacedAssetResponse, AssetPositionUpdate

router = APIRouter(prefix="/api/v1/location", tags=["Location Assets Placement"])


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

    result = []
    for a in assets:
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
            cabinet=a.cabinet,
            current_user_name=a.responsible_ad_user.display_name if a.responsible_ad_user else None,
            hostname=a.hostname,
            ip_address=a.ip_address,
            mac_address=a.mac_address
        ))
    return result


@router.get("/unplaced-assets", response_model=List[PlacedAssetResponse])
def get_unplaced_assets_pool(
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """
    Пул неразмещенных активов (компьютеры из AD, принтеры, коммутаторы),
    доступных для перетаскивания (Drag & Drop) на интерактивный холст.
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

    assets = query.limit(100).all()

    result = []
    for a in assets:
        result.append(PlacedAssetResponse(
            id=a.id,
            inventory_number=a.inventory_number,
            name=a.name,
            asset_type=a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
            condition=a.condition.value if hasattr(a.condition, "value") else str(a.condition),
            coords_x=None,
            coords_y=None,
            zone_id=None,
            floor_id=None,
            cabinet=a.cabinet,
            current_user_name=a.responsible_ad_user.display_name if a.responsible_ad_user else None,
            hostname=a.hostname,
            ip_address=a.ip_address,
            mac_address=a.mac_address
        ))
    return result


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

    # Координаты должны быть в диапазоне 0.0 - 1.0
    asset.coords_x = max(0.0, min(1.0, payload.coords_x))
    asset.coords_y = max(0.0, min(1.0, payload.coords_y))
    if payload.floor_id:
        asset.floor_id = payload.floor_id
    if payload.zone_id:
        asset.zone_id = payload.zone_id
        # Если привязано к зоне, можно автоматически обновить кабинет
        zone = db.query(Zone).filter(Zone.id == payload.zone_id).first()
        if zone and zone.room_number:
            asset.cabinet = f"Кабинет {zone.room_number}"

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
