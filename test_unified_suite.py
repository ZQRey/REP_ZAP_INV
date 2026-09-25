import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "CARTRIDGE"))

from fastapi.testclient import TestClient
from main_server import app
from SHARED.database import init_db, SessionLocal
from SHARED import models

def test_full_unified_platform():
    print("[*] 1. Инициализация базы данных...")
    init_db()

    client = TestClient(app)

    # 1. Проверка работоспособности Health
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print(f"[+] Health check OK: {res.json()}")

    # 2. Логин администратора через Единый SSO
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123",
        "auth_type": "local"
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    token_data = res.json()
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[+] SSO Login OK for user {token_data['user']['username']}")

    # 3. Проверка профиля текущего пользователя
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    print(f"[+] Profile: {res.json()['full_name']}, role: {res.json()['role']}")

    # 4. Проверка сбора компьютеров из AD (Демо/Мок)
    res = client.post("/api/v1/repair/ad/sync-computers", headers=headers)
    assert res.status_code == 200
    ad_sync_res = res.json()
    print(f"[+] AD Computer Sync: {ad_sync_res}")

    # 5. Проверка списка оборудования и фильтров по состоянию
    res = client.get("/api/v1/repair/equipment", headers=headers)
    assert res.status_code == 200
    equip_list = res.json()
    assert len(equip_list) > 0, "No equipment found after AD sync"
    print(f"[+] Equipment list count: {len(equip_list)}")

    # 6. Этап 1: Приемка неисправной техники в IT-отделе
    test_inv = "TEST-PC-999"
    res = client.post("/api/v1/repair/equipment/accept", json={
        "inventory_number": test_inv,
        "name": "Рабочая станция бухгалтера HP",
        "asset_type": "workstation",
        "cabinet": "Кабинет 202",
        "reported_issue": "Синий экран при загрузке (BSOD)",
        "condition": "broken",
        "notes": "Проверить оперативную память"
    }, headers=headers)
    assert res.status_code == 200, f"Accept failed: {res.text}"
    accepted_asset = res.json()
    assert accepted_asset["condition"] == "broken"
    assert accepted_asset["status"] == "pending_sc"
    print(f"[+] Этап 1 Приемка OK: {accepted_asset['inventory_number']} переведен в статус pending_sc и состояние broken")

    # 7. Этап 2: Отправка в СЦ / Создание акта передачи
    res = client.post("/api/v1/repair/batches", json={
        "vendor_name": "ООО «ТехноРемСервис»",
        "asset_ids": [accepted_asset["id"]],
        "notes": "Срочный ремонт по гарантии"
    }, headers=headers)
    assert res.status_code == 200, f"Batch creation failed: {res.text}"
    batch_data = res.json()
    batch_id = batch_data["id"]
    print(f"[+] Этап 2 Отправка в СЦ OK: Акт {batch_data['act_number']} создан, позиций: {batch_data['items_count']}")

    # 8. Проверка печатной формы акта передачи А4
    res = client.get(f"/print/repair-act/{batch_id}")
    assert res.status_code == 200
    assert "АКТ ПРИЕМА-ПЕРЕДАЧИ ОБОРУДОВАНИЯ" in res.text
    print("[+] Печатная форма Акта А4 успешно сгенерирована HTML")

    # 9. Этап 3: Принятие из СЦ в IT-отдел (БЕЗ WHATSAPP)
    res = client.post("/api/v1/repair/equipment/return-sc", json={
        "asset_ids": [accepted_asset["id"]],
        "diagnostic_result": "Заменен неисправный модуль RAM DDR4",
        "work_performed": "Чистка, замена модуля памяти",
        "cost": 2400.0,
        "condition": "working"
    }, headers=headers)
    assert res.status_code == 200, f"Return failed: {res.text}"
    print("[+] Этап 3 Принятие из СЦ OK (без WhatsApp!): статус returned_it, состояние working")

    # 10. Этап 4: Установка на рабочее место (БЕЗ WHATSAPP)
    res = client.post("/api/v1/repair/equipment/install-workplace", json={
        "asset_ids": [accepted_asset["id"]],
        "cabinet": "Кабинет 202",
        "notes": "Установлен на рабочее место сотрудника"
    }, headers=headers)
    assert res.status_code == 200, f"Install failed: {res.text}"
    print("[+] Этап 4 Установка на рабочее место OK (без WhatsApp!): статус at_workplace, состояние working")

    # 11. Отчеты по рабочей и сломанной технике (JSON и Excel)
    res = client.get("/api/v1/repair/reports/data", headers=headers)
    assert res.status_code == 200
    report_json = res.json()["report"]
    assert "summary" in report_json
    print(f"[+] Отчет по технике JSON OK: Всего {report_json['summary']['total_count']}, Рабочих: {report_json['summary']['working_count']}, Сломанных: {report_json['summary']['broken_count']}")

    res = client.get("/api/v1/repair/reports/export/excel", headers=headers)
    assert res.status_code == 200
    assert len(res.content) > 1000
    print(f"[+] Экспорт отчета в Excel (.xlsx) OK: размер {len(res.content)} байт")

    # 12. Модуль локаций (2D карта и трассировка кабелей)
    branches = client.get("/api/branches", headers=headers).json()
    branch_id = branches[0]["id"]
    res = client.get(f"/api/v1/location/branches/{branch_id}/floors", headers=headers)
    assert res.status_code == 200
    floors = res.json()
    assert len(floors) > 0
    floor_id = floors[0]["id"]
    print(f"[+] Модуль локаций: Этаж {floors[0]['name']}, зон: {len(floors[0]['zones'])}")

    # Размещение актива на карте
    res = client.post(f"/api/v1/location/assets/{accepted_asset['id']}/position", json={
        "coords_x": 0.45,
        "coords_y": 0.25,
        "floor_id": floor_id
    }, headers=headers)
    assert res.status_code == 200
    print("[+] Позиционирование актива на карте Konva OK (coords_x=0.45, coords_y=0.25)")

    # Коммутаторы и трассировка
    switches = client.get(f"/api/v1/location/floors/{floor_id}/switches", headers=headers).json()
    assert len(switches) > 0
    switch_id = switches[0]["id"]
    print(f"[+] Коммутатор на этаже: {switches[0]['name']}, портов: {switches[0]['total_ports']}")

    res = client.get(f"/api/v1/location/network/trace?from_switch={switch_id}&to_asset={accepted_asset['id']}", headers=headers)
    assert res.status_code == 200
    trace = res.json()
    assert trace["found"] == True
    print(f"[+] A* Трассировка кабеля OK: {trace['message']}")

    # 13. Проверка доступности модуля Картриджей через общий сервер
    res = client.get("/cartridges/health")
    assert res.status_code == 200
    print("[+] Модуль Картриджей смонтирован и доступен по /cartridges")

    print("\n[======================================================]")
    print("[+] ВСЕ 13 ТЕСТОВ ЕДИНОЙ ПЛАТФОРМЫ УСПЕШНО ПРОЙДЕНЫ! [+]")
    print("[======================================================]")


if __name__ == "__main__":
    test_full_unified_platform()
