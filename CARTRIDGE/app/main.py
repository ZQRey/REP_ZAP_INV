from SHARED.auth_service import require_business_auth
from SHARED.security_config import CORS_ORIGINS
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from SHARED.database import init_db
from CARTRIDGE.app.routers import (
    auth_router,
    branches_router,
    app_users_router,
    settings_router,
    users_router,
    cartridges_router,
    batches_router,
    notifications_router,
    print_router,
    reports_router,
    models_router
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация таблиц БД, дефолтных настроек, филиалов и администратора
    init_db()
    yield


app = FastAPI(
    dependencies=[Depends(require_business_auth)],
    title="Cartridge Tracker API",
    description="Система учета и контроля оборота картриджей с интеграцией AD и WhatsApp",
    version="1.1.0",
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

# Подключение API роутеров
app.include_router(auth_router.router)
app.include_router(branches_router.router)
app.include_router(app_users_router.router)
app.include_router(settings_router.router)
app.include_router(users_router.router)
app.include_router(cartridges_router.router)
app.include_router(batches_router.router)
app.include_router(notifications_router.router)
app.include_router(print_router.router)
app.include_router(reports_router.router)
app.include_router(models_router.router)

# Статические файлы (CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "service": "cartridge-tracker"}


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


from SHARED.http_security import install as install_http_security
install_http_security(app)
