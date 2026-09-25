from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import EquipmentModel, AppUser
from SHARED.auth_service import get_current_user, require_role
from REPAIR.app.schemas import EquipmentModelResponse, EquipmentModelCreate

router = APIRouter(prefix="/api/v1/repair/models", tags=["Equipment Models"])


@router.get("", response_model=List[EquipmentModelResponse])
def list_equipment_models(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """Справочник моделей компьютерного и офисного оборудования."""
    query = db.query(EquipmentModel)
    if category:
        query = query.filter(EquipmentModel.category == category)
    return query.order_by(EquipmentModel.name).all()


@router.post("", response_model=EquipmentModelResponse)
def create_equipment_model(
    payload: EquipmentModelCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Добавить новую модель в справочник."""
    existing = db.query(EquipmentModel).filter(EquipmentModel.name.ilike(payload.name.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail="Модель с таким наименованием уже существует")

    model_obj = EquipmentModel(
        name=payload.name.strip(),
        category=payload.category,
        vendor=payload.vendor.strip() if payload.vendor else None,
        specs_template=payload.specs_template,
        notes=payload.notes
    )
    db.add(model_obj)
    db.commit()
    db.refresh(model_obj)
    return model_obj


@router.delete("/{model_id}")
def delete_equipment_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin"]))
):
    """Удалить модель из справочника."""
    model_obj = db.query(EquipmentModel).filter(EquipmentModel.id == model_id).first()
    if not model_obj:
        raise HTTPException(status_code=404, detail="Модель не найдена")

    db.delete(model_obj)
    db.commit()
    return {"success": True, "message": "Модель успешно удалена"}
