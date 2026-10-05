from SHARED.policies.static import LocationStaticFiles
from SHARED.auth_service import require_business_auth
from SHARED.security_config import CORS_ORIGINS
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException, status, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# Добавляем корень проекта и подпапки в путь поиска модулей
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

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
    dependencies=[Depends(require_business_auth)],
    title="Unified IT Enterprise Platform",
    description="Единая платформа: Учет картриджей, Ремонт техники и Интерактивная карта сети (ITAM)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# ЕДИНАЯ АВТОРИЗАЦИЯ (SSO AUTH API)
# ==========================================

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)
    auth_type: str = "local" # "local" | "ad"


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Единая точка аутентификации (Single Sign-On) для всех трех приложений."""
    from SHARED.login_security import check_login
    from CARTRIDGE.app.services.auth_service import AuthService as LoginService
    check_login(request, payload.username)
    user = LoginService.authenticate_user(db, payload.username, payload.password, payload.auth_type)

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
            "branch_id": user.branch_id,
            "must_change_password": user.must_change_password
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
        "auth_type": current_user.auth_type,
        "must_change_password": current_user.must_change_password
    }


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


@app.post('/api/v1/auth/change-password')
def change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db),
                    current_user: AppUser = Depends(get_current_user)):
    if current_user.auth_type != 'local':
        raise HTTPException(400, 'Пароль доменной учётной записи меняется в Active Directory')
    if not AuthService.verify_password(payload.current_password, current_user.password_hash or ''):
        raise HTTPException(400, 'Текущий пароль неверен')
    if payload.new_password == 'admin123' or payload.new_password == payload.current_password:
        raise HTTPException(422, 'Укажите новый пароль, отличный от начального и текущего')
    current_user.password_hash = AuthService.hash_password(payload.new_password)
    current_user.must_change_password = False
    db.commit()
    return {'success': True}


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

# Авторизация картриджей на корневом уровне для SSO совместимости
from CARTRIDGE.app.routers.auth_router import router as cartridge_auth_router
app.include_router(cartridge_auth_router)


# ==========================================
# МОНТИРОВАНИЕ ПОДСИСТЕМ (SUB-APPS) И СТАТИКИ
# ==========================================

CARTRIDGE_STATIC_DIR = BASE_DIR / "CARTRIDGE" / "app" / "static"
REPAIR_STATIC_DIR = BASE_DIR / "REPAIR" / "app" / "static"
LOCATION_STATIC_DIR = BASE_DIR / "LOCATION" / "app" / "static"

# Статика модулей
app.mount("/cartridges/static", StaticFiles(directory=str(CARTRIDGE_STATIC_DIR)), name="cartridges_static")
app.mount("/repair/static", StaticFiles(directory=str(REPAIR_STATIC_DIR)), name="repair_static")
app.mount("/location/static", LocationStaticFiles(directory=str(LOCATION_STATIC_DIR)), name="location_static")

# Прямые маршруты для обратной совместимости со старыми абсолютными путями браузера
@app.get("/static/js/app.js")
def get_cartridge_app_js():
    return FileResponse(str(CARTRIDGE_STATIC_DIR / "js" / "app.js"))

@app.get("/static/js/qr-scanner.js")
def get_cartridge_qr_scanner_js():
    return FileResponse(str(CARTRIDGE_STATIC_DIR / "js" / "qr-scanner.js"))

@app.get("/static/css/custom.css")
def get_cartridge_custom_css():
    return FileResponse(str(CARTRIDGE_STATIC_DIR / "css" / "custom.css"))

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
    from sqlalchemy import text
    try:
        from SHARED.database import SessionLocal
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    if database != "ok":
        raise HTTPException(status_code=503, detail="Database health check failed")
    return {
        "status": "ok",
        "platform": "unified-it-enterprise",
        "database": database,
        "modules": ["cartridges", "repair", "location", "portal"]
    }


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="Unified IT Enterprise Platform Server")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port to listen on (default 8000 or 80)")
    parser.add_argument("--host", type=str, default=os.getenv("HOST", "0.0.0.0"), help="Host to bind to")  # nosec B104 - container/dev server bind address
    parser.add_argument("--reload", action="store_true", default=False, help="Enable auto-reload")
    args = parser.parse_args()

    print(f"[*] Starting Unified IT Enterprise Platform on http://{args.host}:{args.port}")
    uvicorn.run("main_server:app", host=args.host, port=args.port, reload=args.reload, access_log=False)


from SHARED.http_security import install as install_http_security
install_http_security(app)
