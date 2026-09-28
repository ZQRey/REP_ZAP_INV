# Authorization matrix

Актуальная реализация: `SHARED/authentication.py`, `SHARED/policies/`. Подробный поток и deployment: [AUTHORIZATION_ARCHITECTURE.md](AUTHORIZATION_ARCHITECTURE.md). Эта матрица заменяет первоначальную аудиторскую матрицу; она описывает реализованные ограничения.

S = superadmin; A = branch admin; T = technician; O = operator; V = viewer; U = user. Любое разрешение A/T/O/V/U относится только к своему ненулевому branch. U дополнительно ограничен ownership по login. «Через операцию» означает отсутствие самостоятельного CRUD endpoint: изменение возможно только из явно разрешенной бизнес-операции. Ни одна новая роль или новый endpoint не получает доступ по умолчанию.

| Entity | Scope | Read | Create | Update | Delete | Cross-branch |
|---|---|---|---|---|---|---|
| Branch | branch, ownership по id | S/A/T/O/V/U | S | S/A; network_subnets только S | S, только без зависимых ресурсов | S |
| AppUser | branch; profile self | S/A; свой профиль всем | S/A, A только lower roles | S/A, A не self/peer/admin/superadmin | S/A, те же ограничения | S; членство можно явно изменить |
| Asset | branch; U owner-only | S/A/T/O/V/U | S/A/T/O | S/A/T/O; network credentials T/A/S | S/A/T | S; перенос обычным PUT запрещён |
| EquipmentHistoryLog | Asset | через Asset/report | через разрешенную операцию | нет API | через удаление Asset | S |
| RepairBatch | branch | S/A/T/O/V | S/A/T/O | S/A/T/O, close | нет API | S; состав одного филиала |
| RepairBatchItem | RepairBatch AND Asset | S/A/T/O/V | через batch | S/A/T/O, возврат из СЦ | через удаление Asset | связи между филиалами запрещены |
| RepairPartUsed | RepairBatchItem | через разрешенную операцию | нет API | нет API | через удаление Item | S, в рамках родителя |
| SparePartsWarehouse | branch | нет API | нет API | нет API | нет API | будущий endpoint требует отдельной политики |
| Cartridge | branch; U owner-only | S/A/T/O/V/U | S/A/O | S/A/O, прием/выдача/возврат | S/A | S; перенос обычным PUT запрещён |
| HistoryLog | Cartridge | через Cartridge/report | через разрешенную операцию | нет API | через Cartridge | S |
| Batch | branch | S/A/T/O/V | S/A/O | через возврат картриджей | нет API | S; состав одного филиала |
| BatchItem | Batch AND Cartridge | через Batch | через batch | нет API | через удаление родителя | связи между филиалами запрещены |
| Floor | branch | S/A/T/O/V | S/A | S/A, включая карту | S/A | S |
| Zone (cabinet) | Floor | S/A/T/O/V | S/A/T | нет самостоятельного UPDATE API | S/A | S; связи одного филиала |
| CablePath | Floor | S/A/T/O/V через trace | нет API | нет API | через Floor | S |
| NetworkSwitch | Asset | S/A/T/O/V | S/A/T | S/A/T; poll также O | S/A/T | S; MAC matching только branch коммутатора |
| SwitchPort | NetworkSwitch; Zone/Asset same branch | S/A/T/O/V | через switch/port operation | S/A/T/O; connect endpoint S/A/T | через Switch | cross-links запрещены |
| CartridgeModel | global | S/A/T/O/V/U | S | S | S | глобальный справочник |
| EquipmentModel | global; computed counts/specs scoped | S/A/T/O/V/U | S | S | S | глобальный справочник |
| ADUser | global, staff-only directory | S/A/T/O | S через sync; проверенный AD login обновляет собственный профиль | те же операции | нет API | явно глобальный, branch в схеме отсутствует |
| SystemSetting | global; masked response | S/A/T/O/V/U | S | S | нет API | глобальные настройки |
| AuditLog | global, restricted | только доверенный административный код S | нет API | нет API | нет API | обычным пользователям скрыт |
| DocumentCounter | global, internal | нет API | Alembic initialization | atomic increment внутри разрешенной write operation | нет API | не клиентский ресурс |

Дополнительные ресурсы:

| Resource | Scope | Read | Create/Update/Delete | Cross-branch |
|---|---|---|---|---|
| Repair/Cartridge reports и print | выбранный branch; все вложенные строки scoped | S/A/T/O/V | read-only | S |
| Location statistics, placements, paths | branch через Floor/Asset/Switch | S/A/T/O/V | placement S/A/T, assign/create также O | S; foreign references запрещены |
| Floor map file | владелец Floor | S/A/T/O/V через authenticated endpoint | S/A upload | S; public static запрещён |
| WhatsApp account QR/status/reset | self instance | S/A/O | S/A/O self | только S |
| WhatsApp notifications | scoped Cartridge | результат своей операции | S/A/O; все IDs до отправки | S по explicit policy |
| AD/network integrations, settings tests | global либо scoped network target | по endpoint registry ниже | global S; branch network S/A/T, poll O | raw IP только branch allowlist/свой switch; S global allowlist |
| Portal HTML, module HTML/CSS/JS, health, OpenAPI | public shell/schema | anonymous | нет data mutation | данных филиалов не содержат |
| Login | public credential exchange | нет | rate-limited authentication | выдача JWT не отменяет branch policy |

## Проверенные классы обходов

| Проверка | Серверное решение | Regression evidence |
|---|---|---|
| Foreign numeric Asset ID GET/PUT/DELETE | scoped lookup, 404 | `test_foreign_object_ids_rejected` |
| Client branch_id при создании | foreign/0/-1 → 403; omitted → branch Principal | create/selector tests |
| Repair batch c чужим Asset, bulk movements/notification | каждый ID проверен до обработчика | foreign bulk + adapter preflight tests |
| Floor/Zone/Switch/port/path references | parent scope + same-branch links | location/network cases |
| Admin role/self/branch escalation | explicit user-management policy | branch admin tests |
| Forged JWT role/branch | только DB role/branch | fixture deliberately injects elevated claims |
| Branchless/inactive/unknown role | branch APIs 403 / inactive 401 / unknown role 403 | account tests |
| Reports, aggregates, aliases, eager/lazy loaders | единый SQL scope | reports + ORM tests |
| Public map URL/copy another floor's URL | static 404 + scoped map endpoint | floor map test |
| Старые cross-branch FK/cascade | preflight 409, данные не меняются | legacy relationship test |
| Новый маршрут без policy | fail-closed 403 + inventory/architecture test | unknown endpoint test |
| Анонимный доступ/Viewer mutation/foreign branch query | проверены все реальные mounted routes | exhaustive route loops |

## Полный реестр HTTP-операций

Ниже каждая source declaration, включая aliases. Root дополнительно подключает CARTRIDGE/REPAIR/LOCATION по соответствующим mount prefixes; standalone applications используют тот же guard. Тест обходит реальные подключения, а не только эту таблицу. Starlette static mounts и генерируемые docs/OpenAPI перечислены отдельно выше. Реестр не включает CLI и SQL migrations: это доверенные административные операции.

<!-- GENERATED_ENDPOINT_TABLE -->

113 source declarations; 110 handler/method policies.

| Method | Path | Roles | Action / scope | Source |
|---|---|---|---|---|
| GET | `/health` | anonymous | read / public | [CARTRIDGE/app/main.py:72](CARTRIDGE/app/main.py#L72) |
| GET | `/` | anonymous | read / public | [CARTRIDGE/app/main.py:77](CARTRIDGE/app/main.py#L77) |
| GET | `/api/app-users` | S/A | read / branch | [CARTRIDGE/app/routers/app_users_router.py:15](CARTRIDGE/app/routers/app_users_router.py#L15) |
| POST | `/api/app-users` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:26](CARTRIDGE/app/routers/app_users_router.py#L26) |
| PUT | `/api/app-users/{user_id}` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:67](CARTRIDGE/app/routers/app_users_router.py#L67) |
| DELETE | `/api/app-users/{user_id}` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:112](CARTRIDGE/app/routers/app_users_router.py#L112) |
| POST | `/api/app-users/{user_id}/toggle-active` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:134](CARTRIDGE/app/routers/app_users_router.py#L134) |
| POST | `/api/auth/login` | anonymous | write / public | [CARTRIDGE/app/routers/auth_router.py:14](CARTRIDGE/app/routers/auth_router.py#L14) |
| GET | `/api/auth/me` | S/A/T/O/V/U | read / profile | [CARTRIDGE/app/routers/auth_router.py:52](CARTRIDGE/app/routers/auth_router.py#L52) |
| GET | `/api/batches` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/batches_router.py:17](CARTRIDGE/app/routers/batches_router.py#L17) |
| GET | `/api/batches/{batch_id}` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/batches_router.py:42](CARTRIDGE/app/routers/batches_router.py#L42) |
| POST | `/api/batches` | S/A/O | write / branch | [CARTRIDGE/app/routers/batches_router.py:63](CARTRIDGE/app/routers/batches_router.py#L63) |
| GET | `/api/branches` | S/A/T/O/V/U | read / branch | [CARTRIDGE/app/routers/branches_router.py:14](CARTRIDGE/app/routers/branches_router.py#L14) |
| POST | `/api/branches` | S | write / branch | [CARTRIDGE/app/routers/branches_router.py:20](CARTRIDGE/app/routers/branches_router.py#L20) |
| PUT | `/api/branches/{branch_id}` | S/A | write / branch | [CARTRIDGE/app/routers/branches_router.py:46](CARTRIDGE/app/routers/branches_router.py#L46) |
| DELETE | `/api/branches/{branch_id}` | S | write / branch | [CARTRIDGE/app/routers/branches_router.py:81](CARTRIDGE/app/routers/branches_router.py#L81) |
| GET | `/api/cartridges` | S/A/T/O/V/U | read / branch | [CARTRIDGE/app/routers/cartridges_router.py:25](CARTRIDGE/app/routers/cartridges_router.py#L25) |
| GET | `/api/cartridges/search/quick` | S/A/T/O/V/U | read / branch | [CARTRIDGE/app/routers/cartridges_router.py:59](CARTRIDGE/app/routers/cartridges_router.py#L59) |
| GET | `/api/cartridges/{cartridge_id}` | S/A/T/O/V/U | read / branch | [CARTRIDGE/app/routers/cartridges_router.py:86](CARTRIDGE/app/routers/cartridges_router.py#L86) |
| POST | `/api/cartridges` | S/A/O | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:105](CARTRIDGE/app/routers/cartridges_router.py#L105) |
| PUT | `/api/cartridges/{cartridge_id}` | S/A/O | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:147](CARTRIDGE/app/routers/cartridges_router.py#L147) |
| DELETE | `/api/cartridges/{cartridge_id}` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:206](CARTRIDGE/app/routers/cartridges_router.py#L206) |
| POST | `/api/cartridges/accept` | S/A/O | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:221](CARTRIDGE/app/routers/cartridges_router.py#L221) |
| POST | `/api/cartridges/{cartridge_id}/issue` | S/A/O | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:298](CARTRIDGE/app/routers/cartridges_router.py#L298) |
| POST | `/api/cartridges/bulk-issue` | S/A/O | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:335](CARTRIDGE/app/routers/cartridges_router.py#L335) |
| POST | `/api/cartridges/return-vendor` | S/A/O | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:377](CARTRIDGE/app/routers/cartridges_router.py#L377) |
| GET | `/api/cartridge-models` | S/A/T/O/V/U | read / catalogs | [CARTRIDGE/app/routers/models_router.py:15](CARTRIDGE/app/routers/models_router.py#L15) |
| POST | `/api/cartridge-models` | S | write / catalogs | [CARTRIDGE/app/routers/models_router.py:49](CARTRIDGE/app/routers/models_router.py#L49) |
| PUT | `/api/cartridge-models/{model_id}` | S | write / catalogs | [CARTRIDGE/app/routers/models_router.py:80](CARTRIDGE/app/routers/models_router.py#L80) |
| DELETE | `/api/cartridge-models/{model_id}` | S | write / catalogs | [CARTRIDGE/app/routers/models_router.py:125](CARTRIDGE/app/routers/models_router.py#L125) |
| POST | `/api/notifications/whatsapp/ready` | S/A/O | write / branch | [CARTRIDGE/app/routers/notifications_router.py:17](CARTRIDGE/app/routers/notifications_router.py#L17) |
| GET | `/print/act/{batch_id}` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/print_router.py:33](CARTRIDGE/app/routers/print_router.py#L33) |
| GET | `/api/reports/data` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/reports_router.py:18](CARTRIDGE/app/routers/reports_router.py#L18) |
| GET | `/api/reports/export/excel` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/reports_router.py:51](CARTRIDGE/app/routers/reports_router.py#L51) |
| GET | `/api/reports/export/pdf` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/reports_router.py:102](CARTRIDGE/app/routers/reports_router.py#L102) |
| GET | `/api/settings` | S/A/T/O/V/U | read / settings | [CARTRIDGE/app/routers/settings_router.py:17](CARTRIDGE/app/routers/settings_router.py#L17) |
| POST | `/api/settings` | S | write / settings | [CARTRIDGE/app/routers/settings_router.py:28](CARTRIDGE/app/routers/settings_router.py#L28) |
| PUT | `/api/settings` | S | write / settings | [CARTRIDGE/app/routers/settings_router.py:28](CARTRIDGE/app/routers/settings_router.py#L28) |
| POST | `/api/settings/ldap/test` | S | write / settings | [CARTRIDGE/app/routers/settings_router.py:45](CARTRIDGE/app/routers/settings_router.py#L45) |
| POST | `/api/settings/ldap/sync` | S | write / settings | [CARTRIDGE/app/routers/settings_router.py:63](CARTRIDGE/app/routers/settings_router.py#L63) |
| POST | `/api/settings/ad-sync` | S | write / settings | [CARTRIDGE/app/routers/settings_router.py:63](CARTRIDGE/app/routers/settings_router.py#L63) |
| GET | `/api/settings/wa/status` | S/A/O | wa_self / branch | [CARTRIDGE/app/routers/settings_router.py:73](CARTRIDGE/app/routers/settings_router.py#L73) |
| GET | `/api/settings/wa/operators-status` | S | read / settings | [CARTRIDGE/app/routers/settings_router.py:100](CARTRIDGE/app/routers/settings_router.py#L100) |
| POST | `/api/settings/wa/qr` | S/A/O | wa_self / branch | [CARTRIDGE/app/routers/settings_router.py:109](CARTRIDGE/app/routers/settings_router.py#L109) |
| POST | `/api/settings/wa/reset` | S/A/O | wa_self / branch | [CARTRIDGE/app/routers/settings_router.py:146](CARTRIDGE/app/routers/settings_router.py#L146) |
| POST | `/api/settings/wa/test` | S | write / settings | [CARTRIDGE/app/routers/settings_router.py:181](CARTRIDGE/app/routers/settings_router.py#L181) |
| GET | `/api/users` | S/A/T/O | read / directory | [CARTRIDGE/app/routers/users_router.py:15](CARTRIDGE/app/routers/users_router.py#L15) |
| GET | `/api/users/ad` | S/A/T/O | read / directory | [CARTRIDGE/app/routers/users_router.py:15](CARTRIDGE/app/routers/users_router.py#L15) |
| GET | `/health` | anonymous | read / public | [LOCATION/app/main.py:48](LOCATION/app/main.py#L48) |
| GET | `/` | anonymous | read / public | [LOCATION/app/main.py:53](LOCATION/app/main.py#L53) |
| GET | `/api/v1/location/floors/{floor_id}/assets` | S/A/T/O/V | read / branch | [LOCATION/app/routers/assets_placement_router.py:112](LOCATION/app/routers/assets_placement_router.py#L112) |
| GET | `/api/v1/location/placed-assets` | S/A/T/O/V | read / branch | [LOCATION/app/routers/assets_placement_router.py:130](LOCATION/app/routers/assets_placement_router.py#L130) |
| GET | `/api/v1/location/unplaced-assets` | S/A/T/O/V | read / branch | [LOCATION/app/routers/assets_placement_router.py:169](LOCATION/app/routers/assets_placement_router.py#L169) |
| POST | `/api/v1/location/assets/{asset_id}/position` | S/A/T | write / branch | [LOCATION/app/routers/assets_placement_router.py:206](LOCATION/app/routers/assets_placement_router.py#L206) |
| POST | `/api/v1/location/assets/{asset_id}/assign-cabinet` | S/A/T/O | write / branch | [LOCATION/app/routers/assets_placement_router.py:233](LOCATION/app/routers/assets_placement_router.py#L233) |
| POST | `/api/v1/location/assets/{asset_id}/unplace` | S/A/T | write / branch | [LOCATION/app/routers/assets_placement_router.py:282](LOCATION/app/routers/assets_placement_router.py#L282) |
| POST | `/api/v1/location/assets/create-and-place` | S/A/T/O | write / branch | [LOCATION/app/routers/assets_placement_router.py:301](LOCATION/app/routers/assets_placement_router.py#L301) |
| GET | `/api/v1/location/floors/{floor_id}/map` | S/A/T/O/V | read / branch | [LOCATION/app/routers/floors_router.py:15](LOCATION/app/routers/floors_router.py#L15) |
| GET | `/api/v1/location/branches/{branch_id}/floors` | S/A/T/O/V | read / branch | [LOCATION/app/routers/floors_router.py:34](LOCATION/app/routers/floors_router.py#L34) |
| POST | `/api/v1/location/floors` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:46](LOCATION/app/routers/floors_router.py#L46) |
| PUT | `/api/v1/location/floors/{floor_id}` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:66](LOCATION/app/routers/floors_router.py#L66) |
| DELETE | `/api/v1/location/floors/{floor_id}` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:92](LOCATION/app/routers/floors_router.py#L92) |
| POST | `/api/v1/location/floors/{floor_id}/upload-map` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:119](LOCATION/app/routers/floors_router.py#L119) |
| GET | `/api/v1/location/network/trace` | S/A/T/O/V | read / branch | [LOCATION/app/routers/pathfinding_router.py:15](LOCATION/app/routers/pathfinding_router.py#L15) |
| GET | `/api/v1/location/stats` | S/A/T/O/V | read / branch | [LOCATION/app/routers/pathfinding_router.py:39](LOCATION/app/routers/pathfinding_router.py#L39) |
| GET | `/api/v1/location/floors/{floor_id}/switches` | S/A/T/O/V | read / branch | [LOCATION/app/routers/switches_router.py:80](LOCATION/app/routers/switches_router.py#L80) |
| POST | `/api/v1/location/switches` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:96](LOCATION/app/routers/switches_router.py#L96) |
| PUT | `/api/v1/location/switches/{switch_id}` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:166](LOCATION/app/routers/switches_router.py#L166) |
| POST | `/api/v1/location/switches/test-connection` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:219](LOCATION/app/routers/switches_router.py#L219) |
| DELETE | `/api/v1/location/switches/{switch_id}` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:239](LOCATION/app/routers/switches_router.py#L239) |
| PUT | `/api/v1/location/switches/{switch_id}/ports/{port_number}` | S/A/T/O | write / branch | [LOCATION/app/routers/switches_router.py:270](LOCATION/app/routers/switches_router.py#L270) |
| POST | `/api/v1/location/switches/{switch_id}/ports/{port_number}/connect` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:337](LOCATION/app/routers/switches_router.py#L337) |
| POST | `/api/v1/location/switches/{switch_id}/poll` | S/A/T/O | write / branch | [LOCATION/app/routers/switches_router.py:360](LOCATION/app/routers/switches_router.py#L360) |
| POST | `/api/v1/location/switches/{switch_id}/simulate-event` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:379](LOCATION/app/routers/switches_router.py#L379) |
| POST | `/api/v1/location/floors/{floor_id}/zones` | S/A/T | write / branch | [LOCATION/app/routers/zones_router.py:13](LOCATION/app/routers/zones_router.py#L13) |
| DELETE | `/api/v1/location/zones/{zone_id}` | S/A | write / branch | [LOCATION/app/routers/zones_router.py:41](LOCATION/app/routers/zones_router.py#L41) |
| POST | `/api/v1/auth/login` | anonymous | write / public | [main_server.py:77](main_server.py#L77) |
| GET | `/api/v1/auth/me` | S/A/T/O/V/U | read / profile | [main_server.py:112](main_server.py#L112) |
| GET | `/static/js/app.js` | anonymous | read / public | [main_server.py:199](main_server.py#L199) |
| GET | `/static/js/qr-scanner.js` | anonymous | read / public | [main_server.py:203](main_server.py#L203) |
| GET | `/static/css/custom.css` | anonymous | read / public | [main_server.py:207](main_server.py#L207) |
| GET | `/` | anonymous | read / public | [main_server.py:228](main_server.py#L228) |
| GET | `/health` | anonymous | read / public | [main_server.py:233](main_server.py#L233) |
| GET | `/health` | anonymous | read / public | [REPAIR/app/main.py:52](REPAIR/app/main.py#L52) |
| GET | `/` | anonymous | read / public | [REPAIR/app/main.py:57](REPAIR/app/main.py#L57) |
| POST | `/api/v1/repair/ad/sync-computers` | S | write / branch | [REPAIR/app/routers/ad_computers_router.py:16](REPAIR/app/routers/ad_computers_router.py#L16) |
| GET | `/api/v1/repair/ad/stats` | S/A/T/O/V | read / branch | [REPAIR/app/routers/ad_computers_router.py:40](REPAIR/app/routers/ad_computers_router.py#L40) |
| GET | `/api/v1/repair/models` | S/A/T/O/V/U | read / catalogs | [REPAIR/app/routers/equipment_models_router.py:21](REPAIR/app/routers/equipment_models_router.py#L21) |
| POST | `/api/v1/repair/models/sync-from-ad` | S | write / catalogs | [REPAIR/app/routers/equipment_models_router.py:88](REPAIR/app/routers/equipment_models_router.py#L88) |
| GET | `/api/v1/repair/models/suggest-specs` | S/A/T/O/V/U | read / catalogs | [REPAIR/app/routers/equipment_models_router.py:100](REPAIR/app/routers/equipment_models_router.py#L100) |
| POST | `/api/v1/repair/models` | S | write / catalogs | [REPAIR/app/routers/equipment_models_router.py:138](REPAIR/app/routers/equipment_models_router.py#L138) |
| PUT | `/api/v1/repair/models/{model_id}` | S | write / catalogs | [REPAIR/app/routers/equipment_models_router.py:190](REPAIR/app/routers/equipment_models_router.py#L190) |
| DELETE | `/api/v1/repair/models/{model_id}` | S | write / catalogs | [REPAIR/app/routers/equipment_models_router.py:243](REPAIR/app/routers/equipment_models_router.py#L243) |
| GET | `/api/v1/repair/equipment` | S/A/T/O/V/U | read / branch | [REPAIR/app/routers/equipment_router.py:174](REPAIR/app/routers/equipment_router.py#L174) |
| GET | `/api/v1/repair/equipment/find-by-inv` | S/A/T/O/V/U | read / branch | [REPAIR/app/routers/equipment_router.py:240](REPAIR/app/routers/equipment_router.py#L240) |
| GET | `/api/v1/repair/equipment/ad-users` | S/A/T/O | read / directory | [REPAIR/app/routers/equipment_router.py:341](REPAIR/app/routers/equipment_router.py#L341) |
| GET | `/api/v1/repair/equipment/users/ad` | S/A/T/O | read / directory | [REPAIR/app/routers/equipment_router.py:341](REPAIR/app/routers/equipment_router.py#L341) |
| GET | `/api/v1/repair/equipment/{asset_id}` | S/A/T/O/V/U | read / branch | [REPAIR/app/routers/equipment_router.py:374](REPAIR/app/routers/equipment_router.py#L374) |
| POST | `/api/v1/repair/equipment/accept` | S/A/T/O | write / branch | [REPAIR/app/routers/equipment_router.py:427](REPAIR/app/routers/equipment_router.py#L427) |
| POST | `/api/v1/repair/equipment` | S/A/T/O | write / branch | [REPAIR/app/routers/equipment_router.py:455](REPAIR/app/routers/equipment_router.py#L455) |
| PUT | `/api/v1/repair/equipment/{asset_id}` | S/A/T/O | write / branch | [REPAIR/app/routers/equipment_router.py:502](REPAIR/app/routers/equipment_router.py#L502) |
| POST | `/api/v1/repair/equipment/test-switch-connection` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:570](REPAIR/app/routers/equipment_router.py#L570) |
| POST | `/api/v1/repair/equipment/{asset_id}/sync-switch` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:585](REPAIR/app/routers/equipment_router.py#L585) |
| DELETE | `/api/v1/repair/equipment/{asset_id}` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:615](REPAIR/app/routers/equipment_router.py#L615) |
| POST | `/api/v1/repair/equipment/return-sc` | S/A/T/O | write / branch | [REPAIR/app/routers/equipment_router.py:661](REPAIR/app/routers/equipment_router.py#L661) |
| POST | `/api/v1/repair/equipment/install-workplace` | S/A/T/O | write / branch | [REPAIR/app/routers/equipment_router.py:716](REPAIR/app/routers/equipment_router.py#L716) |
| GET | `/api/v1/repair/batches` | S/A/T/O/V | read / branch | [REPAIR/app/routers/repair_batches_router.py:30](REPAIR/app/routers/repair_batches_router.py#L30) |
| GET | `/api/v1/repair/batches/{batch_id}` | S/A/T/O/V | read / branch | [REPAIR/app/routers/repair_batches_router.py:105](REPAIR/app/routers/repair_batches_router.py#L105) |
| POST | `/api/v1/repair/batches` | S/A/T/O | write / branch | [REPAIR/app/routers/repair_batches_router.py:169](REPAIR/app/routers/repair_batches_router.py#L169) |
| POST | `/api/v1/repair/batches/{batch_id}/close` | S/A/T/O | write / branch | [REPAIR/app/routers/repair_batches_router.py:237](REPAIR/app/routers/repair_batches_router.py#L237) |
| GET | `/print/repair-act/{batch_id}` | S/A/T/O/V | read / branch | [REPAIR/app/routers/repair_print_router.py:30](REPAIR/app/routers/repair_print_router.py#L30) |
| GET | `/api/v1/repair/reports/data` | S/A/T/O/V | read / branch | [REPAIR/app/routers/repair_reports_router.py:17](REPAIR/app/routers/repair_reports_router.py#L17) |
| GET | `/api/v1/repair/reports/export/excel` | S/A/T/O/V | read / branch | [REPAIR/app/routers/repair_reports_router.py:55](REPAIR/app/routers/repair_reports_router.py#L55) |
