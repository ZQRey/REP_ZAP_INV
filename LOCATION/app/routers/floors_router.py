from SHARED.authentication import require_authenticated_user
from SHARED.security_config import DEMO_ENABLED
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import Floor, Zone, Branch, AppUser, Asset
from LOCATION.app.schemas import FloorResponse, FloorCreate, FloorUpdate

router = APIRouter(prefix="/api/v1/location", tags=["Location Floors"])


@router.get("/floors/{floor_id}/map")
def get_floor_map(floor_id: int, db: Session = Depends(get_db), current_user: AppUser = Depends(require_authenticated_user)):
    from pathlib import Path
    from urllib.parse import urlparse
    from fastapi.responses import FileResponse

    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if floor is None or not floor.map_image_url:
        raise HTTPException(404, "Floor map not found")
    url = urlparse(floor.map_image_url)
    if url.scheme or url.netloc or not url.path.startswith(("/location/static/maps/", "/static/maps/")):
        raise HTTPException(404, "Only locally uploaded floor maps are available")
    root = (Path(__file__).resolve().parent.parent / "static" / "maps").resolve()
    target = (root / url.path.split("/maps/", 1)[1]).resolve()
    if not target.is_relative_to(root) or not target.name.startswith(f"floor_{floor.id}_") or not target.is_file():
        raise HTTPException(404, "Floor map not found")
    return FileResponse(target, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/branches/{branch_id}/floors", response_model=List[FloorResponse])
def get_branch_floors(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Список этажей выбранного филиала с векторными зонами."""
    floors = db.query(Floor).options(joinedload(Floor.zones)).filter(Floor.branch_id == branch_id).all()
    
    return floors


@router.post("/floors", response_model=FloorResponse)
def create_floor(
    payload: FloorCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Создание нового этажа филиала."""
    floor = Floor(
        branch_id=payload.branch_id if current_user.role == "superadmin" else current_user.branch_id,
        floor_number=payload.floor_number,
        name=payload.name.strip(),
        map_image_url=payload.map_image_url,
        scale_pixels_per_meter=payload.scale_pixels_per_meter
    )
    db.add(floor)
    db.commit()
    db.refresh(floor)
    return floor


@router.put("/floors/{floor_id}", response_model=FloorResponse)
def update_floor(
    floor_id: int,
    payload: FloorUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Редактирование параметров этажа (название, номер, масштаб, URL карты)."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    if payload.name is not None:
        floor.name = payload.name.strip()
    if payload.floor_number is not None:
        floor.floor_number = payload.floor_number
    if payload.scale_pixels_per_meter is not None:
        floor.scale_pixels_per_meter = payload.scale_pixels_per_meter
    if payload.map_image_url is not None:
        floor.map_image_url = payload.map_image_url

    db.commit()
    db.refresh(floor)
    return floor


@router.delete("/floors/{floor_id}")
def delete_floor(
    floor_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Удаление этажа и отвязка размещенных на нем активов."""
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    # Отвязываем размещенные активы
    db.query(Asset).filter(Asset.floor_id == floor_id).update({
        "floor_id": None,
        "zone_id": None,
        "coords_x": None,
        "coords_y": None
    })

    # Удаляем зоны этажа
    db.query(Zone).filter(Zone.floor_id == floor_id).delete()

    db.delete(floor)
    db.commit()
    return {"success": True, "message": f"Этаж '{floor.name}' успешно удален"}


@router.post("/floors/{floor_id}/upload-map")
async def upload_floor_map(
    floor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_authenticated_user)
):
    """Загрузка фонового изображения карты этажа (PNG, JPG, SVG, WebP)."""
    import time
    from pathlib import Path
    
    floor = db.query(Floor).filter(Floor.id == floor_id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    maps_dir = Path(__file__).resolve().parent.parent / "static" / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".svg", ".webp"]:
        ext = ".png"

    filename = f"floor_{floor_id}_{int(time.time())}{ext}"
    target_path = maps_dir / filename

    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    map_url = f"/location/static/maps/{filename}"
    floor.map_image_url = map_url
    db.commit()

    return {
        "success": True,
        "map_image_url": map_url,
        "message": "План этажа успешно загружен и сохранен."
    }

