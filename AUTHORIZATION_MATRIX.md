# Матрица авторизации и полный реестр HTTP-операций

28.09.2026 · `main@ecd7afa17ec1166b1427ca53b041a8e4e360137f`. Матрица описывает фактический код; не является утверждённой бизнес-политикой. Проверено статически, без runtime-запросов.

## Обозначения и aliases

ANON — нет обязательной authentication; OPTIONAL — токен проверяется, но отсутствие/invalid token даёт anonymous. AUTH — любой активный AppUser, включая `user`, `viewer` и неизвестную строковую роль. S=superadmin, A=admin, O=operator, T=technician. `require_role` дополнительно допускает superadmin. Роль из БД, не доверенная role claim.

Ни app factory, ни include_router, ни mount не добавляют глобальную authentication. Каждый маршрут CARTRIDGE ниже доступен в корне и с префиксом `/cartridges`; REPAIR — в корне и с `/repair`; LOCATION — в корне и с `/location`. Например, `/api/cartridges` и `/cartridges/api/cartridges`, `/print/repair-act/{batch_id}` и `/repair/print/repair-act/{batch_id}`, `/api/v1/location/stats` и `/location/api/v1/location/stats`. Это 99 router declarations × 2 регистрационных пути + 13 прямых app declarations = 211 явно определённых method/path registrations (без framework docs и StaticFiles). На root/mount handlers политика одинакова, CORS различается. Дубли namespace Cartridge не дают дополнительного security boundary.

У module `main.py` строки `/` и `/health` доступны только под своим mount. Root main_server routes — только в корне. FastAPI также по умолчанию создаёт `/docs`, `/redoc`, `/openapi.json`, `/docs/oauth2-redirect` для root и sub-app. StaticFiles доступны анонимно под `/static`, `/cartridges/static`, `/repair/static`, `/location/static`; uploaded maps также публичны. Public UI shell не равнозначен разрешению читать business API.

## Целевая политика (предложение)

| Операция | Public | User | Viewer | Operator | Technician | Branch admin | Superadmin |
|---|---|---|---|---|---|---|---|
| Login, UI assets, минимальный liveness | Да | Да | Да | Да | Да | Да | Да |
| Свои назначенные объекты | Нет | Own | Branch read | Branch | Branch | Branch | Explicit global |
| Чтение чужих объектов/отчётов внутри филиала | Нет | Нет | Разрешённые поля | Да | По домену | Да | Да |
| Cartridge workflow | Нет | Нет | Нет | Branch | Только отдельная permission | Branch | Да |
| Repair workflow | Нет | Нет | Нет | Branch | Branch | Branch | Да |
| Map placement/network poll | Нет | Нет | Нет | Ограниченные команды | Branch | Branch | Да |
| Device credential write / connection target | Нет | Нет | Нет | Нет по умолчанию | Branch + permission | Branch + permission | Да |
| Secret read | Нет | Нет | Нет | Нет | Нет | Нет | Обычно тоже нет; write-only |
| Identity/global settings/branch lifecycle | Нет | Нет | Нет | Нет | Нет | Только делегированные permissions | Да |
| Cross-branch transfer | Нет | Нет | Нет | Нет | Нет | Нет по умолчанию | Отдельная audited permission |
| WA QR/reset | Нет | Нет | Нет | Own instance | Только permission | Own instance | Managed instance |

`branch_id=NULL` не даёт глобальный доступ. Входной branch_id — только selector, пересекаемый с server scope; запрещённый target отклоняется. Для object IDs проверять реальные parents; bulk должен либо целиком разрешаться, либо не менять ничего. AD directory сейчас глобален — target policy требует явно определить, какие сотрудники/поля доступны филиалу. Shared catalogs можно читать глобально, но counts/notes из tenant assets должны фильтроваться. User и Viewer не объединять без решения бизнеса.

## Фактические операции

Колонка «branch от клиента» отмечает direct path/query либо поле request schema (с учётом наследования), а не просто присутствие branch_id в response. «Нет» не означает безопасность: floor_id, asset_id, switch_id, zone_id и batch_id тоже дают доступ к филиалу через объект. Данные в колонке перечисляют чувствительные элементы и побочные эффекты; не каждый response содержит все поля во всех состояниях.


### main_server.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `POST /api/v1/auth/login` | ANON | Нет | Public credential exchange; S01/S02/S11/S12 | JWT и профиль после login | [L76](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/main_server.py#L76) |
| `GET /api/v1/auth/me` | AUTH | Нет | Только текущий principal | Собственный профиль | [L144](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/main_server.py#L144) |
| `GET /static/js/app.js` | ANON | Нет | — | UI/static/health | [L231](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/main_server.py#L231) |
| `GET /static/js/qr-scanner.js` | ANON | Нет | — | UI/static/health | [L235](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/main_server.py#L235) |
| `GET /static/css/custom.css` | ANON | Нет | — | UI/static/health | [L239](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/main_server.py#L239) |
| `GET /` | ANON | Нет | — | UI/static/health | [L260](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/main_server.py#L260) |
| `GET /health` | ANON | Нет | — | UI/static/health | [L265](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/main_server.py#L265) |

### REPAIR/app/main.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /health` | ANON | Нет | — | UI/static/health | [L46](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/main.py#L46) |
| `GET /` | ANON | Нет | — | UI/static/health | [L51](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/main.py#L51) |

### REPAIR/app/routers/ad_computers_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `POST /api/v1/repair/ad/sync-computers` | S,A,T | Да: query | НЕТ branch target check; global sync/NULL backfill | AD computers; может seed demo | [L15](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/ad_computers_router.py#L15) |
| `GET /api/v1/repair/ad/stats` | AUTH | Нет | НЕТ branch scope | Глобальная статистика AD/OS | [L39](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/ad_computers_router.py#L39) |

### REPAIR/app/routers/equipment_models_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/repair/models` | AUTH | Нет | Глобально; counts и notes без tenant scope | Модели, counts; notes могут содержать сводку AD/кабинетов | [L20](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_models_router.py#L20) |
| `POST /api/v1/repair/models/sync-from-ad` | S,A,T | Нет | Глобально; purge models и rename/type update assets | Глобальная модификация реестра | [L87](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_models_router.py#L87) |
| `GET /api/v1/repair/models/suggest-specs` | AUTH | Нет | Глобальные samples без tenant scope | Агрегаты парка и OS | [L99](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_models_router.py#L99) |
| `POST /api/v1/repair/models` | S,A,T | Нет | Глобальный справочник | Модель | [L137](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_models_router.py#L137) |
| `PUT /api/v1/repair/models/{model_id}` | S,A,T | Нет | Глобальный справочник | Модель | [L189](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_models_router.py#L189) |
| `DELETE /api/v1/repair/models/{model_id}` | S,A,T | Нет | Глобальный справочник | Удаление модели | [L242](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_models_router.py#L242) |

### REPAIR/app/routers/equipment_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/repair/equipment` | AUTH | Да: query | Частично чтение, но GET auto-heal всех NULL через client branch | Инвентарь и ПАРОЛЬ коммутатора; S04/S09 | [L176](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L176) |
| `GET /api/v1/repair/equipment/find-by-inv` | AUTH | Нет | НЕТ scope; GET может присвоить владельца | Инвентарь, владелец | [L257](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L257) |
| `GET /api/v1/repair/equipment/ad-users` | AUTH | Нет | Глобальный AD directory | ФИО, логин, кабинет, отдел, телефон | [L385](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L385) |
| `GET /api/v1/repair/equipment/users/ad` | AUTH | Нет | Глобальный AD directory | ФИО, логин, кабинет, отдел, телефон | [L386](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L386) |
| `GET /api/v1/repair/equipment/{asset_id}` | AUTH | Нет | НЕТ object/owner scope | История/спецификации; ПАРОЛЬ switch; S04 | [L419](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L419) |
| `POST /api/v1/repair/equipment/accept` | S,A,T,O | Да: body | НЕТ object scope; client branch приоритетен | Equipment DTO; helper возвращает switch credentials | [L472](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L472) |
| `POST /api/v1/repair/equipment` | S,A,T,O | Да: body | НЕТ branch target check | Equipment DTO с switch config | [L500](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L500) |
| `PUT /api/v1/repair/equipment/{asset_id}` | S,A,T,O | Да: body | НЕТ object/target branch check | Equipment DTO с switch config | [L547](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L547) |
| `POST /api/v1/repair/equipment/test-switch-connection` | S,A,T | Нет | НЕТ inventory/subnet allowlist | Сетевой probe произвольного host/port | [L615](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L615) |
| `POST /api/v1/repair/equipment/{asset_id}/sync-switch` | S,A,T | Нет | НЕТ object branch check | Network poll result; изменяет расположение | [L679](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L679) |
| `DELETE /api/v1/repair/equipment/{asset_id}` | S,A,T | Нет | НЕТ object branch check | Hard delete asset/history/repair parts/items | [L709](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L709) |
| `POST /api/v1/repair/equipment/return-sc` | S,A,T,O | Нет | НЕТ scope по всем asset_ids и repair items | Bulk state/cost update | [L772](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L772) |
| `POST /api/v1/repair/equipment/install-workplace` | S,A,T,O | Нет | НЕТ scope по asset_ids/owner | Bulk state/owner update | [L827](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/equipment_router.py#L827) |

### REPAIR/app/routers/repair_batches_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/repair/batches` | AUTH | Да: query | Частично: assigned branch scoped; NULL global; owner нет | Акты/оборудование/стоимости | [L29](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/repair_batches_router.py#L29) |
| `GET /api/v1/repair/batches/{batch_id}` | AUTH | Нет | НЕТ object branch/owner | Акт/оборудование/стоимости | [L104](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/repair_batches_router.py#L104) |
| `POST /api/v1/repair/batches` | S,A,T,O | Да: body | НЕТ object scope и branch consistency | Акт/чужие assets; состояния изменяются | [L168](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/repair_batches_router.py#L168) |
| `POST /api/v1/repair/batches/{batch_id}/close` | S,A,T,O | Нет | НЕТ object branch и проверки всех returns | Закрытие акта | [L236](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/repair_batches_router.py#L236) |

### REPAIR/app/routers/repair_print_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /print/repair-act/{batch_id}` | ANON | Нет | НЕТ authentication/branch | Акт ремонта с оборудованием/реквизитами | [L28](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/repair_print_router.py#L28) |

### REPAIR/app/routers/repair_reports_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/repair/reports/data` | AUTH | Да: query | Частично: assigned branch scoped; NULL global; личный owner нет | Инвентарь/история/расходы | [L16](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/repair_reports_router.py#L16) |
| `GET /api/v1/repair/reports/export/excel` | AUTH | Да: query | Частично: assigned branch scoped; NULL global; личный owner нет | XLSX с инвентарём/расходами | [L54](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/REPAIR/app/routers/repair_reports_router.py#L54) |

### LOCATION/app/main.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /health` | ANON | Нет | — | UI/static/health | [L41](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/main.py#L41) |
| `GET /` | ANON | Нет | — | UI/static/health | [L46](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/main.py#L46) |

### LOCATION/app/routers/assets_placement_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/location/floors/{floor_id}/assets` | AUTH | Нет | НЕТ floor branch check | Карта, network links, ФИО ответственных | [L111](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/assets_placement_router.py#L111) |
| `GET /api/v1/location/placed-assets` | AUTH | Да: query | Частично: assigned branch scoped; NULL global | Карта/сетевые данные/PII | [L129](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/assets_placement_router.py#L129) |
| `GET /api/v1/location/unplaced-assets` | AUTH | Да: query | Частично: assigned branch scoped; NULL global | Неразмещённые активы/PII | [L168](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/assets_placement_router.py#L168) |
| `POST /api/v1/location/assets/{asset_id}/position` | S,A,T | Нет | НЕТ asset/target floor/zone consistency | Размещение/сетевые данные | [L205](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/assets_placement_router.py#L205) |
| `POST /api/v1/location/assets/{asset_id}/assign-cabinet` | S,A,T,O | Нет | НЕТ asset/target floor/zone consistency | Размещение/сетевые данные | [L232](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/assets_placement_router.py#L232) |
| `POST /api/v1/location/assets/{asset_id}/unplace` | S,A,T | Нет | НЕТ object branch check | Размещение/сетевые данные | [L281](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/assets_placement_router.py#L281) |
| `POST /api/v1/location/assets/create-and-place` | S,A,T,O | Да: body | НЕТ client branch/floor/zone consistency | Новый актив на карте | [L300](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/assets_placement_router.py#L300) |

### LOCATION/app/routers/floors_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/location/branches/{branch_id}/floors` | AUTH | Да: path | НЕТ branch check; GET создаёт floor/demo zones | Этажи/комнаты/ответственные | [L13](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/floors_router.py#L13) |
| `POST /api/v1/location/floors` | S,A | Да: body | НЕТ client branch check | Этаж/зоны | [L117](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/floors_router.py#L117) |
| `PUT /api/v1/location/floors/{floor_id}` | S,A | Нет | НЕТ object branch check | Этаж/зоны | [L137](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/floors_router.py#L137) |
| `DELETE /api/v1/location/floors/{floor_id}` | S,A | Нет | НЕТ object branch check | Удаление/массовое unplace | [L163](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/floors_router.py#L163) |
| `POST /api/v1/location/floors/{floor_id}/upload-map` | S,A | Нет | НЕТ object branch; upload public same-origin | URL публичного файла | [L190](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/floors_router.py#L190) |

### LOCATION/app/routers/pathfinding_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/location/network/trace` | AUTH | Нет | НЕТ scope обоих объектов/общего этажа | Физическая топология | [L14](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/pathfinding_router.py#L14) |
| `GET /api/v1/location/stats` | AUTH | Да: query | НЕТ scope; branch только floors count | Глобальные агрегаты | [L38](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/pathfinding_router.py#L38) |

### LOCATION/app/routers/switches_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/v1/location/floors/{floor_id}/switches` | AUTH | Нет | НЕТ floor branch check | IP/порты/SNMP community/extra_params | [L80](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L80) |
| `POST /api/v1/location/switches` | S,A,T | Да: body | НЕТ branch/floor consistency | Switch response с community/extra_params | [L96](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L96) |
| `PUT /api/v1/location/switches/{switch_id}` | S,A,T | Нет | НЕТ object branch check | Switch response с community/extra_params | [L166](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L166) |
| `POST /api/v1/location/switches/test-connection` | S,A,T,O | Нет | НЕТ inventory/subnet allowlist | Сетевой probe произвольного host/port | [L219](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L219) |
| `DELETE /api/v1/location/switches/{switch_id}` | S,A,T | Нет | НЕТ object branch check | Удаление switch/asset/history | [L239](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L239) |
| `PUT /api/v1/location/switches/{switch_id}/ports/{port_number}` | S,A,T,O | Нет | НЕТ switch/zone/asset scope; может создать порт | Топология/связанные активы | [L270](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L270) |
| `POST /api/v1/location/switches/{switch_id}/ports/{port_number}/connect` | S,A,T | Нет | НЕТ scope switch и target asset | Изменение связи | [L337](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L337) |
| `POST /api/v1/location/switches/{switch_id}/poll` | S,A,T,O | Нет | НЕТ object branch; global MAC matching | Network observations/перемещения | [L360](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L360) |
| `POST /api/v1/location/switches/{switch_id}/simulate-event` | S,A,T | Нет | НЕТ object branch; demo пишет реальные данные | Перемещения активов | [L379](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/switches_router.py#L379) |

### LOCATION/app/routers/zones_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `POST /api/v1/location/floors/{floor_id}/zones` | S,A,T | Нет | НЕТ floor branch check | Новая зона/ответственный | [L12](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/zones_router.py#L12) |
| `DELETE /api/v1/location/zones/{zone_id}` | S,A | Нет | НЕТ zone branch check | Удаление зоны | [L40](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/LOCATION/app/routers/zones_router.py#L40) |

### CARTRIDGE/app/main.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /health` | ANON | Нет | — | UI/static/health | [L68](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/main.py#L68) |
| `GET /` | ANON | Нет | — | UI/static/health | [L73](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/main.py#L73) |

### CARTRIDGE/app/routers/app_users_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/app-users` | S | Нет | Глобально; superadmin | Учётки, роли, филиалы | [L13](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/app_users_router.py#L13) |
| `POST /api/app-users` | S | Да: body | Глобально; branch существует; role/auth_type произвольные строки | Профиль учётки | [L24](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/app_users_router.py#L24) |
| `PUT /api/app-users/{user_id}` | S | Да: body | Глобально; branch существует; особые запреты для admin | Профиль учётки | [L65](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/app_users_router.py#L65) |
| `DELETE /api/app-users/{user_id}` | S | Нет | Глобально; нельзя удалить себя/admin | Результат удаления | [L110](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/app_users_router.py#L110) |
| `POST /api/app-users/{user_id}/toggle-active` | S | Нет | Глобально; admin защищён | Состояние учётки | [L132](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/app_users_router.py#L132) |

### CARTRIDGE/app/routers/auth_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `POST /api/auth/login` | ANON | Нет | Public credential exchange; S01/S02/S11/S12 | JWT и профиль после login | [L12](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/auth_router.py#L12) |
| `GET /api/auth/me` | AUTH | Нет | Только текущий principal | Собственный профиль | [L48](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/auth_router.py#L48) |

### CARTRIDGE/app/routers/batches_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/batches` | S,A,O | Да: query | Да: non-superadmin только branch, NULL даёт пустой список | Акты, связанные картриджи/владельцы | [L15](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/batches_router.py#L15) |
| `GET /api/batches/{batch_id}` | S,A,O | Нет | Частично: чужой branch запрещён, но NULL membership обходит | Акт и связанные картриджи/владельцы | [L40](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/batches_router.py#L40) |
| `POST /api/batches` | S,A,O | Да: body | Да для найденных объектов: forced own branch; NULL запрещён; missing IDs не полностью проверены | Акт; global superadmin может mixed branch | [L61](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/batches_router.py#L61) |

### CARTRIDGE/app/routers/branches_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/branches` | ANON | Нет | НЕТ scope; все филиалы | Адреса, IT-office, notes, WA template | [L13](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/branches_router.py#L13) |
| `POST /api/branches` | S,A | Нет | Глобальная операция доступна branch admin | Branch DTO | [L19](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/branches_router.py#L19) |
| `PUT /api/branches/{branch_id}` | S,A | Да: path | НЕТ проверки целевого филиала | Branch DTO | [L45](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/branches_router.py#L45) |
| `DELETE /api/branches/{branch_id}` | S,A | Да: path | НЕТ проверки целевого филиала; проверены только cartridges | Удаление филиала, отвязка пользователей | [L80](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/branches_router.py#L80) |

### CARTRIDGE/app/routers/cartridges_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/cartridges` | OPTIONAL | Да: query | Частично: user owner по ilike; admin/operator с branch scoped; anonymous/viewer/NULL global | Инвентарь, ФИО/телефон владельца, филиал | [L28](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L28) |
| `GET /api/cartridges/search/quick` | ANON | Нет | НЕТ auth/ownership | Cartridge DTO с владельцем | [L80](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L80) |
| `GET /api/cartridges/{cartridge_id}` | OPTIONAL | Нет | Owner только для role=user; anonymous/прочие без object scope | Владелец, история, notes | [L107](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L107) |
| `POST /api/cartridges` | S,A,O | Да: body | НЕТ; payload.branch_id доверен | Cartridge DTO | [L134](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L134) |
| `PUT /api/cartridges/{cartridge_id}` | S,A,O | Да: body | НЕТ; смена branch/owner/status по payload | Cartridge DTO | [L176](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L176) |
| `DELETE /api/cartridges/{cartridge_id}` | S,A | Нет | НЕТ object scope | Удаление объекта/истории | [L235](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L235) |
| `POST /api/cartridges/accept` | S,A,O | Да: body | НЕТ; поиск marker глобален; branch из payload | Cartridge DTO | [L250](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L250) |
| `POST /api/cartridges/{cartridge_id}/issue` | S,A,O | Нет | НЕТ object scope и state gate | Результат изменения | [L327](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L327) |
| `POST /api/cartridges/bulk-issue` | S,A,O | Нет | НЕТ scope всех IDs; missing IDs пропускаются | Результат массовой операции | [L364](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L364) |
| `POST /api/cartridges/return-vendor` | S,A,O | Нет | НЕТ scope всех IDs | Результат массовой операции | [L406](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/cartridges_router.py#L406) |

### CARTRIDGE/app/routers/models_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/cartridge-models` | S,A,O | Нет | Справочник глобальный; counts по всем филиалам | Модели и глобальные количества | [L14](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/models_router.py#L14) |
| `POST /api/cartridge-models` | S,A | Нет | Глобальный справочник; отдельная permission отсутствует | Модель | [L48](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/models_router.py#L48) |
| `PUT /api/cartridge-models/{model_id}` | S,A | Нет | Глобальный справочник; отдельная permission отсутствует | Модель и глобальный count | [L79](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/models_router.py#L79) |
| `DELETE /api/cartridge-models/{model_id}` | S,A | Нет | Глобальный справочник; count-use check | Результат удаления | [L124](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/models_router.py#L124) |

### CARTRIDGE/app/routers/notifications_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `POST /api/notifications/whatsapp/ready` | S,A,O | Нет | НЕТ recipient/object branch scope; пустые IDs = все ready | ФИО, телефоны, инвентарь; внешняя отправка | [L16](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/notifications_router.py#L16) |

### CARTRIDGE/app/routers/print_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /print/act/{batch_id}` | ANON | Нет | НЕТ authentication/branch | Акт с инвентарём/реквизитами | [L31](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/print_router.py#L31) |

### CARTRIDGE/app/routers/reports_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/reports/data` | S,A,O | Да: query | Частично в service: assigned admin/operator scoped; NULL global | Инвентарь, владельцы/телефоны, история | [L17](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/reports_router.py#L17) |
| `GET /api/reports/export/excel` | S,A,O | Да: query | Частично в service: assigned admin/operator scoped; NULL global | XLSX с инвентарём/PII | [L50](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/reports_router.py#L50) |
| `GET /api/reports/export/pdf` | S,A,O | Да: query | Частично в service: assigned admin/operator scoped; NULL global | PDF с инвентарём/PII | [L101](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/reports_router.py#L101) |

### CARTRIDGE/app/routers/settings_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/settings` | OPTIONAL | Нет | Публично; маскируются только 2 ключа для non-superadmin | LDAP host/DN/user, WA URL; superadmin получает secrets | [L20](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L20) |
| `POST /api/settings` | S | Нет | Глобально superadmin; произвольные settings keys | Updated settings, включая секреты | [L35](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L35) |
| `PUT /api/settings` | S | Нет | Глобально superadmin; произвольные settings keys | Updated settings, включая секреты | [L36](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L36) |
| `POST /api/settings/ldap/test` | S | Нет | Глобально superadmin; host задаёт клиент | Результат соединения/ошибки | [L53](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L53) |
| `POST /api/settings/ldap/sync` | S | Нет | Глобально superadmin | Результат sync AD | [L70](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L70) |
| `POST /api/settings/ad-sync` | S | Нет | Глобально superadmin | Результат sync AD | [L71](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L71) |
| `GET /api/settings/wa/status` | S,A,O | Нет | Non-superadmin instance принудительно own/shared; superadmin любой | Instance connection status | [L81](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L81) |
| `GET /api/settings/wa/operators-status` | S | Нет | Глобально superadmin | Аккаунты/статусы всех операторов | [L108](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L108) |
| `POST /api/settings/wa/qr` | S,A,O | Нет | Да: non-superadmin только own instance/user; superadmin любой | QR/pairing — sensitive session material; возможен recreate | [L117](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L117) |
| `POST /api/settings/wa/reset` | S,A,O | Нет | Да: non-superadmin только own instance/user; superadmin любой | Удаление/пересоздание session, QR | [L154](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L154) |
| `POST /api/settings/wa/test` | S,A,O | Нет | Instance own/shared; phone/message произвольны, recipient scope отсутствует | Внешняя отправка, result/error | [L189](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/settings_router.py#L189) |

### CARTRIDGE/app/routers/users_router.py

| Method / path | Auth | branch от клиента | Scope / ownership фактически | Данные / эффект | Код |
|---|---|---|---|---|---|
| `GET /api/users` | S,A,O | Нет | Глобальный AD directory без tenant relation | ФИО, логин, кабинет, отдел, телефон | [L13](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/users_router.py#L13) |
| `GET /api/users/ad` | S,A,O | Нет | Глобальный AD directory без tenant relation | ФИО, логин, кабинет, отдел, телефон | [L14](https://github.com/ZQRey/REP_ZAP_INV/blob/ecd7afa17ec1166b1427ca53b041a8e4e360137f/CARTRIDGE/app/routers/users_router.py#L14) |

## Обязательные отрицательные сценарии

Для каждой business row: anonymous; invalid/expired JWT; disabled user; role=user/viewer/unknown; branch A→B; user.branch=NULL; object.branch=NULL; bulk A+B+missing ID; несогласованные floor/zone/branch; прямой root и mounted alias; stale token после смены membership/password. Expected denial проверяется вместе с отсутствием DB/external effects. Для print/download не использовать долгоживущий query token. Для business read проверить отсутствие секретов рекурсивно во вложенных DTO.

Публичные бизнес-операции: GET `/api/branches`, `/api/settings`, `/api/cartridges`, `/api/cartridges/search/quick`, `/api/cartridges/{cartridge_id}`, `/print/act/{batch_id}`, `/print/repair-act/{batch_id}` и соответствующие mount aliases. Login/UI/health/docs являются отдельными намеренно публичными категориями; они не должны автоматически считаться уязвимостью.
