from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import Zone, Floor, AppUser
from SHARED.auth_service import get_current_user, require_role
from LOCATION.app.schemas import ZoneResponse, ZoneBase

router = APIRouter(prefix="/api/v1/location", tags=["Location Zones"])


@router.post("/floors/{floor_id}/zones", response_model=ZoneResponse)
def save_floor_zone(
    floor_id: int,
    payload: ZoneBase,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Сохранение векторного полигона комнаты или коридора на этаже."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    zone = Zone(
        floor_id=floor_id,
        name=payload.name.strip(),
        zone_type=payload.zone_type,
        polygon_coords=payload.polygon_coords,
        fill_color=payload.fill_color or "rgba(59, 130, 246, 0.15)",
        border_color=payload.border_color or "#3b82f6",
        responsible_person=payload.responsible_person,
        room_number=payload.room_number
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}")
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin"]))
):
    """Удаление полигона зоны."""
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Зона не найдена")

    db.delete(zone)
    db.commit()
    return {"success": True, "message": "Зона удалена"}
