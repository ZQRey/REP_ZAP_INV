from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from SHARED.database import get_db
from SHARED.models import Asset, AppUser
from SHARED.auth_service import get_current_user, require_role
from SHARED.ldap_service import LDAPService
from REPAIR.app.schemas import ADComputerSyncResponse

router = APIRouter(prefix="/api/v1/repair/ad", tags=["AD Computer Sync"])


@router.post("/sync-computers", response_model=ADComputerSyncResponse)
def sync_computers_from_active_directory(
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """
    Автоматический сбор информации о компьютерах из Active Directory:
    - Запрашивает объекты компьютеров (objectCategory=computer)
    - Извлекает имя хоста, ОС, описание и последнее время входа
    - Автоматически создает/обновляет компьютеры в едином реестре активов
    - Остальная техника (мониторы, принтеры, ИБП) вводится вручную.
    """
    target_branch = branch_id or current_user.branch_id
    result = LDAPService.sync_ad_computers(db=db, default_branch_id=target_branch)

    return ADComputerSyncResponse(
        status=result.get("status", "info"),
        message=result.get("message", "Сбор завершен"),
        added=result.get("added", 0),
        updated=result.get("updated", 0)
    )


@router.get("/stats")
def get_ad_computer_stats(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Статистика собранных компьютеров из Active Directory."""
    total_ad_pcs = db.query(Asset).filter(Asset.ad_guid != None).count()
    total_manual = db.query(Asset).filter(Asset.ad_guid == None).count()
    return {
        "ad_computers_count": total_ad_pcs,
        "manual_equipment_count": total_manual,
        "total_assets": total_ad_pcs + total_manual
    }
