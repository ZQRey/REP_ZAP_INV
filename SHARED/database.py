import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from SHARED.config import DATABASE_URL, DEFAULT_SETTINGS, SETTING_DESCRIPTIONS

logger = logging.getLogger("SHARED.database")

# Поддержка SQLite и PostgreSQL
connect_args = {}
effective_db_url = DATABASE_URL

if effective_db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif effective_db_url.startswith("postgres://"):
    effective_db_url = effective_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif effective_db_url.startswith("postgresql://") and not effective_db_url.startswith("postgresql+"):
    # В SQLAlchemy 2.0 схема "postgresql://" по умолчанию ищет драйвер 'psycopg' (psycopg3).
    # Если установлен только psycopg2-binary, автоматически используем postgresql+psycopg2://.
    try:
        import psycopg
    except ImportError:
        effective_db_url = effective_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(effective_db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency для получения сессии БД."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Инициализация таблиц базы данных и базовых записей:
    - Дефолтные системные настройки
    - Главный филиал
    - Суперпользователь (admin / admin123)
    - Базовые модели картриджей и техники
    """
    from SHARED import models
    from SHARED.auth_service import AuthService
    
    # Создаем все зарегистрированные таблицы
    Base.metadata.create_all(bind=engine)

    # Автоматическая миграция / проверка колонок для SQLite
    if DATABASE_URL.startswith("sqlite"):
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                # network_switches columns
                res = conn.execute(text("PRAGMA table_info(network_switches)")).fetchall()
                existing_cols = {row[1] for row in res}
                new_switch_cols = [
                    ("management_type", "VARCHAR(50) DEFAULT 'snmp'"),
                    ("mgmt_port", "INTEGER DEFAULT 161"),
                    ("username", "VARCHAR(100)"),
                    ("password", "VARCHAR(255)"),
                    ("extra_params", "JSON"),
                    ("last_poll_status", "VARCHAR(20) DEFAULT 'never'"),
                    ("last_poll_message", "VARCHAR(500)"),
                    ("last_polled_at", "DATETIME")
                ]
                for col_name, col_def in new_switch_cols:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE network_switches ADD COLUMN {col_name} {col_def}"))

                # switch_ports columns
                res_p = conn.execute(text("PRAGMA table_info(switch_ports)")).fetchall()
                existing_p_cols = {row[1] for row in res_p}
                new_port_cols = [
                    ("cabinet", "VARCHAR(100)"),
                    ("socket_label", "VARCHAR(100)"),
                    ("zone_id", "INTEGER"),
                    ("last_mac", "VARCHAR(50)"),
                    ("last_ip", "VARCHAR(50)"),
                    ("last_seen_at", "DATETIME")
                ]
                for col_name, col_def in new_port_cols:
                    if col_name not in existing_p_cols:
                        conn.execute(text(f"ALTER TABLE switch_ports ADD COLUMN {col_name} {col_def}"))
                conn.commit()
        except Exception as ex:
            logger.warning(f"SQLite schema migration warning: {ex}")

    db = SessionLocal()
    try:
        # 1. Системные настройки
        existing_keys = {s.key for s in db.query(models.SystemSetting.key).all()}
        for key, val in DEFAULT_SETTINGS.items():
            if key not in existing_keys:
                db.add(
                    models.SystemSetting(
                        key=key,
                        value=val,
                        description=SETTING_DESCRIPTIONS.get(key, "")
                    )
                )

        # Автоматическое обновление устаревших шаблонных значений LDAP до короткого формата
        bind_user_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "ad_bind_user").first()
        if bind_user_setting and bind_user_setting.value == "CN=svc_ldap,OU=Service,DC=company,DC=local":
            bind_user_setting.value = "svc_ldap@gp1.loc"

        base_dn_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "ad_base_dn").first()
        if base_dn_setting and base_dn_setting.value == "DC=company,DC=local":
            base_dn_setting.value = "DC=gp1,DC=loc"

        # 2. Главный филиал по умолчанию
        main_branch = db.query(models.Branch).first()
        if not main_branch:
            main_branch = models.Branch(
                name="Главный офис",
                code="HQ",
                address="Центральный офис",
                it_office="Кабинет IT № 108",
                notes="Основной филиал компании"
            )
            db.add(main_branch)
            db.flush()

        # 3. Локальный суперпользователь admin / admin123
        admin_user = db.query(models.AppUser).filter(models.AppUser.username == "admin").first()
        if not admin_user:
            admin_user = models.AppUser(
                username="admin",
                full_name="Главный Администратор",
                password_hash=AuthService.hash_password("admin123"),
                auth_type="local",
                role="superadmin",
                is_active=True,
                branch_id=main_branch.id if main_branch else None
            )
            db.add(admin_user)

        # 4. Базовые популярные модели картриджей (если справочник пуст)
        if db.query(models.CartridgeModel).count() == 0:
            demo_models = [
                models.CartridgeModel(name="HP 85A (CE285A)", vendor="HP", resource_pages=1600, compatible_printers="HP LaserJet P1102 / M1132 / M1212nf"),
                models.CartridgeModel(name="HP 83A (CF283A)", vendor="HP", resource_pages=1500, compatible_printers="HP LaserJet Pro M125 / M127 / M201 / M225"),
                models.CartridgeModel(name="Canon 725", vendor="Canon", resource_pages=1600, compatible_printers="Canon LBP6000 / MF3010"),
                models.CartridgeModel(name="Kyocera TK-1170", vendor="Kyocera", resource_pages=7200, compatible_printers="Kyocera ECOSYS M2040dn / M2540dn / M2640idw"),
                models.CartridgeModel(name="Samsung MLT-D101S", vendor="Samsung", resource_pages=1500, compatible_printers="Samsung ML-2160 / SCX-3400"),
                models.CartridgeModel(name="Pantum PC-211EV", vendor="Pantum", resource_pages=1600, compatible_printers="Pantum P2207 / P2500 / M6500"),
            ]
            db.add_all(demo_models)

        # 5. Базовые категории моделей техники (если справочник пуст)
        if db.query(models.EquipmentModel).count() == 0:
            demo_equip_models = [
                models.EquipmentModel(name="HP ProDesk 400 G6", category="workstation", vendor="HP", specs_template="Core i5, 16GB RAM, 512GB SSD"),
                models.EquipmentModel(name="Lenovo ThinkCentre M720q", category="workstation", vendor="Lenovo", specs_template="Core i3, 8GB RAM, 256GB SSD"),
                models.EquipmentModel(name="Dell Latitude 5420", category="laptop", vendor="Dell", specs_template="Core i5-1135G7, 16GB RAM, 512GB SSD, 14\" FHD"),
                models.EquipmentModel(name="HP LaserJet Pro M428fdn", category="printer", vendor="HP", specs_template="МФУ лазерное, A4, дуплекс, сеть"),
                models.EquipmentModel(name="Dell P2419H", category="monitor", vendor="Dell", specs_template="23.8\" IPS, Full HD, HDMI/DP/VGA"),
                models.EquipmentModel(name="APC Smart-UPS 1500VA", category="ups", vendor="APC", specs_template="1500VA / 1000W, LCD, 230V"),
                models.EquipmentModel(name="Cisco Catalyst 2960X-48TS-L", category="switch", vendor="Cisco", specs_template="48x 1GbE, 4x 1G SFP, LAN Base"),
            ]
            db.add_all(demo_equip_models)

        db.commit()
        logger.info("[DB INIT] Database successfully initialized in BD/app_unified.db")
    except Exception as e:
        db.rollback()
        logger.error(f"[DB INIT ERROR] Failed to initialize database: {e}")
        raise
    finally:
        db.close()
