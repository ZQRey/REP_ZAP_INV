from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import Floor, Zone, Branch, AppUser, Asset
from SHARED.auth_service import get_current_user, require_role
from LOCATION.app.schemas import FloorResponse, FloorCreate, FloorUpdate

router = APIRouter(prefix="/api/v1/location", tags=["Location Floors"])


@router.get("/branches/{branch_id}/floors", response_model=List[FloorResponse])
def get_branch_floors(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Список этажей выбранного филиала с векторными зонами."""
    floors = db.query(Floor).options(joinedload(Floor.zones)).filter(Floor.branch_id == branch_id).all()
    
    # Если этажей еще нет, создадим дефолтный 1-й этаж
    if not floors:
        default_floor = Floor(
            branch_id=branch_id,
            floor_number=1,
            name="1-й Этаж (Главный корпус)",
            map_image_url=None,
            scale_pixels_per_meter=20.0
        )
        db.add(default_floor)
        db.flush()

        # Создаем базовые демонстрационные зоны (Кабинеты и Коридор)
        demo_zones = [
            Zone(
                floor_id=default_floor.id,
                name="Коридор Центральный",
                zone_type="corridor",
                polygon_coords=[
                    {"x": 0.05, "y": 0.40},
                    {"x": 0.95, "y": 0.40},
                    {"x": 0.95, "y": 0.60},
                    {"x": 0.05, "y": 0.60}
                ],
                fill_color="rgba(148, 163, 184, 0.15)",
                border_color="#64748b"
            ),
            Zone(
                floor_id=default_floor.id,
                name="Кабинет IT № 108",
                zone_type="server_room",
                room_number="108",
                responsible_person="Администратор IT",
                polygon_coords=[
                    {"x": 0.05, "y": 0.08},
                    {"x": 0.35, "y": 0.08},
                    {"x": 0.35, "y": 0.38},
                    {"x": 0.05, "y": 0.38}
                ],
                fill_color="rgba(99, 102, 241, 0.20)",
                border_color="#4f46e5"
            ),
            Zone(
                floor_id=default_floor.id,
                name="Бухгалтерия (Каб. 201)",
                zone_type="office",
                room_number="201",
                responsible_person="Главный бухгалтер",
                polygon_coords=[
                    {"x": 0.40, "y": 0.08},
                    {"x": 0.70, "y": 0.08},
                    {"x": 0.70, "y": 0.38},
                    {"x": 0.40, "y": 0.38}
                ],
                fill_color="rgba(59, 130, 246, 0.15)",
                border_color="#2563eb"
            ),
            Zone(
                floor_id=default_floor.id,
                name="Дирекция (Каб. 301)",
                zone_type="office",
                room_number="301",
                responsible_person="Генеральный директор",
                polygon_coords=[
                    {"x": 0.05, "y": 0.62},
                    {"x": 0.45, "y": 0.62},
                    {"x": 0.45, "y": 0.92},
                    {"x": 0.05, "y": 0.92}
                ],
                fill_color="rgba(16, 185, 129, 0.15)",
                border_color="#059669"
            ),
            Zone(
                floor_id=default_floor.id,
                name="Склад IT и Расходников",
                zone_type="warehouse",
                room_number="Склад-1",
                polygon_coords=[
                    {"x": 0.50, "y": 0.62},
                    {"x": 0.95, "y": 0.62},
                    {"x": 0.95, "y": 0.92},
                    {"x": 0.50, "y": 0.92}
                ],
                fill_color="rgba(245, 158, 11, 0.15)",
                border_color="#d97706"
            )
        ]
        db.add_all(demo_zones)
        db.commit()
        db.refresh(default_floor)
        floors = [default_floor]

    return floors


@router.post("/floors", response_model=FloorResponse)
def create_floor(
    payload: FloorCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin"]))
):
    """Создание нового этажа филиала."""
    floor = Floor(
        branch_id=payload.branch_id,
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
    current_user: AppUser = Depends(require_role(["superadmin", "admin"]))
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
    current_user: AppUser = Depends(require_role(["superadmin", "admin"]))
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
    current_user: AppUser = Depends(require_role(["superadmin", "admin"]))
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
