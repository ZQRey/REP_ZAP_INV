import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Добавляем корень проекта и подпапки в путь поиска модулей
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "CARTRIDGE"))

from SHARED.database import init_db, get_db
from SHARED.models import AppUser, Branch, SystemSetting, ADUser
from SHARED.auth_service import AuthService, get_current_user, require_role, require_superadmin
from SHARED.ldap_service import LDAPService

# Подключение подсистем
from CARTRIDGE.app.main import app as cartridge_app
from REPAIR.app.main import app as repair_app
from LOCATION.app.main import app as location_app
from REPAIR.app.routers.repair_print_router import router as repair_print_router
from CARTRIDGE.app.routers.print_router import router as cartridge_print_router
from CARTRIDGE.app.routers.branches_router import router as branches_router
from CARTRIDGE.app.routers.settings_router import router as settings_router
from CARTRIDGE.app.routers.users_router import router as ad_users_router
from CARTRIDGE.app.routers.app_users_router import router as app_users_router


PORTAL_STATIC_DIR = BASE_DIR / "PORTAL" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация единой базы данных в BD/app_unified.db
    init_db()
    yield


app = FastAPI(
    title="Unified IT Enterprise Platform",
    description="Единая платформа: Учет картриджей, Ремонт техники и Интерактивная карта сети (ITAM)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# ЕДИНАЯ АВТОРИЗАЦИЯ (SSO AUTH API)
# ==========================================

class LoginRequest(BaseModel):
    username: str
    password: str
    auth_type: str = "local" # "local" | "ad"


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Единая точка аутентификации (Single Sign-On) для всех трех приложений."""
    username = payload.username.strip()
    password = payload.password

    user = None
    # 1. Локальная проверка
    if payload.auth_type == "local" or True:
        user = AuthService.authenticate_local_user(db, username, password)

    # 2. Если не найден локально или указан AD, проверяем домен
    if not user and payload.auth_type == "ad":
        # Проверяем учетку в AD через LDAP bind
        settings = LDAPService.get_ldap_settings(db)
        host = settings.get("ad_host")
        if host:
            try:
                from ldap3 import Server, Connection, ALL
                server = Server(host, get_info=ALL, connect_timeout=5)
                # Пытаемся забиндиться пользователем
                bind_dn = f"{username}@{settings.get('ad_base_dn', '').replace('DC=', '').replace(',', '.')}"
                conn = Connection(server, user=bind_dn, password=password)
                if conn.bind():
                    # Создаем или находим локального пользователя с ролью operator
                    user = db.query(AppUser).filter(AppUser.username == username).first()
                    if not user:
                        user = AppUser(
                            username=username,
                            full_name=username,
                            auth_type="ad",
                            role="operator",
                            is_active=True
                        )
                        db.add(user)
                        db.commit()
                        db.refresh(user)
                    conn.unbind()
            except Exception as e:
                pass

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль"
        )

    # Генерация JWT токена
    token = AuthService.create_access_token(data={
        "sub": user.username,
        "role": user.role,
        "branch_id": user.branch_id,
        "full_name": user.full_name
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "branch_id": user.branch_id
        }
    }


@app.get("/api/v1/auth/me")
def get_current_profile(current_user: AppUser = Depends(get_current_user)):
    """Информация о текущем авторизованном пользователе."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "branch_id": current_user.branch_id,
        "branch_name": current_user.branch.name if current_user.branch else None,
        "auth_type": current_user.auth_type
    }


# Подключение роутеров модулей
from REPAIR.app.routers import (
    equipment_router,
    ad_computers_router,
    repair_batches_router,
    repair_reports_router,
    equipment_models_router
)
from LOCATION.app.routers import (
    floors_router,
    zones_router,
    assets_placement_router,
    switches_router,
    pathfinding_router
)
from CARTRIDGE.app.routers import (
    cartridges_router,
    batches_router,
    reports_router as cartridge_reports_router,
    models_router as cartridge_models_router,
    notifications_router
)

# ==========================================
# ОБЩИЕ API РОУТЕРЫ
# ==========================================
app.include_router(branches_router)
app.include_router(settings_router)
app.include_router(ad_users_router)
app.include_router(app_users_router)
app.include_router(repair_print_router)
app.include_router(cartridge_print_router)

# Роутеры ремонта
app.include_router(equipment_router.router)
app.include_router(ad_computers_router.router)
app.include_router(repair_batches_router.router)
app.include_router(repair_reports_router.router)
app.include_router(equipment_models_router.router)

# Роутеры локаций
app.include_router(floors_router.router)
app.include_router(zones_router.router)
app.include_router(assets_placement_router.router)
app.include_router(switches_router.router)
app.include_router(pathfinding_router.router)

# Роутеры картриджей
app.include_router(cartridges_router.router)
app.include_router(batches_router.router)
app.include_router(cartridge_reports_router.router)
app.include_router(cartridge_models_router.router)
app.include_router(notifications_router.router)


# ==========================================
# МОНТИРОВАНИЕ ПОДСИСТЕМ (SUB-APPS)
# ==========================================

# 1. Модуль картриджей: доступен по /cartridges
app.mount("/cartridges", cartridge_app)

# 2. Модуль ремонта техники: доступен по /repair
app.mount("/repair", repair_app)

# 3. Модуль интерактивной карты сети (ITAM): доступен по /location
app.mount("/location", location_app)

# Статика главного портала
app.mount("/static", StaticFiles(directory=str(PORTAL_STATIC_DIR)), name="portal-static")


# ==========================================
# ГЛАВНЫЙ ЭКРАН ПОРТАЛА (PORTAL HUB)
# ==========================================

@app.get("/")
def portal_index():
    return FileResponse(str(PORTAL_STATIC_DIR / "portal.html"))


@app.get("/health")
def unified_health():
    return {
        "status": "ok",
        "platform": "unified-it-enterprise",
        "database": "BD/app_unified.db",
        "modules": ["cartridges", "repair", "location", "portal"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_server.py:app", host="0.0.0.0", port=8000, reload=True)
