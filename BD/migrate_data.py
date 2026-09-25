"""
Скрипт переноса и синхронизации данных из CARTRIDGE/data/cartridges.db
в общую базу данных BD/app_unified.db.
"""
import os
import sys
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from SHARED.database import init_db, SessionLocal, engine
from SHARED import models

OLD_DB_PATH = BASE_DIR / "CARTRIDGE" / "data" / "cartridges.db"
NEW_DB_PATH = BASE_DIR / "BD" / "app_unified.db"


def run_migration():
    print(f"[*] Инициализация общей базы данных: {NEW_DB_PATH}")
    init_db()

    if not OLD_DB_PATH.exists():
        print(f"[-] Исходная база данных {OLD_DB_PATH} не найдена. Создана чистая база с дефолтными данными.")
        return

    print(f"[*] Миграция данных из {OLD_DB_PATH} в {NEW_DB_PATH}...")
    
    conn_old = sqlite3.connect(OLD_DB_PATH)
    conn_old.row_factory = sqlite3.Row
    cursor_old = conn_old.cursor()

    db = SessionLocal()
    try:
        # 1. Филиалы (Branches)
        try:
            cursor_old.execute("SELECT * FROM branches;")
            for row in cursor_old.fetchall():
                row_dict = dict(row)
                exists = db.query(models.Branch).filter(models.Branch.name == row_dict.get("name")).first()
                if not exists:
                    b = models.Branch(
                        id=row_dict.get("id"),
                        name=row_dict.get("name"),
                        code=row_dict.get("code"),
                        address=row_dict.get("address"),
                        it_office=row_dict.get("it_office"),
                        wa_message_template=row_dict.get("wa_message_template"),
                        notes=row_dict.get("notes")
                    )
                    db.add(b)
            db.commit()
            print("[+] Филиалы успешно перенесены.")
        except Exception as e:
            print(f"[-] Ошибка миграции филиалов: {e}")
            db.rollback()

        # 2. Пользователи (AppUsers)
        try:
            cursor_old.execute("SELECT * FROM app_users;")
            for row in cursor_old.fetchall():
                row_dict = dict(row)
                exists = db.query(models.AppUser).filter(models.AppUser.username == row_dict.get("username")).first()
                if not exists:
                    u = models.AppUser(
                        id=row_dict.get("id"),
                        username=row_dict.get("username"),
                        full_name=row_dict.get("full_name"),
                        password_hash=row_dict.get("password_hash"),
                        auth_type=row_dict.get("auth_type", "local"),
                        role=row_dict.get("role", "operator"),
                        is_active=bool(row_dict.get("is_active", 1)),
                        branch_id=row_dict.get("branch_id"),
                        wa_instance_name=row_dict.get("wa_instance_name")
                    )
                    db.add(u)
                else:
                    # Обновим хэш пароля если нужно
                    if row_dict.get("password_hash"):
                        exists.password_hash = row_dict.get("password_hash")
            db.commit()
            print("[+] Пользователи успешно перенесены.")
        except Exception as e:
            print(f"[-] Ошибка миграции пользователей: {e}")
            db.rollback()

        # 3. Сотрудники AD (ADUsers)
        try:
            cursor_old.execute("SELECT * FROM ad_users;")
            for row in cursor_old.fetchall():
                row_dict = dict(row)
                exists = db.query(models.ADUser).filter(models.ADUser.samaccountname == row_dict.get("samaccountname")).first()
                if not exists:
                    adu = models.ADUser(
                        samaccountname=row_dict.get("samaccountname"),
                        display_name=row_dict.get("display_name"),
                        department=row_dict.get("department"),
                        cabinet=row_dict.get("cabinet"),
                        phone=row_dict.get("phone")
                    )
                    db.add(adu)
            db.commit()
            print("[+] Сотрудники AD перенесены.")
        except Exception as e:
            print(f"[-] Ошибка миграции сотрудников AD: {e}")
            db.rollback()

        # 4. Модели картриджей (CartridgeModels)
        try:
            cursor_old.execute("SELECT * FROM cartridge_models;")
            for row in cursor_old.fetchall():
                row_dict = dict(row)
                exists = db.query(models.CartridgeModel).filter(models.CartridgeModel.name == row_dict.get("name")).first()
                if not exists:
                    cm = models.CartridgeModel(
                        name=row_dict.get("name"),
                        vendor=row_dict.get("vendor"),
                        resource_pages=row_dict.get("resource_pages"),
                        compatible_printers=row_dict.get("compatible_printers"),
                        notes=row_dict.get("notes")
                    )
                    db.add(cm)
            db.commit()
            print("[+] Модели картриджей перенесены.")
        except Exception as e:
            print(f"[-] Ошибка миграции моделей картриджей: {e}")
            db.rollback()

        # 5. Картриджи (Cartridges)
        try:
            cursor_old.execute("SELECT * FROM cartridges;")
            for row in cursor_old.fetchall():
                row_dict = dict(row)
                exists = db.query(models.Cartridge).filter(models.Cartridge.marker_label == row_dict.get("marker_label")).first()
                if not exists:
                    c = models.Cartridge(
                        id=row_dict.get("id"),
                        marker_label=row_dict.get("marker_label"),
                        qr_code=row_dict.get("qr_code"),
                        model=row_dict.get("model"),
                        cabinet=row_dict.get("cabinet"),
                        status=row_dict.get("status", "in_use"),
                        branch_id=row_dict.get("branch_id"),
                        current_user_id=row_dict.get("current_user_id"),
                        condition="working",
                        notes=row_dict.get("notes")
                    )
                    db.add(c)
            db.commit()
            print("[+] Картриджи успешно перенесены.")
        except Exception as e:
            print(f"[-] Ошибка миграции картриджей: {e}")
            db.rollback()

        # 6. Партии заправки (Batches & BatchItems)
        try:
            cursor_old.execute("SELECT * FROM batches;")
            for row in cursor_old.fetchall():
                row_dict = dict(row)
                exists = db.query(models.Batch).filter(models.Batch.act_number == row_dict.get("act_number")).first()
                if not exists:
                    b = models.Batch(
                        id=row_dict.get("id"),
                        act_number=row_dict.get("act_number"),
                        vendor_name=row_dict.get("vendor_name"),
                        branch_id=row_dict.get("branch_id"),
                        status=row_dict.get("status", "open"),
                        notes=row_dict.get("notes")
                    )
                    db.add(b)
            db.commit()

            cursor_old.execute("SELECT * FROM batch_items;")
            for row in cursor_old.fetchall():
                row_dict = dict(row)
                bi = models.BatchItem(
                    id=row_dict.get("id"),
                    batch_id=row_dict.get("batch_id"),
                    cartridge_id=row_dict.get("cartridge_id"),
                    action_required=row_dict.get("action_required", "Заправка")
                )
                db.merge(bi)
            db.commit()
            print("[+] Акты и позиции картриджей перенесены.")
        except Exception as e:
            print(f"[-] Ошибка миграции актов: {e}")
            db.rollback()

        print("[*] Миграция успешно завершена! Единая база данных готова в BD/app_unified.db")

    finally:
        db.close()
        conn_old.close()


if __name__ == "__main__":
    run_migration()
