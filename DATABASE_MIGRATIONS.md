# Миграции базы данных

## Источник схемы и границы проверки

Alembic — единственный механизм изменения схемы приложения. Canonical ORM: `SHARED/models.py`; единственные Base, engine и SessionLocal: `SHARED/database.py`; DATABASE_URL/DATABASE_URL_FILE: `SHARED/security_config.py`. Alembic использует эти же объекты, без второго pool/registry. Файл `alembic/frozen_baseline.py` — **не ORM**, а неизменяемый исторический Core snapshot 22 таблиц из main `c07e978`; будущие миграции не должны редактировать его.

**Production-БД и schema-only dump не были предоставлены.** Нельзя утверждать, что deployed schema совпадает с моделями. Baseline построен по canonical models, сохранённому DDL-контракту SQLite/PostgreSQL и всем прежним startup ALTER. Для существующей БД обязательны read-only audit и проверка на восстановленной копии. Не выполнять слепой `alembic stamp head`: это обходит проверки и не создаёт constraints/counters.

После head существует 23-я таблица `document_counters`. Приложение при запуске проверяет Alembic revision и останавливается, если версия отсутствует/устарела. Startup не вызывает create_all, ALTER/ADD COLUMN, schema repair или command.upgrade. `init_db` после проверки версии сохраняет прежнее наполнение базовых записей; создание администратора по-прежнему явное. Standalone Repair/Location проверяют версию без seeding.

## Последовательность revisions

| Revision | Upgrade | Downgrade / риск |
|---|---|---|
| `0001_baseline` | Создаёт frozen schema на пустой БД. Для существующей требует явного adoption и совпадения схемы | **Destructive:** удаляет все 22 таблицы и PostgreSQL enum types. Заблокирован без `-x allow_destructive=true` |
| `0002_legacy_alignment` | Только известные nullable columns, отсутствующие canonical FK/indexes, расширение it_office 100→255, удаление устаревших server defaults | No-op: обе revisions описывают canonical baseline. Не возвращает отсутствующие FK, короткие поля и небезопасные defaults. Исторические физические дефекты не восстанавливаются |
| `0003_integrity_numbering` | Проверяет данные, добавляет UNIQUE/CHECK/NOT NULL/FK indexes и transactional counters; существующие строки не переписывает | **Потенциально destructive:** снимает ограничения и удаляет историю счётчиков. Явный флаг обязателен. Сами документы и их номера остаются |

Нормальный upgrade не содержит удаления таблиц/колонок/строк, сужения типов, преобразования enum labels, дедупликации или автоматического исправления значений. Добавление NOT NULL/UNIQUE/CHECK может заблокировать старые некорректные операции; это намеренное изменение целостности. При дублях, NULL, нарушениях CHECK или orphan rows миграция останавливается до изменения таблиц соответствующей revision.

PostgreSQL migrations выполняются в транзакции под advisory lock. Для DDL задан lock_timeout 15 секунд. Integrity migration блокирует запись в application tables на время preflight/constraints/counter initialization. Планировать окно обслуживания и остановить все старые writers (API, фоновые задачи, import scripts); приложение старой версии не умеет пользоваться новым счётчиком. Индексы создаются обычным транзакционным способом, не CONCURRENTLY: на больших таблицах нужна оценка длительности на копии.

## Найденные расхождения

Прежний startup мог добавить `cartridges.branch_id`, `batches.branch_id`, `switch_ports.zone_id` и `switch_ports.connected_asset_id` как INTEGER без FK; create_all не исправлял constraints существующих таблиц. Другие ручные добавления: поля управления и polling `network_switches`; кабинет, розетка, MAC/IP и last_seen_at в `switch_ports`; cartridges.condition; app_users.wa_instance_name; branches.it_office/wa_message_template. В Cartridge-only схеме мог отсутствовать branches.network_subnets.

- `branches.it_office`: ORM VARCHAR(255), старый shared ALTER VARCHAR(100). Revision 0002 только расширяет поле, ничего не обрезает.
- Старые ALTER оставляли server defaults для management_type/mgmt_port/snmp_community/total_ports/last_poll_status/condition, которых нет в canonical models. 0002 удаляет только распознанные исторические defaults; существующие значения не изменяет. Обнаружение старого SNMP default не является назначением community устройствам.
- Отсутствующие nullable columns добавляются с NULL для прежних строк, без скрытого backfill. В 0003 часть новых operational fields требует NOT NULL. Если старые строки получают NULL, миграция остановится: сначала явное согласованное заполнение на копии, затем повторная проверка. Значения не угадываются.
- Missing canonical FK и indexes добавляются; orphan rows предварительно блокируют операцию. Поля с ON DELETE SET NULL остаются nullable. Обязательные FK позиций актов уже были NOT NULL и остаются такими.
- Enum labels сохраняются: SQLAlchemy хранит uppercase labels (`IN_USE`, `AT_VENDOR` и т. п.), не lower-case `.value`. Изменение labels блокирует adoption.
- Неизвестные differences (другие типы, missing tables, изменённые PK, лишние колонки/constraints в application tables и т. п.) блокируют adoption. Для них нужна отдельная рассмотренная миграция; автоматического «repair everything» нет.

Чужие таблицы Evolution/PostGIS исключены из autogenerate и не удаляются. Это не отменяет проверки application schema. Частичная Cartridge-only БД с 9 таблицами не может быть зарегистрирована как полный baseline: требуется отдельный план переноса в unified schema.

## Новая целостность

Добавлены именованные UNIQUE:

- `batch_items(batch_id, cartridge_id)` — картридж не может повторяться в одном акте;
- `repair_batch_items(batch_id, asset_id)` — оборудование не может повторяться в одном акте ремонта;
- `switch_ports(switch_id, port_number)` — номер порта уникален внутри коммутатора.

Повторная отправка того же устройства в **другом** акте остаётся допустимой. Существующий UNIQUE network_switches.asset_id сохраняет отношение один-к-одному. На всех FK обеспечено покрытие индексом с FK в начале (отдельный index либо уже существующий PK/UNIQUE/composite index). Cross-branch authorization не заменяется FK и остаётся обязанностью backend.

CHECK: неотрицательные цены/стоимость/остатки/порог, положительное количество использованных деталей, положительный масштаб, неотрицательная вместимость кабельного канала, допустимый management port 1–65535, VLAN 1–4094, положительный номер порта и total_ports, статусы актов open/closed, счётчик >=0. NOT NULL добавлены для соответствующих обязательных количеств, стоимости, масштаба, VLAN/management port/total_ports и статусов актов/ремонтных позиций. Полный неизменяемый перечень — `alembic/integrity_spec.json`; models содержат такие же ограничения.

Миграция не удаляет дубли и не назначает orphan rows случайному филиалу. Для диагностики, например:

```sql
SELECT batch_id, cartridge_id, COUNT(*)
FROM batch_items GROUP BY batch_id, cartridge_id HAVING COUNT(*) > 1;
SELECT batch_id, asset_id, COUNT(*)
FROM repair_batch_items GROUP BY batch_id, asset_id HAVING COUNT(*) > 1;
SELECT switch_id, port_number, COUNT(*)
FROM switch_ports GROUP BY switch_id, port_number HAVING COUNT(*) > 1;
```

Эти COUNT используются только для проверки дублей, никогда для выдачи номера документа.

## Номера актов

`SHARED.document_numbers.next_document_number` выполняет один `UPDATE document_counters SET last_value = last_value + 1 ... RETURNING last_value` в транзакции создания акта. PostgreSQL блокирует строку счётчика; конкурентные writers получают разные номера. Два независимых scope: cartridge и repair. Нет runtime COUNT/MAX, поиска «последнего акта» или fallback.

Сохраняется внешний формат `ПРЕФИКСYYYYMMDD-NNN` / `ПРЕФИКСYYYY-NNNN`, но suffix теперь **глобально возрастает внутри scope и не сбрасывается ежедневно/ежегодно**. Удаление документов не сбрасывает счётчик. Rollback отменяет и резервирование номера: незафиксированный номер может использоваться снова. Это транзакционная нумерация, не обещание безусловно безразрывного публичного реестра.

Revision 0003 под блокировкой один раз инициализирует last_value максимальным ASCII-числовым suffix существующих номеров всех периодов/prefixes. Номера не переписываются; нестандартные номера без числового suffix остаются. Переполнение BIGINT останавливает миграцию. После запуска внешние импорты актов с произвольными номерами требуют отдельного maintenance-процесса согласования счётчика; старый BD/migrate_data нельзя запускать параллельно live writers. Downgrade удаляет историю даже уже удалённых актов: восстановление production требует backup счётчиков, иначе возможно повторное использование исторически выданного номера.

## Команды и внедрение

Работать из корня репозитория с установленными requirements. Секреты подавать существующей configuration системой; не хранить URL/password в alembic.ini, командной истории или Git. Production configuration требует штатные обязательные секреты приложения. Для migration job DATABASE_URL должен использовать отдельную роль владельца схемы; runtime role должна иметь только необходимые DML/sequence privileges, без CREATE/ALTER/DROP. Изменение реальных ролей автоматически не выполняется.

Сначала сделать backup, проверить восстановление в отдельную БД, снять schema-only dump, остановить writers. Проверить объём данных/время блокировок на восстановленной копии. Ни одна команда ниже не выполнялась над production в этой работе.

**Пустая БД:**

```sh
alembic upgrade head
alembic current
alembic check
# После успешной миграции запустить приложение.
```

**Существующая БД без Alembic:**

```sh
python -m SHARED.migration_support
```

Команда только читает схему, выводит имена расхождений без row data/secrets. Exit 0 — точное совпадение baseline; exit 1 — differences. После проверки backup и результата на копии:

```sh
# Только если audit не нашёл расхождений:
alembic -x adopt_existing=true upgrade head

# Если ВСЕ differences помечены known_legacy=true и их исправление рассмотрено:
alembic -x adopt_existing=true -x accept_legacy_drift=true upgrade head
```

Adoption валидирует схему повторно и не применяет baseline CREATE поверх существующих таблиц. Не заменять процесс на stamp. Audit baseline предназначен для состояния ДО миграции; после head использовать `alembic current` и `alembic check`.

**Docker:** образы содержат alembic/ и alembic.ini; CMD запускает только uvicorn. Автоматического upgrade, даже additive, нет. После остановки приложения оператор запускает одноразовую задачу явно:

```sh
docker compose run --rm --no-deps unified-server alembic upgrade head
docker compose up -d unified-server
```

Зависимости БД должны уже работать, конфигурация — быть загружена. Для adoption нужны те же явные флаги. Migration role URL передаётся средой этой одноразовой задачи, не заменой секретов в tracked compose. В многосерверной установке выполнять миграцию один раз, затем запускать новую версию всех writers.

**Новая revision:**

```sh
alembic revision --autogenerate -m "describe_schema_change"
# Или пустая reviewable revision:
alembic revision -m "describe_data_migration"
alembic upgrade head
alembic check
```

Autogenerate — черновик: проверить downgrade, FK ondelete, unique/check names, enum changes и PostgreSQL locks; SQLAlchemy/Alembic не обнаруживает автоматически все CHECK/PK/enum differences. Не редактировать применённые revisions, frozen_baseline и integrity_spec; добавлять следующую revision. Baseline SQL можно просмотреть через `alembic upgrade 0001_baseline --sql`. Revisions 0002/0003 требуют online preflight и намеренно запрещают offline execution: проверять DDL/данные на восстановленной копии, не исполнять обходной SQL без preflight.

**Откат:**

```sh
alembic downgrade -1
```

При head эта команда **остановится**, поскольку удаляется история счётчиков и гарантии целостности. Только после отдельного рассмотрения и backup:

```sh
alembic -x allow_destructive=true downgrade 0002_legacy_alignment
```

Откат до base удаляет всю application schema и не является обычным rollback приложения. По умолчанию заблокирован. Удаление данных невозможно компенсировать upgrade; требуется проверенное восстановление backup. No-op downgrade 0002 не восстанавливает старые дефекты схемы.

## Проверки

```sh
python -m pytest
python -m pytest tests/migrations -v
```

Локальные тесты работают только с временной SQLite. Отдельный CI job запускает PostgreSQL 15 с временной БД rep_zap_migration_test, случайным паролем и loopback port; тестовый URL дополнительно проверяется перед любыми destructive fixtures. Проверяются fresh upgrade/startup, exact existing adoption, known/unknown drift, данные и numbering после migration, orphan/duplicate/NULL/CHECK failures без cleanup, UNIQUE/FK/CHECK enforcement, autogenerate parity, parallel numbering, rollback, guarded downgrade/reupgrade, отсутствие startup DDL.

SQLite batch migrations временно выключают FK enforcement только в migration connection для rebuild и выполняют foreign_key_check до commit. Runtime SQLite включает FK enforcement. PostgreSQL — основной deployment target; SQLite не заменяет PostgreSQL CI. Тестовые drop/create и downgrade выполняются только над одноразовыми тестовыми БД, не production.
