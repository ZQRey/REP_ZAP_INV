from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from SHARED.models import AssetType, AssetStatus, AssetCondition


# --- Зоны (Полигоны комнат и коридоров) ---
class ZonePoint(BaseModel):
    x: float  # Нормализованные 0.0 - 1.0
    y: float


class ZoneBase(BaseModel):
    name: str
    zone_type: str = "office"  # office, corridor, server_room, warehouse
    polygon_coords: List[Dict[str, float]] = []
    fill_color: Optional[str] = "rgba(59, 130, 246, 0.15)"
    border_color: Optional[str] = "#3b82f6"
    responsible_person: Optional[str] = None
    room_number: Optional[str] = None


class ZoneCreate(ZoneBase):
    floor_id: int


class ZoneResponse(ZoneBase):
    id: int
    floor_id: int

    model_config = ConfigDict(from_attributes=True)


# --- Поэтажные планы ---
class FloorBase(BaseModel):
    branch_id: int
    floor_number: int = 1
    name: str
    map_image_url: Optional[str] = None
    scale_pixels_per_meter: float = 20.0


class FloorCreate(FloorBase):
    pass


class FloorResponse(FloorBase):
    id: int
    created_at: Optional[datetime] = None
    zones: List[ZoneResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- Позиционирование активов на карте ---
class AssetPositionUpdate(BaseModel):
    coords_x: float  # 0.0 - 1.0
    coords_y: float
    zone_id: Optional[int] = None
    floor_id: Optional[int] = None


class PlacedAssetResponse(BaseModel):
    id: int
    inventory_number: str
    name: str
    asset_type: str
    status: str
    condition: str
    coords_x: Optional[float] = None
    coords_y: Optional[float] = None
    zone_id: Optional[int] = None
    floor_id: Optional[int] = None
    cabinet: Optional[str] = None
    current_user_name: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Коммутаторы и порты ---
class SwitchPortResponse(BaseModel):
    id: int
    switch_id: int
    port_number: int
    port_speed: str
    vlan_id: int
    status: str  # up, down, disabled
    connected_asset_id: Optional[int] = None
    connected_asset_name: Optional[str] = None
    connected_asset_inv: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NetworkSwitchResponse(BaseModel):
    id: int
    asset_id: int
    ip_address: str
    snmp_community: str
    model: Optional[str] = None
    total_ports: int
    name: str
    floor_id: Optional[int] = None
    coords_x: Optional[float] = None
    coords_y: Optional[float] = None
    ports: List[SwitchPortResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- Трассировка кабелей (A* Pathfinding) ---
class CableTraceRequest(BaseModel):
    from_switch_id: int
    to_asset_id: int


class CableTraceResponse(BaseModel):
    found: bool
    path_points: List[Dict[str, float]] = []  # [{x, y}, {x, y}, ...]
    distance_meters: float = 0.0
    message: str = ""
