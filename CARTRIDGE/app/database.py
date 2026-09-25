from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL, DEFAULT_SETTINGS, SETTING_DESCRIPTIONS

# Поддержка SQLite и PostgreSQL
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация базы данных и создание таблиц, а также первичная запись настроек, филиалов и администратора."""
    from app import models  # noqa: F401
    from app.services.auth_service import AuthService
    Base.metadata.create_all(bind=engine)

    # 0. Автоматическая миграция схемы для существующих баз данных (PostgreSQL и SQLite)
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        with engine.begin() as conn:
            # cartridges
            if "cartridges" in existing_tables:
                cols_cart = {c["name"] for c in inspector.get_columns("cartridges")}
                if "branch_id" not in cols_cart:
                    conn.execute(text("ALTER TABLE cartridges ADD COLUMN branch_id INTEGER;"))
                if "condition" not in cols_cart:
                    conn.execute(text("ALTER TABLE cartridges ADD COLUMN condition VARCHAR(20) DEFAULT 'working';"))

            # batches
            if "batches" in existing_tables:
                cols_batch = {c["name"] for c in inspector.get_columns("batches")}
                if "branch_id" not in cols_batch:
                    conn.execute(text("ALTER TABLE batches ADD COLUMN branch_id INTEGER;"))

            # app_users
            if "app_users" in existing_tables:
                cols_users = {c["name"] for c in inspector.get_columns("app_users")}
                if "wa_instance_name" not in cols_users:
                    conn.execute(text("ALTER TABLE app_users ADD COLUMN wa_instance_name VARCHAR(100);"))

            # branches
            if "branches" in existing_tables:
                cols_branches = {c["name"] for c in inspector.get_columns("branches")}
                if "it_office" not in cols_branches:
                    conn.execute(text("ALTER TABLE branches ADD COLUMN it_office VARCHAR(255);"))
                if "wa_message_template" not in cols_branches:
                    conn.execute(text("ALTER TABLE branches ADD COLUMN wa_message_template TEXT;"))
    except Exception as ex:
        print(f"[MIGRATION CHECK] Schema migration warning: {ex}")
    
    db = SessionLocal()
    try:
        # 1. Инициализация дефолтных настроек
        existing_keys = {
            s.key for s in db.query(models.SystemSetting.key).all()
        }
        for key, val in DEFAULT_SETTINGS.items():
            if key not in existing_keys:
                db.add(
                    models.SystemSetting(
                        key=key,
                        value=val,
                        description=SETTING_DESCRIPTIONS.get(key, "")
                    )
                )

        # 2. Инициализация филиала по умолчанию
        main_branch = db.query(models.Branch).first()
        if not main_branch:
            main_branch = models.Branch(
                name="Главный офис",
                code="HQ",
                address="Центральный офис",
                notes="Основной филиал компании"
            )
            db.add(main_branch)
            db.flush()

        # 3. Инициализация локального суперпользователя (admin / admin123)
        admin_user = db.query(models.AppUser).filter(models.AppUser.username == "admin").first()
        if not admin_user:
            admin_user = models.AppUser(
                username="admin",
                full_name="Главный Администратор",
                password_hash=AuthService.hash_password("admin123"),
                auth_type="local",
                role="superadmin",
                is_active=True,
                branch_id=None  # Доступ ко всем филиалам
            )
            db.add(admin_user)
        else:
            if admin_user.role == "admin":
                admin_user.role = "superadmin"

        # 4. Очистка логинов существующих AD-пользователей от доменных префиксов/суффиксов (@...)
        ad_users = db.query(models.AppUser).filter(models.AppUser.auth_type == "ad").all()
        for u in ad_users:
            if "@" in u.username or "\\" in u.username:
                clean_name = u.username.split("@")[0].split("\\")[-1].strip()
                existing = db.query(models.AppUser).filter(models.AppUser.username == clean_name, models.AppUser.id != u.id).first()
                if not existing:
                    u.username = clean_name

        # 5. Инициализация популярных моделей картриджей по умолчанию
        if db.query(models.CartridgeModel).count() == 0:
            default_models = [
                models.CartridgeModel(
                    name="HP CE285A (85A)",
                    vendor="HP",
                    resource_pages=1600,
                    compatible_printers="HP LaserJet Pro P1102, P1102w, M1132, M1212nf, M1214nfh, M1217nfw",
                    notes="Популярный офисный картридж"
                ),
                models.CartridgeModel(
                    name="HP CF218A (18A)",
                    vendor="HP",
                    resource_pages=1400,
                    compatible_printers="HP LaserJet Pro M104a, M104w, MFP M132a, M132nw, M132fn, M132fw",
                    notes="Картридж с технологией JetIntelligence"
                ),
                models.CartridgeModel(
                    name="HP CF226A (26A)",
                    vendor="HP",
                    resource_pages=3100,
                    compatible_printers="HP LaserJet Pro M402d, M402n, M402dn, MFP M426dw, M426fdn, M426fdw",
                    notes="Для принтеров высокой нагрузки"
                ),
                models.CartridgeModel(
                    name="Canon 725",
                    vendor="Canon",
                    resource_pages=1600,
                    compatible_printers="Canon i-SENSYS LBP6000, LBP6020, LBP6030, MF3010",
                    notes="Аналог HP CE285A"
                ),
                models.CartridgeModel(
                    name="Canon 728",
                    vendor="Canon",
                    resource_pages=2100,
                    compatible_printers="Canon i-SENSYS MF4410, MF4430, MF4450, MF4550d, MF4570dn, MF4580dn",
                    notes="Аналог HP CE278A"
                ),
                models.CartridgeModel(
                    name="Pantum PC-211EV",
                    vendor="Pantum",
                    resource_pages=1600,
                    compatible_printers="Pantum P2200, P2207, P2500, P2500W, M6500, M6500W, M6550, M6600",
                    notes="Картридж с чипом Pantum"
                ),
                models.CartridgeModel(
                    name="Kyocera TK-1150",
                    vendor="Kyocera",
                    resource_pages=3000,
                    compatible_printers="Kyocera ECOSYS M2135dn, M2635dn, M2735dw, P2235dn, P2235dw",
                    notes="Тонер-картридж Kyocera"
                ),
                models.CartridgeModel(
                    name="Samsung MLT-D101S",
                    vendor="Samsung",
                    resource_pages=1500,
                    compatible_printers="Samsung ML-2160, ML-2165, SCX-3400, SCX-3405, SF-760P",
                    notes="Монохромный картридж Samsung"
                ),
            ]
            db.add_all(default_models)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[INIT DB ERROR] Error initializing database: {e}")
    finally:
        db.close()
