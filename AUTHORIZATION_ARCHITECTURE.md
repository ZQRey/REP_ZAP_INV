# Единая архитектура authorization

## Поток запроса

`Bearer JWT → active AppUser → immutable Principal → endpoint policy → branch/object scope → service → scoped Session`

1. `SHARED/authentication.py` содержит единственный `HTTPBearer`, проверку JWT и загрузку активной учетной записи. Роль и филиал берутся из БД при каждом запросе; одноименные claims JWT не дают полномочий. Неизвестная роль запрещена. Старые импорты authentication оставлены только как совместимые aliases.
2. `SHARED/policies/endpoints.json` явно задаёт роли, действие, область и сетевые полномочия каждого обработчика/метода. Политика применяется общей dependency всех четырех FastAPI applications. Отсутствующая политика означает 403. Aliases одного обработчика наследуют ту же политику; перечень aliases проверяется отдельно.
3. `SHARED/policies/http.py` проверяет path/query/body IDs, выбор филиала, пользователей, сетевые адреса и владение WhatsApp instance **до** вызова бизнес-обработчика. Bulk-запрос проверяет каждый ID, включая `item_ids`; частичная обработка разрешенной части запрещена. HTTPBearer передает credentials только заголовком; прежний запрет `?token=` сохранён.
4. `SHARED/policies/core.py` задаёт immutable `Principal`, `require_branch_access`, `require_object_access`, правила администрирования и scope всех 23 моделей. `require_authenticated_user`, `require_role`, `require_superadmin` экспортируются из `SHARED/authentication.py`.
5. `SHARED/policies/session.py` применяет SQLAlchemy `with_loader_criteria` к SELECT, aliases, aggregates, eager/lazy relationships. Поэтому scope работает также внутри reports, statistics, network services и print endpoints. `before_flush` проверяет записи и связи; bulk DML имеет отдельные ограничения. Внешние object ID проверяются явным запросом, а не `Session.get`, способным вернуть ранее кешированный объект.

Используется прежняя canonical `SHARED.database.get_db`: один Session на запрос, rollback при ошибке, обязательное закрытие. Новых Base, engine, session factory или изменений схемы нет.

## Политика филиалов и объектов

- Все роли кроме superadmin ограничены своим ненулевым `AppUser.branch_id`. Отсутствие филиала не означает глобальный доступ. Профиль и разрешённые глобальные справочники доступны отдельно от branch API.
- Обычный пользователь не может выбрать чужой филиал через query/path/body. Для создания пропущенный/null branch заполняется сервером. Нулевые/отрицательные selectors глобального доступа запрещены обычным пользователям.
- Роль `user` читает только свои Asset/Cartridge: branch совпадает и `current_user_id` равен login без учета регистра. Совпадение ФИО, кабинета, hostname или знания numeric ID не дает доступа. Viewer читает данные своего филиала без права изменений.
- Superadmin может читать все филиалы либо явно выбрать один; создавать объект в выбранном филиале; управлять членством пользователей. Смешивание филиалов в одном явно адресованном bulk-запросе изменения запрещено. Для глобальной рассылки superadmin без списка IDs сохраняется разрешенная выборка всех готовых картриджей; `branch_id` query ограничивает её одним филиалом.
- Связи Asset–Floor/Zone, BatchItem–Cartridge, RepairBatchItem–Asset, SwitchPort–Zone/Asset должны оставаться внутри одного филиала даже для superadmin. Zone актива должна соответствовать его Floor.
- Обычный PUT не переносит существующие branch-scoped сущности между филиалами. Для такого переноса нужен отдельный согласованный workflow, которого пока нет. Исключение: явное изменение филиала AppUser superadmin.
- Объекты с NULL branch доступны superadmin. Эта работа не назначает им филиал автоматически и не удаляет данные.
- Старые некорректные связи скрываются обычным scope. Перед изменением адресованного объекта проверяются также скрытые входящие связи: при конфликте возвращается 409. Каскадное удаление чужих данных запрещено; исправление старых связей выполняется отдельно после проверки владельцев.

## Дополнительные границы

Branch admin управляет только technician/operator/viewer/user своего филиала. Нельзя менять свою учетную запись через административный endpoint, управлять peer admin/superadmin, выдавать admin/superadmin или переносить пользователя в другой филиал. Сетевой allowlist филиала меняет только superadmin; обычные описательные настройки своего филиала доступны admin.

Network операции ограничены зарегистрированными коммутаторами своего филиала или IP из управляемого superadmin `Branch.network_subnets`; доменные имена для обычного пользователя запрещены. Дополнительно сохраняется глобальный allowlist адресов из security hardening. MAC matching ограничен филиалом самого коммутатора даже для superadmin.

ADUser — явно глобальный справочник сотрудников: в текущей схеме у него нет branch ownership. Чтение разрешено только staff, без viewer/user. AD sync и глобальные каталоги на запись требуют superadmin. Это осознанная граница текущей схемы, а не утверждение о филиальной изоляции AD. Если справочник тоже должен быть филиальным, нужна отдельная модель принадлежности и миграция.

SystemSetting возвращается клиентам через существующую маскирующую сериализацию; изменение и проверка глобальных интеграций требуют superadmin. WhatsApp status/QR/reset для обычных операторов ограничены своим instance. Уведомления выбирают картриджи через scoped Session и проверяют все переданные IDs до вызова внешнего API.

Карты этажей больше не выдаются через public static maps. Новый `GET /api/v1/location/floors/{floor_id}/map` проверяет floor scope, локальный путь и принадлежность имени файла этому этажу. Canvas загружает изображение с Bearer header через Blob URL. Внешние URL карт и ссылки на файл другого этажа не обслуживаются: существующие такие карты нужно загрузить через upload-map своего этажа. Public HTML/CSS/JS, health и OpenAPI содержат только интерфейс/описание API; данные получают отдельными защищенными запросами. Nginx проксирует запросы, отдельного публичного alias maps нет.

GET больше не назначает branch/AD-владельца и не создает demo Floor. Read policy запрещает flush с изменениями. Ответы с Authorization, включая печатные акты, имеют `Cache-Control: no-store`.

## Граница доверия и расширение

Это application-level enforcement, не PostgreSQL RLS. Startup, migrations, bootstrap/reset CLI и предварительный этап login используют привилегированный Session без request Principal. Они не являются публичными data endpoints. HTTP services обязаны использовать переданный `db`; создавать дополнительный unbound Session внутри обработчика запрещено и проверяется architecture test. Новые background jobs должны явно выбрать проверенный Principal/branch и вызвать `bind_scope`, либо быть отдельно рассмотренным административным процессом.

Обычный request Session запрещает Core/raw SQL. Единственное узкое исключение — внутренний read-only Core connection в `require_consistent_references`: он обнаруживает скрытые поврежденные связи, возвращает только разрешение/409 и не передает строки клиенту. DocumentCounter имеет отдельное атомарное UPDATE для разрешенных write операций.

Для нового endpoint: добавить явную политику, перечислить все aliases, определить scope каждого ID/внешнего эффекта, добавить негативный и положительный тест. Для новой модели: определить global либо branch-parent chain; architecture test отклонит модель без scope. Не добавлять обходные флаги вроде `skip_scope` в клиентские параметры.

## Проверка и внедрение

`python scripts/audit_authorization.py` проверяет соответствие source routes и policy registry. `tests/security/test_branch_isolation.py` проверяет все mounted routes на анонимный доступ, все мутации для viewer, все branch endpoints на чужой selector, а также IDOR, связи, отчеты, карты, роли, bulk preflight и положительные сценарии. Architecture tests проверяют модельный scope и единственный Bearer. CI запускает эти сценарии также на временном PostgreSQL 15.

Изменения построены поверх Alembic PR #4. Сначала требуется внедрить его после проверки production schema, затем эти policies. Новая schema migration для authorization не требуется. Перед rollout назначить реальные филиалы учетным записям, проверить AD ownership и старые cross-branch связи, определить network_subnets суперпользователем. Не назначать всем NULL-записям случайный филиал. Не выполняется production migration, удаление данных или history rewrite.
