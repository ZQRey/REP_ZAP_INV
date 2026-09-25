import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Numeric,
    JSON,
    Enum as SQLEnum,
    func
)
from sqlalchemy.orm import relationship
from SHARED.database import Base


# ==========================================
# 1. ОБЩЕЕ ЯДРО (SHARED CORE)
# ==========================================

class Branch(Base):
    """Филиал или подразделение компании."""
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, index=True, nullable=False)
    code = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    it_office = Column(String(255), nullable=True)           # Кабинет IT-отдела (напр. "Кабинет 108")
    network_subnets = Column(JSON, nullable=True, default=list) # Подсети в CIDR (напр. ["192.168.1.0/24"])
    wa_message_template = Column(Text, nullable=True)        # Шаблон WhatsApp (только для картриджей)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    users = relationship("AppUser", back_populates="branch")
    cartridges = relationship("Cartridge", back_populates="branch")
    cartridge_batches = relationship("Batch", back_populates="branch")
    assets = relationship("Asset", back_populates="branch")
    floors = relationship("Floor", back_populates="branch", cascade="all, delete-orphan")
    repair_batches = relationship("RepairBatch", back_populates="branch")
    spare_parts = relationship("SparePartsWarehouse", back_populates="branch")


class AppUser(Base):
    """Пользователь системы (оператор, администратор, техник)."""
    __tablename__ = "app_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)
    auth_type = Column(String(20), default="local")          # "local" или "ad"
    role = Column(String(20), default="operator")            # "superadmin", "admin", "technician", "operator", "viewer"
    is_active = Column(Boolean, default=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    wa_instance_name = Column(String(100), nullable=True)    # Только для картриджей
    created_at = Column(DateTime, default=datetime.utcnow)

    branch = relationship("Branch", back_populates="users")


class SystemSetting(Base):
    """Глобальные настройки системы (Active Directory, шлюз WhatsApp, реквизиты)."""
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)


class ADUser(Base):
    """Сотрудники, синхронизированные из Active Directory (для назначения владельцами)."""
    __tablename__ = "ad_users"

    samaccountname = Column(String(100), primary_key=True, index=True)
    display_name = Column(String(255), nullable=False, index=True)
    department = Column(String(255), nullable=True)
    cabinet = Column(String(100), nullable=True)
    phone = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cartridges = relationship("Cartridge", back_populates="current_user")
    assets = relationship("Asset", back_populates="responsible_ad_user")


class AuditLog(Base):
    """Журнал безопасности и системных действий."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False)
    target_module = Column(String(50), nullable=False)      # "cartridge", "repair", "location", "shared"
    target_entity = Column(String(100), nullable=True)
    entity_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ==========================================
# 2. МОДУЛЬ КАРТРИДЖЕЙ (CARTRIDGE)
# ==========================================

class CartridgeStatus(str, enum.Enum):
    IN_USE = "in_use"                     # В работе (в кабинете у сотрудника)
    PENDING_VENDOR = "pending_vendor"     # Ожидает заправщика (принят в IT-отделе)
    AT_VENDOR = "at_vendor"               # На заправке (передан поставщику по акту)
    READY_FOR_PICKUP = "ready_for_pickup" # Готов к выдаче (вернулся с заправки)


class CartridgeModel(Base):
    """Справочник моделей картриджей."""
    __tablename__ = "cartridge_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, index=True, nullable=False)
    vendor = Column(String(100), nullable=True)
    resource_pages = Column(Integer, nullable=True)
    compatible_printers = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Cartridge(Base):
    """Единица картриджа с индивидуальной маркировкой."""
    __tablename__ = "cartridges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marker_label = Column(String(100), unique=True, index=True, nullable=False)
    qr_code = Column(String(100), unique=True, index=True, nullable=True)
    model = Column(String(100), nullable=False)
    cabinet = Column(String(100), nullable=False)
    status = Column(
        SQLEnum(CartridgeStatus),
        default=CartridgeStatus.IN_USE,
        nullable=False,
        index=True
    )
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    current_user_id = Column(
        String(100),
        ForeignKey("ad_users.samaccountname", ondelete="SET NULL"),
        nullable=True
    )
    condition = Column(String(20), default="working")       # "working" | "broken" (для отчетов состояния)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    branch = relationship("Branch", back_populates="cartridges")
    current_user = relationship("ADUser", back_populates="cartridges")
    history = relationship("HistoryLog", back_populates="cartridge", cascade="all, delete-orphan", order_by="desc(HistoryLog.timestamp)")
    batch_items = relationship("BatchItem", back_populates="cartridge")


class Batch(Base):
    """Акт передачи картриджей поставщику услуг заправки."""
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    act_number = Column(String(100), unique=True, index=True, nullable=False)
    vendor_name = Column(String(255), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="open")             # "open" / "closed"
    notes = Column(Text, nullable=True)

    branch = relationship("Branch", back_populates="cartridge_batches")
    items = relationship("BatchItem", back_populates="batch", cascade="all, delete-orphan")


class BatchItem(Base):
    """Позиция картриджа в акте заправки."""
    __tablename__ = "batch_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    cartridge_id = Column(Integer, ForeignKey("cartridges.id", ondelete="CASCADE"), nullable=False)
    action_required = Column(String(100), default="Заправка")

    batch = relationship("Batch", back_populates="items")
    cartridge = relationship("Cartridge", back_populates="batch_items")


class HistoryLog(Base):
    """История операций над картриджем."""
    __tablename__ = "history_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cartridge_id = Column(Integer, ForeignKey("cartridges.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    user_name = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    details = Column(Text, nullable=True)

    cartridge = relationship("Cartridge", back_populates="history")


# ==========================================
# 3. МОДУЛЬ ТЕХНИКИ И РЕМОНТА (REPAIR & ASSETS)
# ==========================================

class AssetType(str, enum.Enum):
    WORKSTATION = "workstation"           # Компьютер (ПК)
    LAPTOP = "laptop"                     # Ноутбук
    MONITOR = "monitor"                   # Монитор
    PRINTER = "printer"                   # Принтер / МФУ
    SERVER = "server"                     # Сервер
    SWITCH = "switch"                     # Коммутатор / Сетевое оборудование
    UPS = "ups"                           # Источник бесперебойного питания (ИБП)
    OTHER = "other"                       # Прочая техника


class AssetStatus(str, enum.Enum):
    AT_WORKPLACE = "at_workplace"         # На рабочем месте (в эксплуатации)
    PENDING_SC = "pending_sc"             # Принято в IT-отделе (ожидает отправки в СЦ)
    AT_SC = "at_sc"                       # В сервисном центре (передано по акту)
    RETURNED_IT = "returned_it"           # Принято из СЦ в IT-отдел (готово к установке)
    DECOMMISSIONED = "decommissioned"     # Списано / Утилизировано


class AssetCondition(str, enum.Enum):
    WORKING = "working"                   # В рабочем состоянии 🟢
    BROKEN = "broken"                     # В нерабочем состоянии 🔴


class EquipmentModel(Base):
    """Справочник моделей техники и оборудования."""
    __tablename__ = "equipment_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, index=True, nullable=False)
    category = Column(String(50), default="other")          # workstation, laptop, monitor, printer, ups, etc.
    vendor = Column(String(100), nullable=True)             # HP, Dell, Lenovo, etc.
    specs_template = Column(Text, nullable=True)            # Примерные характеристики
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Asset(Base):
    """
    Единая таблица оборудования и IT-активов.
    Используется в модуле REPAIR (для ремонтов и инвентаризации)
    и в модуле LOCATION (для отображения на 2D-карте этажа).
    """
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inventory_number = Column(String(100), unique=True, index=True, nullable=False) # Инвентарный номер (основной)
    serial_number = Column(String(100), index=True, nullable=True)                 # Серийный номер
    name = Column(String(150), nullable=False)                                     # Название / Модель
    asset_type = Column(
        SQLEnum(AssetType),
        default=AssetType.WORKSTATION,
        nullable=False,
        index=True
    )
    status = Column(
        SQLEnum(AssetStatus),
        default=AssetStatus.AT_WORKPLACE,
        nullable=False,
        index=True
    )
    condition = Column(
        SQLEnum(AssetCondition),
        default=AssetCondition.WORKING,
        nullable=False,
        index=True
    )
    
    # Active Directory привязка для ПК
    ad_guid = Column(String(100), index=True, nullable=True)
    hostname = Column(String(150), index=True, nullable=True)
    os_name = Column(String(150), nullable=True)
    last_logon = Column(DateTime, nullable=True)

    # Сеть и IP/MAC
    ip_address = Column(String(50), nullable=True)
    mac_address = Column(String(50), nullable=True)

    # Привязка к филиалу, кабинету и сотруднику
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    cabinet = Column(String(100), nullable=True)
    current_user_id = Column(
        String(100),
        ForeignKey("ad_users.samaccountname", ondelete="SET NULL"),
        nullable=True
    )

    # Пространственная привязка (для LOCATION Canvas)
    floor_id = Column(Integer, ForeignKey("floors.id", ondelete="SET NULL"), nullable=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True, index=True)
    coords_x = Column(Float, nullable=True)                  # Нормализованные координаты (0.0 - 1.0)
    coords_y = Column(Float, nullable=True)

    # Спецификация и характеристики (JSON: CPU, RAM, Disk, etc.)
    specs = Column(JSON, nullable=True, default=dict)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    branch = relationship("Branch", back_populates="assets")
    responsible_ad_user = relationship("ADUser", back_populates="assets")
    floor = relationship("Floor", back_populates="assets")
    zone = relationship("Zone", back_populates="assets")
    history = relationship("EquipmentHistoryLog", back_populates="asset", cascade="all, delete-orphan", order_by="desc(EquipmentHistoryLog.timestamp)")
    repair_items = relationship("RepairBatchItem", back_populates="asset")
    switch_device = relationship("NetworkSwitch", back_populates="asset", uselist=False)


class RepairBatch(Base):
    """Акт передачи техники в сервисный центр (пакетная отправка)."""
    __tablename__ = "repair_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    act_number = Column(String(100), unique=True, index=True, nullable=False)
    vendor_name = Column(String(255), nullable=False)        # Название СЦ (напр. "ООО ТехноРемСервис")
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), default="open")             # "open" (в СЦ), "closed" (все позиции возвращены)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    branch = relationship("Branch", back_populates="repair_batches")
    items = relationship("RepairBatchItem", back_populates="batch", cascade="all, delete-orphan")


class RepairBatchItem(Base):
    """Позиция оборудования в акте передачи в сервисный центр."""
    __tablename__ = "repair_batch_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("repair_batches.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    
    reported_issue = Column(Text, nullable=True)            # Заявленная неисправность ("Не включается", "Артефакты")
    diagnostic_result = Column(Text, nullable=True)         # Результат диагностики СЦ ("Сгорел блок питания")
    work_performed = Column(Text, nullable=True)            # Выполненные работы ("Замена конденсаторов БП")
    cost = Column(Numeric(10, 2), default=0.0)              # Стоимость ремонта в тенге (₸)
    status = Column(String(50), default="in_repair")        # "in_repair", "repaired", "unrepairable"
    returned_at = Column(DateTime, nullable=True)           # Дата возврата из СЦ в IT-отдел
    installed_at = Column(DateTime, nullable=True)          # Дата установки на рабочее место

    batch = relationship("RepairBatch", back_populates="items")
    asset = relationship("Asset", back_populates="repair_items")
    parts_used = relationship("RepairPartUsed", back_populates="repair_item", cascade="all, delete-orphan")


class RepairPartUsed(Base):
    """Запасные части и компоненты, использованные при ремонте."""
    __tablename__ = "repair_parts_used"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repair_item_id = Column(Integer, ForeignKey("repair_batch_items.id", ondelete="CASCADE"), nullable=False)
    part_name = Column(String(200), nullable=False)         # Напр. "Блок питания Chieftec 600W"
    serial_number = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1)
    cost = Column(Numeric(10, 2), default=0.0)              # Стоимость в тенге (₸)

    repair_item = relationship("RepairBatchItem", back_populates="parts_used")


class SparePartsWarehouse(Base):
    """Склад запасных частей и расходников филиала."""
    __tablename__ = "spare_parts_warehouse"

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(100), nullable=False)          # Память, Диски, Блоки питания, Кабели
    item_name = Column(String(200), nullable=False)
    quantity = Column(Integer, default=0)
    min_threshold = Column(Integer, default=2)              # Порог предупреждения о малом остатке
    unit_price = Column(Numeric(10, 2), default=0.0)        # Цена за единицу в тенге (₸)

    branch = relationship("Branch", back_populates="spare_parts")


class EquipmentHistoryLog(Base):
    """Полный журнал жизненного цикла оборудования."""
    __tablename__ = "equipment_history_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False)            # "Приемка в IT", "Передача в СЦ", "Принято из СЦ", "Установка на рабочее место", "Смена состояния"
    user_name = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    details = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="history")


# ==========================================
# 4. МОДУЛЬ ТОПОЛОГИИ И 2D КАРТ (LOCATION / NETMAP)
# ==========================================

class Floor(Base):
    """Поэтажный план филиала."""
    __tablename__ = "floors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    floor_number = Column(Integer, default=1)
    name = Column(String(100), nullable=False)              # Напр. "Этаж 1", "Серверная зона"
    map_image_url = Column(String(500), nullable=True)      # URL или путь к загруженному фону SVG/PNG
    scale_pixels_per_meter = Column(Float, default=20.0)    # Масштаб (пикселей на метр)
    created_at = Column(DateTime, default=datetime.utcnow)

    branch = relationship("Branch", back_populates="floors")
    zones = relationship("Zone", back_populates="floor", cascade="all, delete-orphan")
    cable_paths = relationship("CablePath", back_populates="floor", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="floor")


class Zone(Base):
    """Зона, кабинет или коридор на этаже (векторный полигон)."""
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_id = Column(Integer, ForeignKey("floors.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)              # Напр. "Кабинет 108", "Бухгалтерия", "Коридор Север"
    zone_type = Column(String(50), default="office")        # office, corridor, server_room, warehouse
    polygon_coords = Column(JSON, nullable=False, default=list) # [{x: 0.1, y: 0.2}, {x: 0.3, y: 0.2}, ...]
    fill_color = Column(String(50), default="rgba(59, 130, 246, 0.15)")
    border_color = Column(String(50), default="#3b82f6")
    responsible_person = Column(String(200), nullable=True)
    room_number = Column(String(50), nullable=True)

    floor = relationship("Floor", back_populates="zones")
    assets = relationship("Asset", back_populates="zone")


class CablePath(Base):
    """Кабельные каналы и трассы по коридорам для поиска пути."""
    __tablename__ = "cable_paths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_id = Column(Integer, ForeignKey("floors.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=True)
    path_vectors = Column(JSON, nullable=False, default=list) # [{x: 0.1, y: 0.2}, {x: 0.5, y: 0.2}, ...]
    max_capacity = Column(Integer, default=48)

    floor = relationship("Floor", back_populates="cable_paths")


class NetworkSwitch(Base):
    """Сетевой коммутатор (расширение над Asset со спецификацией L2/L3 мониторинга)."""
    __tablename__ = "network_switches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, unique=True)
    ip_address = Column(String(50), nullable=False)
    management_type = Column(String(50), default="snmp")    # "omada", "mikrotik", "hp", "tplink", "snmp", "ssh_cli"
    mgmt_port = Column(Integer, default=161)
    username = Column(String(100), nullable=True)
    password = Column(String(255), nullable=True)
    snmp_community = Column(String(100), default="public")
    model = Column(String(150), nullable=True)
    total_ports = Column(Integer, default=24)               # 24 или 48 портов
    extra_params = Column(JSON, nullable=True)              # {"site": "Default", "enable_pwd": "..."}
    last_poll_status = Column(String(20), default="never")  # "ok", "error", "never"
    last_poll_message = Column(String(500), nullable=True)
    last_polled_at = Column(DateTime, nullable=True)

    asset = relationship("Asset", back_populates="switch_device")
    ports = relationship("SwitchPort", back_populates="switch", cascade="all, delete-orphan")


class SwitchPort(Base):
    """Порт сетевого коммутатора с привязкой к кабинету и трекингом MAC."""
    __tablename__ = "switch_ports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    switch_id = Column(Integer, ForeignKey("network_switches.id", ondelete="CASCADE"), nullable=False)
    port_number = Column(Integer, nullable=False)           # 1..48
    port_speed = Column(String(50), default="1Gbps")
    vlan_id = Column(Integer, default=1)
    status = Column(String(20), default="down")             # "up", "down", "disabled"
    cabinet = Column(String(100), nullable=True)            # Привязка порта к кабинету (напр. "Кабинет 302")
    socket_label = Column(String(100), nullable=True)       # Маркировка розетки (напр. "Розетка 302-1")
    zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True)
    last_mac = Column(String(50), nullable=True)            # Последний зафиксированный MAC (напр. "AA:BB:CC:DD:EE:FF")
    last_ip = Column(String(50), nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    connected_asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)

    switch = relationship("NetworkSwitch", back_populates="ports")
    zone = relationship("Zone")
    connected_asset = relationship("Asset", foreign_keys=[connected_asset_id])
