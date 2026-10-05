# Authorization matrix

Актуальные ограничения реализованы в `SHARED/policies/endpoints.json` и применяются до вызова обработчика, включая самостоятельные модули и общий сервер. SQL scope ограничивает вложенные объекты и агрегаты тем же филиалом.

S = superadmin; A = admin; T = technician; O = operator; V = viewer; U = user.

| Роль | Доступ |
|---|---|
| S | Все филиалы, все разрешённые операции и настройки |
| A | Управление картриджами, ремонтом и картой только филиала из профиля; управление нижестоящими пользователями своего филиала |
| O | Только просмотр и экспорт отчётов картриджей, ремонтов и карты в своём филиале; нет реестров, редактора карты, опроса сети, настроек и операций записи |
| U | Текущее состояние только собственных картриджей; история, внутренние примечания, отчёты, ремонт и карта недоступны |
| T/V | Доступ по точному реестру ниже; изоляция своего филиала сохраняется |

Для всех ролей разрешены собственный профиль и смена собственного пароля. Первоначальный пароль блокирует бизнес API до обязательной смены. Branchless staff не получает доступ к данным филиалов. Обычный пользователь может читать собственные картриджи по логину без назначенного филиала. Новые HTTP endpoints без явной политики запрещены. Настройки сети и секреты не доступны оператору; секреты не возвращаются в HTTP ответах.

Отчёт карты содержит местоположение, MAC, технику, коммутатор, порт, розетку, VLAN и время наблюдения. Для неуправляемого свича сохраняются название, произвольное число портов (включая 28) и ручные MAC→порт привязки. Межкоммутаторный канал не является местом автоматического перемещения техники. Неоднозначные MAC не устанавливают идентичность техники.

Подробное описание механизмов: [AUTHORIZATION_ARCHITECTURE.md](AUTHORIZATION_ARCHITECTURE.md).

## Полный реестр HTTP операций

120 source declarations; 117 handler/method policies.

| Method | Path | Roles | Action / scope | Source |
|---|---|---|---|---|
| GET | `/health` | anonymous | read / global | [CARTRIDGE/app/main.py:72](CARTRIDGE/app/main.py#L72) |
| GET | `/` | anonymous | read / global | [CARTRIDGE/app/main.py:77](CARTRIDGE/app/main.py#L77) |
| GET | `/api/app-users` | S/A | read / branch | [CARTRIDGE/app/routers/app_users_router.py:17](CARTRIDGE/app/routers/app_users_router.py#L17) |
| POST | `/api/app-users` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:31](CARTRIDGE/app/routers/app_users_router.py#L31) |
| PUT | `/api/app-users/{user_id}` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:86](CARTRIDGE/app/routers/app_users_router.py#L86) |
| DELETE | `/api/app-users/{user_id}` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:152](CARTRIDGE/app/routers/app_users_router.py#L152) |
| POST | `/api/app-users/{user_id}/toggle-active` | S/A | write / branch | [CARTRIDGE/app/routers/app_users_router.py:181](CARTRIDGE/app/routers/app_users_router.py#L181) |
| POST | `/api/auth/login` | anonymous | write / global | [CARTRIDGE/app/routers/auth_router.py:14](CARTRIDGE/app/routers/auth_router.py#L14) |
| GET | `/api/auth/me` | S/A/T/O/V/U | read / global | [CARTRIDGE/app/routers/auth_router.py:52](CARTRIDGE/app/routers/auth_router.py#L52) |
| GET | `/api/batches` | S/A/T/V | read / branch | [CARTRIDGE/app/routers/batches_router.py:18](CARTRIDGE/app/routers/batches_router.py#L18) |
| GET | `/api/batches/{batch_id}` | S/A/T/V | read / branch | [CARTRIDGE/app/routers/batches_router.py:43](CARTRIDGE/app/routers/batches_router.py#L43) |
| POST | `/api/batches` | S/A | write / branch | [CARTRIDGE/app/routers/batches_router.py:64](CARTRIDGE/app/routers/batches_router.py#L64) |
| GET | `/api/branches` | S/A/T/O/V/U | read / branch | [CARTRIDGE/app/routers/branches_router.py:14](CARTRIDGE/app/routers/branches_router.py#L14) |
| POST | `/api/branches` | S | write / branch | [CARTRIDGE/app/routers/branches_router.py:20](CARTRIDGE/app/routers/branches_router.py#L20) |
| PUT | `/api/branches/{branch_id}` | S/A | write / branch | [CARTRIDGE/app/routers/branches_router.py:46](CARTRIDGE/app/routers/branches_router.py#L46) |
| DELETE | `/api/branches/{branch_id}` | S | write / branch | [CARTRIDGE/app/routers/branches_router.py:81](CARTRIDGE/app/routers/branches_router.py#L81) |
| GET | `/api/cartridges` | S/A/T/V/U | read / branch | [CARTRIDGE/app/routers/cartridges_router.py:26](CARTRIDGE/app/routers/cartridges_router.py#L26) |
| GET | `/api/cartridges/search/quick` | S/A/T/V/U | read / branch | [CARTRIDGE/app/routers/cartridges_router.py:63](CARTRIDGE/app/routers/cartridges_router.py#L63) |
| GET | `/api/cartridges/{cartridge_id}` | S/A/T/V | read / branch | [CARTRIDGE/app/routers/cartridges_router.py:90](CARTRIDGE/app/routers/cartridges_router.py#L90) |
| POST | `/api/cartridges` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:109](CARTRIDGE/app/routers/cartridges_router.py#L109) |
| PUT | `/api/cartridges/{cartridge_id}` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:151](CARTRIDGE/app/routers/cartridges_router.py#L151) |
| DELETE | `/api/cartridges/{cartridge_id}` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:213](CARTRIDGE/app/routers/cartridges_router.py#L213) |
| POST | `/api/cartridges/accept` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:228](CARTRIDGE/app/routers/cartridges_router.py#L228) |
| POST | `/api/cartridges/{cartridge_id}/issue` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:308](CARTRIDGE/app/routers/cartridges_router.py#L308) |
| POST | `/api/cartridges/bulk-issue` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:348](CARTRIDGE/app/routers/cartridges_router.py#L348) |
| POST | `/api/cartridges/return-vendor` | S/A | write / branch | [CARTRIDGE/app/routers/cartridges_router.py:392](CARTRIDGE/app/routers/cartridges_router.py#L392) |
| GET | `/api/cartridge-models` | S/A/T/V/U | read / global | [CARTRIDGE/app/routers/models_router.py:15](CARTRIDGE/app/routers/models_router.py#L15) |
| POST | `/api/cartridge-models` | S | write / global | [CARTRIDGE/app/routers/models_router.py:49](CARTRIDGE/app/routers/models_router.py#L49) |
| PUT | `/api/cartridge-models/{model_id}` | S | write / global | [CARTRIDGE/app/routers/models_router.py:80](CARTRIDGE/app/routers/models_router.py#L80) |
| DELETE | `/api/cartridge-models/{model_id}` | S | write / global | [CARTRIDGE/app/routers/models_router.py:125](CARTRIDGE/app/routers/models_router.py#L125) |
| POST | `/api/notifications/whatsapp/ready` | S/A | write / branch | [CARTRIDGE/app/routers/notifications_router.py:19](CARTRIDGE/app/routers/notifications_router.py#L19) |
| GET | `/print/act/{batch_id}` | S/A/T/V | read / branch | [CARTRIDGE/app/routers/print_router.py:33](CARTRIDGE/app/routers/print_router.py#L33) |
| GET | `/api/reports/data` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/reports_router.py:18](CARTRIDGE/app/routers/reports_router.py#L18) |
| GET | `/api/reports/export/excel` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/reports_router.py:51](CARTRIDGE/app/routers/reports_router.py#L51) |
| GET | `/api/reports/export/pdf` | S/A/T/O/V | read / branch | [CARTRIDGE/app/routers/reports_router.py:102](CARTRIDGE/app/routers/reports_router.py#L102) |
| GET | `/api/settings` | S/A/T/V/U | read / global | [CARTRIDGE/app/routers/settings_router.py:17](CARTRIDGE/app/routers/settings_router.py#L17) |
| POST | `/api/settings` | S | write / global | [CARTRIDGE/app/routers/settings_router.py:28](CARTRIDGE/app/routers/settings_router.py#L28) |
| PUT | `/api/settings` | S | write / global | [CARTRIDGE/app/routers/settings_router.py:28](CARTRIDGE/app/routers/settings_router.py#L28) |
| POST | `/api/settings/ldap/test` | S | write / global | [CARTRIDGE/app/routers/settings_router.py:47](CARTRIDGE/app/routers/settings_router.py#L47) |
| POST | `/api/settings/ldap/sync` | S | write / global | [CARTRIDGE/app/routers/settings_router.py:68](CARTRIDGE/app/routers/settings_router.py#L68) |
| POST | `/api/settings/ad-sync` | S | write / global | [CARTRIDGE/app/routers/settings_router.py:68](CARTRIDGE/app/routers/settings_router.py#L68) |
| GET | `/api/settings/wa/status` | S/A | wa_self / branch | [CARTRIDGE/app/routers/settings_router.py:78](CARTRIDGE/app/routers/settings_router.py#L78) |
| GET | `/api/settings/wa/operators-status` | S | read / global | [CARTRIDGE/app/routers/settings_router.py:105](CARTRIDGE/app/routers/settings_router.py#L105) |
| POST | `/api/settings/wa/qr` | S/A | wa_self / branch | [CARTRIDGE/app/routers/settings_router.py:114](CARTRIDGE/app/routers/settings_router.py#L114) |
| POST | `/api/settings/wa/reset` | S/A | wa_self / branch | [CARTRIDGE/app/routers/settings_router.py:151](CARTRIDGE/app/routers/settings_router.py#L151) |
| POST | `/api/settings/wa/test` | S | write / global | [CARTRIDGE/app/routers/settings_router.py:186](CARTRIDGE/app/routers/settings_router.py#L186) |
| GET | `/api/users` | S/A/T | read / global | [CARTRIDGE/app/routers/users_router.py:15](CARTRIDGE/app/routers/users_router.py#L15) |
| GET | `/api/users/ad` | S/A/T | read / global | [CARTRIDGE/app/routers/users_router.py:15](CARTRIDGE/app/routers/users_router.py#L15) |
| GET | `/health` | anonymous | read / global | [LOCATION/app/main.py:50](LOCATION/app/main.py#L50) |
| GET | `/` | anonymous | read / global | [LOCATION/app/main.py:55](LOCATION/app/main.py#L55) |
| GET | `/api/v1/location/floors/{floor_id}/assets` | S/A/T/V | read / branch | [LOCATION/app/routers/assets_placement_router.py:124](LOCATION/app/routers/assets_placement_router.py#L124) |
| GET | `/api/v1/location/placed-assets` | S/A/T/V | read / branch | [LOCATION/app/routers/assets_placement_router.py:142](LOCATION/app/routers/assets_placement_router.py#L142) |
| GET | `/api/v1/location/unplaced-assets` | S/A/T/V | read / branch | [LOCATION/app/routers/assets_placement_router.py:181](LOCATION/app/routers/assets_placement_router.py#L181) |
| POST | `/api/v1/location/assets/{asset_id}/position` | S/A/T | write / branch | [LOCATION/app/routers/assets_placement_router.py:218](LOCATION/app/routers/assets_placement_router.py#L218) |
| POST | `/api/v1/location/assets/{asset_id}/assign-cabinet` | S/A/T | write / branch | [LOCATION/app/routers/assets_placement_router.py:245](LOCATION/app/routers/assets_placement_router.py#L245) |
| POST | `/api/v1/location/assets/{asset_id}/unplace` | S/A/T | write / branch | [LOCATION/app/routers/assets_placement_router.py:294](LOCATION/app/routers/assets_placement_router.py#L294) |
| POST | `/api/v1/location/assets/create-and-place` | S/A/T | write / branch | [LOCATION/app/routers/assets_placement_router.py:313](LOCATION/app/routers/assets_placement_router.py#L313) |
| GET | `/api/v1/location/floors/{floor_id}/map` | S/A/T/V | read / branch | [LOCATION/app/routers/floors_router.py:15](LOCATION/app/routers/floors_router.py#L15) |
| GET | `/api/v1/location/branches/{branch_id}/floors` | S/A/T/V | read / branch | [LOCATION/app/routers/floors_router.py:34](LOCATION/app/routers/floors_router.py#L34) |
| POST | `/api/v1/location/floors` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:46](LOCATION/app/routers/floors_router.py#L46) |
| PUT | `/api/v1/location/floors/{floor_id}` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:66](LOCATION/app/routers/floors_router.py#L66) |
| DELETE | `/api/v1/location/floors/{floor_id}` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:92](LOCATION/app/routers/floors_router.py#L92) |
| POST | `/api/v1/location/floors/{floor_id}/upload-map` | S/A | write / branch | [LOCATION/app/routers/floors_router.py:119](LOCATION/app/routers/floors_router.py#L119) |
| GET | `/api/v1/location/network/trace` | S/A/T/V | read / branch | [LOCATION/app/routers/pathfinding_router.py:15](LOCATION/app/routers/pathfinding_router.py#L15) |
| GET | `/api/v1/location/stats` | S/A/T/V | read / branch | [LOCATION/app/routers/pathfinding_router.py:39](LOCATION/app/routers/pathfinding_router.py#L39) |
| GET | `/api/v1/location/reports` | S/A/T/O/V | read / branch | [LOCATION/app/routers/reports_router.py:77](LOCATION/app/routers/reports_router.py#L77) |
| GET | `/api/v1/location/reports/csv` | S/A/T/O/V | read / branch | [LOCATION/app/routers/reports_router.py:83](LOCATION/app/routers/reports_router.py#L83) |
| GET | `/api/v1/location/floors/{floor_id}/switches` | S/A/T/V | read / branch | [LOCATION/app/routers/switches_router.py:94](LOCATION/app/routers/switches_router.py#L94) |
| POST | `/api/v1/location/switches` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:110](LOCATION/app/routers/switches_router.py#L110) |
| PUT | `/api/v1/location/switches/{switch_id}` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:182](LOCATION/app/routers/switches_router.py#L182) |
| POST | `/api/v1/location/switches/test-connection` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:240](LOCATION/app/routers/switches_router.py#L240) |
| DELETE | `/api/v1/location/switches/{switch_id}` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:260](LOCATION/app/routers/switches_router.py#L260) |
| PUT | `/api/v1/location/switches/{switch_id}/ports/{port_number}` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:291](LOCATION/app/routers/switches_router.py#L291) |
| POST | `/api/v1/location/switches/{switch_id}/ports/{port_number}/connect` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:368](LOCATION/app/routers/switches_router.py#L368) |
| POST | `/api/v1/location/switches/{switch_id}/poll` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:391](LOCATION/app/routers/switches_router.py#L391) |
| POST | `/api/v1/location/switches/{switch_id}/simulate-event` | S/A/T | write / branch | [LOCATION/app/routers/switches_router.py:411](LOCATION/app/routers/switches_router.py#L411) |
| POST | `/api/v1/location/floors/{floor_id}/zones` | S/A/T | write / branch | [LOCATION/app/routers/zones_router.py:13](LOCATION/app/routers/zones_router.py#L13) |
| DELETE | `/api/v1/location/zones/{zone_id}` | S/A | write / branch | [LOCATION/app/routers/zones_router.py:42](LOCATION/app/routers/zones_router.py#L42) |
| PUT | `/api/v1/location/zones/{zone_id}` | S/A/T | write / branch | [LOCATION/app/routers/zones_router.py:59](LOCATION/app/routers/zones_router.py#L59) |
| POST | `/api/v1/auth/login` | anonymous | write / global | [main_server.py:79](main_server.py#L79) |
| GET | `/api/v1/auth/me` | S/A/T/O/V/U | read / global | [main_server.py:115](main_server.py#L115) |
| POST | `/api/v1/auth/change-password` | S/A/T/O/V/U | password_self / global | [main_server.py:135](main_server.py#L135) |
| GET | `/static/js/app.js` | anonymous | read / global | [main_server.py:225](main_server.py#L225) |
| GET | `/static/js/qr-scanner.js` | anonymous | read / global | [main_server.py:229](main_server.py#L229) |
| GET | `/static/css/custom.css` | anonymous | read / global | [main_server.py:233](main_server.py#L233) |
| GET | `/` | anonymous | read / global | [main_server.py:254](main_server.py#L254) |
| GET | `/health` | anonymous | read / global | [main_server.py:259](main_server.py#L259) |
| GET | `/health` | anonymous | read / global | [REPAIR/app/main.py:52](REPAIR/app/main.py#L52) |
| GET | `/` | anonymous | read / global | [REPAIR/app/main.py:57](REPAIR/app/main.py#L57) |
| POST | `/api/v1/repair/ad/sync-computers` | S | write / branch | [REPAIR/app/routers/ad_computers_router.py:16](REPAIR/app/routers/ad_computers_router.py#L16) |
| GET | `/api/v1/repair/ad/stats` | S/A/T/V | read / branch | [REPAIR/app/routers/ad_computers_router.py:40](REPAIR/app/routers/ad_computers_router.py#L40) |
| GET | `/api/v1/repair/models` | S/A/T/V | read / global | [REPAIR/app/routers/equipment_models_router.py:21](REPAIR/app/routers/equipment_models_router.py#L21) |
| POST | `/api/v1/repair/models/sync-from-ad` | S | write / global | [REPAIR/app/routers/equipment_models_router.py:88](REPAIR/app/routers/equipment_models_router.py#L88) |
| GET | `/api/v1/repair/models/suggest-specs` | S/A/T/V | read / global | [REPAIR/app/routers/equipment_models_router.py:100](REPAIR/app/routers/equipment_models_router.py#L100) |
| POST | `/api/v1/repair/models` | S | write / global | [REPAIR/app/routers/equipment_models_router.py:138](REPAIR/app/routers/equipment_models_router.py#L138) |
| PUT | `/api/v1/repair/models/{model_id}` | S | write / global | [REPAIR/app/routers/equipment_models_router.py:190](REPAIR/app/routers/equipment_models_router.py#L190) |
| DELETE | `/api/v1/repair/models/{model_id}` | S | write / global | [REPAIR/app/routers/equipment_models_router.py:243](REPAIR/app/routers/equipment_models_router.py#L243) |
| GET | `/api/v1/repair/equipment` | S/A/T/V | read / branch | [REPAIR/app/routers/equipment_router.py:175](REPAIR/app/routers/equipment_router.py#L175) |
| GET | `/api/v1/repair/equipment/find-by-inv` | S/A/T/V | read / branch | [REPAIR/app/routers/equipment_router.py:241](REPAIR/app/routers/equipment_router.py#L241) |
| GET | `/api/v1/repair/equipment/ad-users` | S/A/T | read / global | [REPAIR/app/routers/equipment_router.py:342](REPAIR/app/routers/equipment_router.py#L342) |
| GET | `/api/v1/repair/equipment/users/ad` | S/A/T | read / global | [REPAIR/app/routers/equipment_router.py:342](REPAIR/app/routers/equipment_router.py#L342) |
| GET | `/api/v1/repair/equipment/{asset_id}` | S/A/T/V | read / branch | [REPAIR/app/routers/equipment_router.py:375](REPAIR/app/routers/equipment_router.py#L375) |
| POST | `/api/v1/repair/equipment/accept` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:428](REPAIR/app/routers/equipment_router.py#L428) |
| POST | `/api/v1/repair/equipment` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:456](REPAIR/app/routers/equipment_router.py#L456) |
| PUT | `/api/v1/repair/equipment/{asset_id}` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:505](REPAIR/app/routers/equipment_router.py#L505) |
| POST | `/api/v1/repair/equipment/test-switch-connection` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:576](REPAIR/app/routers/equipment_router.py#L576) |
| POST | `/api/v1/repair/equipment/{asset_id}/sync-switch` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:591](REPAIR/app/routers/equipment_router.py#L591) |
| DELETE | `/api/v1/repair/equipment/{asset_id}` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:621](REPAIR/app/routers/equipment_router.py#L621) |
| POST | `/api/v1/repair/equipment/return-sc` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:667](REPAIR/app/routers/equipment_router.py#L667) |
| POST | `/api/v1/repair/equipment/install-workplace` | S/A/T | write / branch | [REPAIR/app/routers/equipment_router.py:730](REPAIR/app/routers/equipment_router.py#L730) |
| GET | `/api/v1/repair/batches` | S/A/T/V | read / branch | [REPAIR/app/routers/repair_batches_router.py:31](REPAIR/app/routers/repair_batches_router.py#L31) |
| GET | `/api/v1/repair/batches/{batch_id}` | S/A/T/V | read / branch | [REPAIR/app/routers/repair_batches_router.py:106](REPAIR/app/routers/repair_batches_router.py#L106) |
| POST | `/api/v1/repair/batches` | S/A/T | write / branch | [REPAIR/app/routers/repair_batches_router.py:170](REPAIR/app/routers/repair_batches_router.py#L170) |
| POST | `/api/v1/repair/batches/{batch_id}/close` | S/A/T | write / branch | [REPAIR/app/routers/repair_batches_router.py:240](REPAIR/app/routers/repair_batches_router.py#L240) |
| GET | `/print/repair-act/{batch_id}` | S/A/T/V | read / branch | [REPAIR/app/routers/repair_print_router.py:30](REPAIR/app/routers/repair_print_router.py#L30) |
| GET | `/api/v1/repair/reports/data` | S/A/T/O/V | read / branch | [REPAIR/app/routers/repair_reports_router.py:17](REPAIR/app/routers/repair_reports_router.py#L17) |
| GET | `/api/v1/repair/reports/export/excel` | S/A/T/O/V | read / branch | [REPAIR/app/routers/repair_reports_router.py:55](REPAIR/app/routers/repair_reports_router.py#L55) |
| GET | `/api/v1/auth/sso/status` | anonymous | read / global | [SHARED/domain_sso.py:77](SHARED/domain_sso.py#L77) |
| GET | `/api/v1/auth/sso` | anonymous | read / global | [SHARED/domain_sso.py:90](SHARED/domain_sso.py#L90) |
| POST | `/api/v1/auth/sso/keytab` | S | write / global | [SHARED/domain_sso.py:120](SHARED/domain_sso.py#L120) |
