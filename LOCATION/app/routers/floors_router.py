from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from SHARED.database import get_db
from SHARED.models import Floor, Zone, Branch, AppUser
from SHARED.auth_service import get_current_user, require_role
from LOCATION.app.schemas import FloorResponse, FloorCreate

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
