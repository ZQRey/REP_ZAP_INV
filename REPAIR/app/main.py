from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from REPAIR.app.routers import (
    equipment_router,
    ad_computers_router,
    repair_batches_router,
    repair_print_router,
    repair_reports_router,
    equipment_models_router
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Equipment Repair & Lifecycle API",
    description="Система учета и ремонта компьютерной техники и оборудования (без WhatsApp)",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(equipment_router.router)
app.include_router(ad_computers_router.router)
app.include_router(repair_batches_router.router)
app.include_router(repair_print_router.router)
app.include_router(repair_reports_router.router)
app.include_router(equipment_models_router.router)

# Статические файлы
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="repair-static")


@app.get("/health")
def health():
    return {"status": "ok", "service": "equipment-repair"}


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))
