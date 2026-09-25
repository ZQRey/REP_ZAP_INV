from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import Floor, Zone, Asset, NetworkSwitch, AppUser
from SHARED.auth_service import get_current_user
from LOCATION.app.schemas import CableTraceResponse
from LOCATION.app.services.pathfinding_service import PathfindingService

router = APIRouter(prefix="/api/v1/location", tags=["Location Pathfinding & Stats"])


@router.get("/network/trace", response_model=CableTraceResponse)
def trace_cable_path(
    from_switch: int = Query(...),
    to_asset: int = Query(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """
    Трассировка кабельного соединения между коммутатором и конечным устройством.
    Возвращает список опорных точек полилинии для анимации бегущего импульса на холсте Konva.js.
    """
    result = PathfindingService.calculate_cable_path(
        db=db,
        from_switch_id=from_switch,
        to_asset_id=to_asset
    )
    return CableTraceResponse(
        found=result["found"],
        path_points=result["path_points"],
        distance_meters=result["distance_meters"],
        message=result["message"]
    )


@router.get("/stats")
def get_location_stats(
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Сводная статистика интерактивной карты филиала."""
    floors_q = db.query(Floor)
    if branch_id:
        floors_q = floors_q.filter(Floor.branch_id == branch_id)
    floors_count = floors_q.count()

    zones_count = db.query(Zone).count()
    placed_assets = db.query(Asset).filter(Asset.coords_x != None, Asset.coords_y != None).count()
    switches_count = db.query(NetworkSwitch).count()

    return {
        "floors": floors_count,
        "zones": zones_count,
        "assets_placed": placed_assets,
        "switches": switches_count
    }
