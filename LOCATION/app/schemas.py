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


class FloorUpdate(BaseModel):
    name: Optional[str] = None
    floor_number: Optional[int] = None
    scale_pixels_per_meter: Optional[float] = None
    map_image_url: Optional[str] = None


class FloorResponse(FloorBase):
    id: int
    created_at: Optional[datetime] = None
    zones: List[ZoneResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AssetCreateAndPlace(BaseModel):
    inventory_number: str
    name: str
    asset_type: str = "workstation"
    serial_number: Optional[str] = None
    condition: str = "working"
    floor_id: int
    branch_id: Optional[int] = None
    cabinet: Optional[str] = None
    coords_x: float = 0.5
    coords_y: float = 0.5
    zone_id: Optional[int] = None
    notes: Optional[str] = None


# --- Позиционирование активов на карте ---
class AssetPositionUpdate(BaseModel):
    coords_x: float  # 0.0 - 1.0
    coords_y: float
    zone_id: Optional[int] = None
    floor_id: Optional[int] = None


class AssignCabinetRequest(BaseModel):
    cabinet: str
    floor_id: Optional[int] = None
    zone_id: Optional[int] = None
    coords_x: Optional[float] = None
    coords_y: Optional[float] = None


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
    floor_name: Optional[str] = None
    zone_name: Optional[str] = None
    cabinet: Optional[str] = None
    current_user_name: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    # Данные L2/L3 сетевого коммутатора
    connected_switch_name: Optional[str] = None
    connected_switch_ip: Optional[str] = None
    connected_port_number: Optional[int] = None
    connected_socket_label: Optional[str] = None
    connected_cabinet: Optional[str] = None
    network_location_status: Optional[str] = None  # "online", "roaming", "offline", "disconnected"

    model_config = ConfigDict(from_attributes=True)


# --- Коммутаторы и порты ---
class SwitchPortResponse(BaseModel):
    id: int
    switch_id: int
    port_number: int
    port_speed: str
    vlan_id: int
    status: str  # up, down, disabled
    cabinet: Optional[str] = None
    socket_label: Optional[str] = None
    zone_id: Optional[int] = None
    last_mac: Optional[str] = None
    last_ip: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    connected_asset_id: Optional[int] = None
    connected_asset_name: Optional[str] = None
    connected_asset_inv: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SwitchPortUpdate(BaseModel):
    cabinet: Optional[str] = None
    socket_label: Optional[str] = None
    zone_id: Optional[int] = None
    vlan_id: Optional[int] = None
    status: Optional[str] = None
    connected_asset_id: Optional[int] = None


class NetworkSwitchResponse(BaseModel):
    id: int
    asset_id: int
    ip_address: str
    management_type: str = "snmp"
    mgmt_port: int = 161
    username: Optional[str] = None
    snmp_community: str
    model: Optional[str] = None
    total_ports: int
    name: str
    cabinet: Optional[str] = None
    last_poll_status: Optional[str] = "never"
    last_poll_message: Optional[str] = None
    last_polled_at: Optional[datetime] = None
    floor_id: Optional[int] = None
    coords_x: Optional[float] = None
    coords_y: Optional[float] = None
    extra_params: Optional[Dict[str, Any]] = None
    ports: List[SwitchPortResponse] = []

    model_config = ConfigDict(from_attributes=True)


class NetworkSwitchCreate(BaseModel):
    name: str
    inventory_number: Optional[str] = None
    ip_address: str
    floor_id: int
    branch_id: Optional[int] = None
    model: Optional[str] = "24-Port Managed Switch"
    management_type: str = "snmp"  # omada, mikrotik, hp, tplink, snmp, ssh_cli
    mgmt_port: int = 161
    username: Optional[str] = None
    password: Optional[str] = None
    snmp_community: str = "public"
    total_ports: int = 24
    cabinet: Optional[str] = "Серверная"
    coords_x: float = 0.5
    coords_y: float = 0.5
    extra_params: Optional[Dict[str, Any]] = None


class NetworkSwitchUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    model: Optional[str] = None
    management_type: Optional[str] = None
    mgmt_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    snmp_community: Optional[str] = None
    total_ports: Optional[int] = None
    cabinet: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None


class SwitchSimulateRequest(BaseModel):
    port_number: int
    mac_address: str
    target_cabinet: Optional[str] = None


class SwitchConnectionTestRequest(BaseModel):
    ip_address: str
    management_type: str = "snmp"
    mgmt_port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    snmp_community: Optional[str] = "public"
    extra_params: Optional[Dict[str, Any]] = None


class SwitchConnectionTestResponse(BaseModel):
    success: bool
    reachable: bool
    status: str = "ok"
    latency_ms: Optional[float] = None
    message: str


# --- Трассировка кабелей (A* Pathfinding) ---
class CableTraceRequest(BaseModel):
    from_switch_id: int
    to_asset_id: int


class CableTraceResponse(BaseModel):
    found: bool
    path_points: List[Dict[str, float]] = []  # [{x, y}, {x, y}, ...]
    distance_meters: float = 0.0
    message: str = ""
