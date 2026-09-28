# DATABASE_MODEL_MAPPING

Сравнение выполнено **до изменения ORM** на security commit `3b4e419d6efe1c63431eeab88fbf1134bd46c509`. Это продолжение PR #2, не возврат к небезопасному main. Инвентаризация: 22 модели SHARED, 9 дублирующихся Cartridge-моделей, 4 enum-класса в SHARED (один из них продублирован). Runtime mapper inspection включает каждую колонку, nullable, Python/server defaults, onupdate, PK, FK/ondelete/onupdate, enum labels/name, indexes/unique/constraints и каждую relationship/cascade/join/order_by.

## Решение до реализации

Canonical registry, engine, SessionLocal и FastAPI get_db — только `SHARED.database`; конфигурация DATABASE_URL — `SHARED.security_config`, фасад `SHARED.config` её переэкспортирует. Все 22 mapped classes и 4 enums — только `SHARED.models`. Файлы `CARTRIDGE/app/database.py` и `models.py` останутся тонкими compatibility exports **тех же объектов**, без определений классов/фабрик/инициализации. Backend consumers будут импортировать SHARED напрямую.

За основу взяты существующие SHARED-модели. Исключение: `AppUser.role` получает безопасный legacy Python default `user`, чтобы голый ORM-конструктор после переключения не повысил привилегии до operator. Это не server_default, не ALTER TABLE и не изменение сохранённых ролей. API/provisioning уже передают роль явно.

Имена таблиц, колонок, типов, PK/FK, ondelete, nullable, indexes, constraints, enum storage и cascades SHARED сохраняются. Существующая unified DB не требует DDL/переноса данных. В старой standalone Cartridge DB может отсутствовать `branches.network_subnets`: это реальное расхождение, а не косметика. Startup проверит его до записи и остановится с инструкцией; отдельная opt-in миграция добавляет только nullable JSON колонку без backfill/удаления данных. Никакие реальные базы в ходе разработки не изменяются.

## Полный mapping моделей

| Old model | Canonical model | Migration required | Affected modules |
|---|---|---|---|
| `SHARED.models.Branch` + `app.models.Branch` / `CARTRIDGE.app.models.Branch` | `SHARED.models.Branch` (`branches`) | Unified: нет. Legacy-only: nullable network_subnets JSON; связь batches → cartridge_batches | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.AppUser` + `app.models.AppUser` / `CARTRIDGE.app.models.AppUser` | `SHARED.models.AppUser` (`app_users`) | Нет DDL/data migration; только Python default operator → user | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.SystemSetting` + `app.models.SystemSetting` / `CARTRIDGE.app.models.SystemSetting` | `SHARED.models.SystemSetting` (`system_settings`) | Нет DDL; imports на SHARED | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.ADUser` + `app.models.ADUser` / `CARTRIDGE.app.models.ADUser` | `SHARED.models.ADUser` (`ad_users`) | Нет DDL; imports на SHARED | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.AuditLog` | `SHARED.models.AuditLog` (`audit_logs`) | Нет DDL; imports на SHARED | SHARED (пока без runtime consumer) |
| `SHARED.models.CartridgeModel` + `app.models.CartridgeModel` / `CARTRIDGE.app.models.CartridgeModel` | `SHARED.models.CartridgeModel` (`cartridge_models`) | Нет DDL; imports на SHARED | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.Cartridge` + `app.models.Cartridge` / `CARTRIDGE.app.models.Cartridge` | `SHARED.models.Cartridge` (`cartridges`) | Нет DDL; imports на SHARED | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.Batch` + `app.models.Batch` / `CARTRIDGE.app.models.Batch` | `SHARED.models.Batch` (`batches`) | Нет DDL; back_populates batches → cartridge_batches | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.BatchItem` + `app.models.BatchItem` / `CARTRIDGE.app.models.BatchItem` | `SHARED.models.BatchItem` (`batch_items`) | Нет DDL; imports на SHARED | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.HistoryLog` + `app.models.HistoryLog` / `CARTRIDGE.app.models.HistoryLog` | `SHARED.models.HistoryLog` (`history_logs`) | Нет DDL; imports на SHARED | Cartridge, Portal, SHARED, BD scripts |
| `SHARED.models.EquipmentModel` | `SHARED.models.EquipmentModel` (`equipment_models`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.Asset` | `SHARED.models.Asset` (`assets`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.RepairBatch` | `SHARED.models.RepairBatch` (`repair_batches`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.RepairBatchItem` | `SHARED.models.RepairBatchItem` (`repair_batch_items`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.RepairPartUsed` | `SHARED.models.RepairPartUsed` (`repair_parts_used`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.SparePartsWarehouse` | `SHARED.models.SparePartsWarehouse` (`spare_parts_warehouse`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.EquipmentHistoryLog` | `SHARED.models.EquipmentHistoryLog` (`equipment_history_logs`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.Floor` | `SHARED.models.Floor` (`floors`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.Zone` | `SHARED.models.Zone` (`zones`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.CablePath` | `SHARED.models.CablePath` (`cable_paths`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.NetworkSwitch` | `SHARED.models.NetworkSwitch` (`network_switches`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |
| `SHARED.models.SwitchPort` | `SHARED.models.SwitchPort` (`switch_ports`) | Нет DDL; imports на SHARED | Repair, Location, Portal, SHARED |

| Old enum | Canonical enum | Storage / migration |
|---|---|---|
| app.models.CartridgeStatus + SHARED.models.CartridgeStatus | SHARED.models.CartridgeStatus | Одинаковые members; единая identity; без изменения enum labels |
| SHARED.models.AssetType | SHARED.models.AssetType | Без изменения |
| SHARED.models.AssetStatus | SHARED.models.AssetStatus | Без изменения |
| SHARED.models.AssetCondition | SHARED.models.AssetCondition | Без изменения |

## Field-by-field: все дублирующиеся модели

В обозначениях ниже `—` означает отсутствие. Default — Python-side insert default, **не DEFAULT в DDL**. Все server_default у дубликатов отсутствуют. `datetime.utcnow` оставлен как есть: переход timezone-aware требует отдельного согласования. `pk/unique/index` отражают отдельные флаги Column; unique indexes перечислены дополнительно.

### Branch → branches

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `id` | INTEGER; null=False; default=None; update=None; auto=True; primary_key; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `name` | VARCHAR(150); null=False; default=None; update=None; auto=auto; unique,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `code` | VARCHAR(50); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `address` | VARCHAR(255); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `it_office` | VARCHAR(255); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `wa_message_template` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `notes` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `created_at` | DATETIME; null=True; default=datetime.utcnow; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `network_subnets` | — | JSON; null=True; default=list; update=None; auto=auto; none; FK=— | Сохранить SHARED; legacy DB требует совместимости |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|
| `users`: {"target": "AppUser", "back_populates": "branch", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = app_users.branch_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |
| `cartridges`: {"target": "Cartridge", "back_populates": "branch", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = cartridges.branch_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |
| `batches`: {"target": "Batch", "back_populates": "branch", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = batches.branch_id", "order_by": [], "foreign_keys": []} | — | Совместимый synonym на cartridge_batches, без второй relationship |
| `cartridge_batches`: — | {"target": "Batch", "back_populates": "branch", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = batches.branch_id", "order_by": [], "foreign_keys": []} | Сохранить SHARED |
| `assets`: — | {"target": "Asset", "back_populates": "branch", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = assets.branch_id", "order_by": [], "foreign_keys": []} | Сохранить SHARED |
| `floors`: — | {"target": "Floor", "back_populates": "branch", "uselist": true, "cascade": ["delete", "delete-orphan", "expunge", "merge", "refresh-expire", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = floors.branch_id", "order_by": [], "foreign_keys": []} | Сохранить SHARED |
| `repair_batches`: — | {"target": "RepairBatch", "back_populates": "branch", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = repair_batches.branch_id", "order_by": [], "foreign_keys": []} | Сохранить SHARED |
| `spare_parts`: — | {"target": "SparePartsWarehouse", "back_populates": "branch", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = spare_parts_warehouse.branch_id", "order_by": [], "foreign_keys": []} | Сохранить SHARED |

Indexes: `[{"name": "ix_branches_name", "columns": ["name"], "unique": true}]`. Совпадают с legacy.

Constraints: `[{"type": "PrimaryKeyConstraint", "name": null, "columns": ["id"]}]`. Совпадают с legacy.

### CartridgeModel → cartridge_models

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `id` | INTEGER; null=False; default=None; update=None; auto=True; primary_key; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `name` | VARCHAR(150); null=False; default=None; update=None; auto=auto; unique,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `vendor` | VARCHAR(100); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `resource_pages` | INTEGER; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `compatible_printers` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `notes` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `created_at` | DATETIME; null=True; default=datetime.utcnow; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|

Indexes: `[{"name": "ix_cartridge_models_name", "columns": ["name"], "unique": true}]`. Совпадают с legacy.

Constraints: `[{"type": "PrimaryKeyConstraint", "name": null, "columns": ["id"]}]`. Совпадают с legacy.

### AppUser → app_users

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `id` | INTEGER; null=False; default=None; update=None; auto=True; primary_key; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `username` | VARCHAR(100); null=False; default=None; update=None; auto=auto; unique,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `full_name` | VARCHAR(255); null=False; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `password_hash` | VARCHAR(255); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `auth_type` | VARCHAR(20); null=True; default=local; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `role` | VARCHAR(20); null=True; default=user; update=None; auto=auto; none; FK=— | VARCHAR(20); null=True; default=operator; update=None; auto=auto; none; FK=— | Legacy default user; остальные свойства SHARED |
| `is_active` | BOOLEAN; null=True; default=True; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `branch_id` | INTEGER; null=True; default=None; update=None; auto=auto; none; FK=branches.id (delete=SET NULL, update=None) | = Legacy | Сохранить SHARED (совпадает) |
| `wa_instance_name` | VARCHAR(100); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `created_at` | DATETIME; null=True; default=datetime.utcnow; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|
| `branch`: {"target": "Branch", "back_populates": "users", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = app_users.branch_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |

Indexes: `[{"name": "ix_app_users_username", "columns": ["username"], "unique": true}]`. Совпадают с legacy.

Constraints: `[{"type": "ForeignKeyConstraint", "name": null, "columns": ["branch_id"]}, {"type": "PrimaryKeyConstraint", "name": null, "columns": ["id"]}]`. Совпадают с legacy.

### SystemSetting → system_settings

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `key` | VARCHAR(100); null=False; default=None; update=None; auto=auto; primary_key,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `value` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `description` | VARCHAR(255); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|

Indexes: `[{"name": "ix_system_settings_key", "columns": ["key"], "unique": false}]`. Совпадают с legacy.

Constraints: `[{"type": "PrimaryKeyConstraint", "name": null, "columns": ["key"]}]`. Совпадают с legacy.

### ADUser → ad_users

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `samaccountname` | VARCHAR(100); null=False; default=None; update=None; auto=auto; primary_key,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `display_name` | VARCHAR(255); null=False; default=None; update=None; auto=auto; index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `department` | VARCHAR(255); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `cabinet` | VARCHAR(100); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `phone` | VARCHAR(100); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `updated_at` | DATETIME; null=True; default=datetime.utcnow; update=datetime.utcnow; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|
| `cartridges`: {"target": "Cartridge", "back_populates": "current_user", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "ad_users.samaccountname = cartridges.current_user_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |
| `assets`: — | {"target": "Asset", "back_populates": "responsible_ad_user", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "ad_users.samaccountname = assets.current_user_id", "order_by": [], "foreign_keys": []} | Сохранить SHARED |

Indexes: `[{"name": "ix_ad_users_display_name", "columns": ["display_name"], "unique": false}, {"name": "ix_ad_users_samaccountname", "columns": ["samaccountname"], "unique": false}]`. Совпадают с legacy.

Constraints: `[{"type": "PrimaryKeyConstraint", "name": null, "columns": ["samaccountname"]}]`. Совпадают с legacy.

### Cartridge → cartridges

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `id` | INTEGER; null=False; default=None; update=None; auto=True; primary_key; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `marker_label` | VARCHAR(100); null=False; default=None; update=None; auto=auto; unique,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `qr_code` | VARCHAR(100); null=True; default=None; update=None; auto=auto; unique,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `model` | VARCHAR(100); null=False; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `cabinet` | VARCHAR(100); null=False; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `status` | VARCHAR(16); null=False; default=CartridgeStatus.IN_USE; update=None; auto=auto; index; FK=—; enum={'name': 'cartridgestatus', 'labels': ['IN_USE', 'PENDING_VENDOR', 'AT_VENDOR', 'READY_FOR_PICKUP'], 'native_enum': True, 'create_constraint': False, 'validate_strings': False} | = Legacy | Сохранить SHARED (совпадает) |
| `branch_id` | INTEGER; null=True; default=None; update=None; auto=auto; index; FK=branches.id (delete=SET NULL, update=None) | = Legacy | Сохранить SHARED (совпадает) |
| `current_user_id` | VARCHAR(100); null=True; default=None; update=None; auto=auto; none; FK=ad_users.samaccountname (delete=SET NULL, update=None) | = Legacy | Сохранить SHARED (совпадает) |
| `condition` | VARCHAR(20); null=True; default=working; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `notes` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `updated_at` | DATETIME; null=True; default=datetime.utcnow; update=datetime.utcnow; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|
| `branch`: {"target": "Branch", "back_populates": "cartridges", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = cartridges.branch_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |
| `current_user`: {"target": "ADUser", "back_populates": "cartridges", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "ad_users.samaccountname = cartridges.current_user_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |
| `history`: {"target": "HistoryLog", "back_populates": "cartridge", "uselist": true, "cascade": ["delete", "delete-orphan", "expunge", "merge", "refresh-expire", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "cartridges.id = history_logs.cartridge_id", "order_by": ["history_logs.timestamp DESC"], "foreign_keys": []} | = Legacy | Сохранить SHARED |
| `batch_items`: {"target": "BatchItem", "back_populates": "cartridge", "uselist": true, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "cartridges.id = batch_items.cartridge_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |

Indexes: `[{"name": "ix_cartridges_branch_id", "columns": ["branch_id"], "unique": false}, {"name": "ix_cartridges_marker_label", "columns": ["marker_label"], "unique": true}, {"name": "ix_cartridges_qr_code", "columns": ["qr_code"], "unique": true}, {"name": "ix_cartridges_status", "columns": ["status"], "unique": false}]`. Совпадают с legacy.

Constraints: `[{"type": "ForeignKeyConstraint", "name": null, "columns": ["branch_id"]}, {"type": "ForeignKeyConstraint", "name": null, "columns": ["current_user_id"]}, {"type": "PrimaryKeyConstraint", "name": null, "columns": ["id"]}]`. Совпадают с legacy.

### Batch → batches

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `id` | INTEGER; null=False; default=None; update=None; auto=True; primary_key; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `act_number` | VARCHAR(100); null=False; default=None; update=None; auto=auto; unique,index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `vendor_name` | VARCHAR(255); null=False; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `branch_id` | INTEGER; null=True; default=None; update=None; auto=auto; index; FK=branches.id (delete=SET NULL, update=None) | = Legacy | Сохранить SHARED (совпадает) |
| `created_at` | DATETIME; null=True; default=datetime.utcnow; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `status` | VARCHAR(50); null=True; default=open; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `notes` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|
| `branch`: {"target": "Branch", "back_populates": "batches", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = batches.branch_id", "order_by": [], "foreign_keys": []} | {"target": "Branch", "back_populates": "cartridge_batches", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "branches.id = batches.branch_id", "order_by": [], "foreign_keys": []} | Сохранить SHARED |
| `items`: {"target": "BatchItem", "back_populates": "batch", "uselist": true, "cascade": ["delete", "delete-orphan", "expunge", "merge", "refresh-expire", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "batches.id = batch_items.batch_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |

Indexes: `[{"name": "ix_batches_act_number", "columns": ["act_number"], "unique": true}, {"name": "ix_batches_branch_id", "columns": ["branch_id"], "unique": false}]`. Совпадают с legacy.

Constraints: `[{"type": "ForeignKeyConstraint", "name": null, "columns": ["branch_id"]}, {"type": "PrimaryKeyConstraint", "name": null, "columns": ["id"]}]`. Совпадают с legacy.

### BatchItem → batch_items

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `id` | INTEGER; null=False; default=None; update=None; auto=True; primary_key; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `batch_id` | INTEGER; null=False; default=None; update=None; auto=auto; none; FK=batches.id (delete=CASCADE, update=None) | = Legacy | Сохранить SHARED (совпадает) |
| `cartridge_id` | INTEGER; null=False; default=None; update=None; auto=auto; none; FK=cartridges.id (delete=CASCADE, update=None) | = Legacy | Сохранить SHARED (совпадает) |
| `action_required` | VARCHAR(100); null=True; default=Заправка; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|
| `batch`: {"target": "Batch", "back_populates": "items", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "batches.id = batch_items.batch_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |
| `cartridge`: {"target": "Cartridge", "back_populates": "batch_items", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "cartridges.id = batch_items.cartridge_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |

Indexes: `[]`. Совпадают с legacy.

Constraints: `[{"type": "ForeignKeyConstraint", "name": null, "columns": ["batch_id"]}, {"type": "ForeignKeyConstraint", "name": null, "columns": ["cartridge_id"]}, {"type": "PrimaryKeyConstraint", "name": null, "columns": ["id"]}]`. Совпадают с legacy.

### HistoryLog → history_logs

| Поле | Legacy | SHARED до изменения | Canonical decision |
|---|---|---|---|
| `id` | INTEGER; null=False; default=None; update=None; auto=True; primary_key; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `cartridge_id` | INTEGER; null=False; default=None; update=None; auto=auto; index; FK=cartridges.id (delete=CASCADE, update=None) | = Legacy | Сохранить SHARED (совпадает) |
| `action` | VARCHAR(100); null=False; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `user_name` | VARCHAR(255); null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `timestamp` | DATETIME; null=True; default=datetime.utcnow; update=None; auto=auto; index; FK=— | = Legacy | Сохранить SHARED (совпадает) |
| `details` | TEXT; null=True; default=None; update=None; auto=auto; none; FK=— | = Legacy | Сохранить SHARED (совпадает) |

Relationships (сравниваются также join, uselist, cascade, lazy, passive_deletes, viewonly и order_by):

| Legacy relation | SHARED relation | Решение |
|---|---|---|
| `cartridge`: {"target": "Cartridge", "back_populates": "history", "uselist": false, "cascade": ["merge", "save-update"], "lazy": "select", "passive_deletes": false, "viewonly": false, "join": "cartridges.id = history_logs.cartridge_id", "order_by": [], "foreign_keys": []} | = Legacy | Сохранить SHARED |

Indexes: `[{"name": "ix_history_logs_cartridge_id", "columns": ["cartridge_id"], "unique": false}, {"name": "ix_history_logs_timestamp", "columns": ["timestamp"], "unique": false}]`. Совпадают с legacy.

Constraints: `[{"type": "ForeignKeyConstraint", "name": null, "columns": ["cartridge_id"]}, {"type": "PrimaryKeyConstraint", "name": null, "columns": ["id"]}]`. Совпадают с legacy.

## Существенные расхождения и совместимость

1. Branch.network_subnets: отсутствует в legacy; SHARED JSON nullable=True, Python default=list. Дополнительные связи SHARED: assets, floors (all/delete-orphan), repair_batches, spare_parts. Branch.batches переименован в cartridge_batches; прежнее имя останется synonym на ту же collection для внешних callers. Единственный Batch.branch.back_populates — cartridge_batches.
2. AppUser.role: тип VARCHAR(20), nullable=True и constraints идентичны, различается только Python default. Выбран user, существующие role values не переписываются; role остаётся строкой, значения user/viewer/operator/admin/superadmin не переводятся в enum.
3. ADUser.assets есть только в SHARED, back_populates=responsible_ad_user. Остальные колонки и cartridges relation совпадают.
4. CartridgeStatus: persisted SQLAlchemy enum labels — IN_USE/PENDING_VENDOR/AT_VENDOR/READY_FOR_PICKUP, не lower-case Python values. Сохраняются имя cartridgestatus, native_enum, длина VARCHAR и flags; нельзя вводить values_callable или пересоздавать PostgreSQL enum в рамках этого refactor.
5. Старый init_db писал branches.it_office VARCHAR(255), SHARED legacy ALTER — VARCHAR(100), но обе ORM-модели объявляют VARCHAR(255). Физическое расхождение существующих БД не исправляется автоматически. Проверка реальной deployed schema остаётся обязательной.
6. В старом тесте test_user_requirements_verification создавались отдельные engine/sessionmaker; перевод на canonical объекты убирает дополнительный pool и несовместимые dependency overrides.

## Границы и безопасный порядок

1. Зафиксировать mapping и metadata contract до редактирования.
2. Перевести consumers/скрипты на SHARED; заменить legacy files exports тех же объектов; не копировать классы и не наследовать второй Base.
3. Убрать eager import cycle SHARED package → auth → database/models: package exports сделать lazy, init_db импортирует models только при выполнении. Сохранить старые public exports.
4. Один get_db с rollback при ошибке и close в finally; FastAPI использует dependency cache. Authentication guard получает тот же db через Depends вместо отдельной middleware session. Сервисы принимают Session аргументом; commit остаётся явной обязанностью business operation, auto-commit не вводится.
5. Сохранить существующую canonical init_db семантику unified deployment. Legacy startup DDL остаётся одной реализацией в SHARED; это не замена Alembic. Проверка network_subnets идёт до create_all и seeding.
6. Проверить identity Base/engine/factory/dependency/models/enums для всех путей импорта, configure_mappers и subprocess import orders, schema contract для SQLite/PostgreSQL DDL и чтение старых строк.
7. Выполнить architecture tests, security regressions и конечный поиск фабрик. Не выполнять reset_data, BD/migrate_data или миграцию на реальной базе.

## Legacy-only database: единственная условная schema migration

После backup/проверки восстановления: `python -m SHARED.migrations.add_branch_network_subnets --check`. Если отсутствует колонка, `--apply` добавит `branches.network_subnets JSON` с NULL для прежних строк. Повторный запуск — no-op. Никаких rename/drop/rewrite enum/backfill. Для уже актуальной unified schema миграция не требуется. Эта команда не вызывается автоматически startup и не выполнялась над production.

## Замечание об административных scripts

После объединения registry `Base.metadata.drop_all()` охватывает все 22 таблицы: его нельзя применять как Cartridge-only reset. Существующие ручные тесты запускаются только на отдельной временной DB. Reset script не запускается в этой работе; его database target должен происходить из canonical engine, а production reset будет запрещён, чтобы смена imports не расширила опасное поведение.
