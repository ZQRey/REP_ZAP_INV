from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from SHARED.models import AssetType, AssetStatus, AssetCondition


# --- Модели оборудования (Справочник) ---
class EquipmentModelBase(BaseModel):
    name: str
    category: str = "workstation"
    vendor: Optional[str] = None
    specs_template: Optional[str] = None
    notes: Optional[str] = None


class EquipmentModelCreate(EquipmentModelBase):
    pass


class EquipmentModelUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    specs_template: Optional[str] = None
    notes: Optional[str] = None


class EquipmentModelResponse(EquipmentModelBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Техника и IT-активы (Asset) ---
class EquipmentBase(BaseModel):
    inventory_number: str
    serial_number: Optional[str] = None
    name: str
    asset_type: AssetType = AssetType.WORKSTATION
    condition: AssetCondition = AssetCondition.WORKING
    cabinet: Optional[str] = None
    branch_id: Optional[int] = None
    current_user_id: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class EquipmentCreate(EquipmentBase):
    status: AssetStatus = AssetStatus.AT_WORKPLACE


class EquipmentUpdate(BaseModel):
    inventory_number: Optional[str] = None
    serial_number: Optional[str] = None
    name: Optional[str] = None
    asset_type: Optional[AssetType] = None
    condition: Optional[AssetCondition] = None
    status: Optional[AssetStatus] = None
    cabinet: Optional[str] = None
    branch_id: Optional[int] = None
    current_user_id: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class EquipmentAcceptanceRequest(BaseModel):
    """ЭТАП 1: Приемка неисправной техники в IT-отдел."""
    inventory_number: str
    serial_number: Optional[str] = None
    name: str
    asset_type: AssetType = AssetType.WORKSTATION
    cabinet: str
    branch_id: Optional[int] = None
    current_user_id: Optional[str] = None
    reported_issue: str = "Неисправность оборудования"
    condition: AssetCondition = AssetCondition.BROKEN
    notes: Optional[str] = None


class EquipmentHistoryResponse(BaseModel):
    id: int
    asset_id: int
    action: str
    user_name: Optional[str] = None
    timestamp: datetime
    details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EquipmentResponse(BaseModel):
    id: int
    inventory_number: str
    serial_number: Optional[str] = None
    name: str
    asset_type: AssetType
    status: AssetStatus
    condition: AssetCondition
    cabinet: Optional[str] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    current_user_id: Optional[str] = None
    current_user_name: Optional[str] = None
    hostname: Optional[str] = None
    os_name: Optional[str] = None
    ad_guid: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EquipmentDetailResponse(EquipmentResponse):
    history: List[EquipmentHistoryResponse] = []


# --- Партии отправки в СЦ (RepairBatch) ---
class RepairBatchItemCreate(BaseModel):
    asset_id: int
    reported_issue: Optional[str] = "Диагностика и ремонт"
    action_required: Optional[str] = "Ремонт"


class RepairBatchCreate(BaseModel):
    vendor_name: str
    branch_id: Optional[int] = None
    notes: Optional[str] = None
    asset_ids: List[int] = []
    issues_map: Optional[Dict[int, str]] = None


class RepairBatchItemResponse(BaseModel):
    id: int
    batch_id: int
    asset_id: int
    reported_issue: Optional[str] = None
    diagnostic_result: Optional[str] = None
    work_performed: Optional[str] = None
    cost: float = 0.0
    status: str = "in_repair"
    asset: Optional[EquipmentResponse] = None
    returned_at: Optional[datetime] = None
    installed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RepairBatchResponse(BaseModel):
    id: int
    act_number: str
    vendor_name: str
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    status: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None
    items_count: int = 0
    items: List[RepairBatchItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- Запросы на смену стадий (без WhatsApp) ---
class ReturnFromSCRequest(BaseModel):
    """ЭТАП 3: Принятие техники из СЦ в IT-отдел."""
    item_ids: Optional[List[int]] = None
    asset_ids: Optional[List[int]] = None
    diagnostic_result: Optional[str] = "Ремонт выполнен успешно"
    work_performed: Optional[str] = "Восстановление работоспособности"
    cost: Optional[float] = 0.0
    condition: AssetCondition = AssetCondition.WORKING
    notes: Optional[str] = None


class InstallAtWorkplaceRequest(BaseModel):
    """ЭТАП 4: Установка техники на рабочее место сотрудника."""
    asset_ids: List[int]
    cabinet: Optional[str] = None
    current_user_id: Optional[str] = None
    notes: Optional[str] = None


# --- AD Синхронизация компьютеров ---
class ADComputerSyncResponse(BaseModel):
    status: str
    message: str
    added: int = 0
    updated: int = 0
