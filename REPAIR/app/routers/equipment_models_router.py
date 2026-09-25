from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from SHARED.database import get_db
from SHARED.models import EquipmentModel, Asset, AppUser
from SHARED.auth_service import get_current_user, require_role
from REPAIR.app.schemas import (
    EquipmentModelResponse,
    EquipmentModelCreate,
    EquipmentModelUpdate,
    ModelParseSuggestResponse
)
from REPAIR.app.services.model_parser_service import ModelParserService

router = APIRouter(prefix="/api/v1/repair/models", tags=["Equipment Models"])


@router.get("", response_model=List[EquipmentModelResponse])
def list_equipment_models(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """
    Справочник моделей компьютерного и сетевого оборудования.
    Возвращает список моделей с количеством закрепленных в организации устройств.
    """
    query = db.query(EquipmentModel)
    if category:
        query = query.filter(EquipmentModel.category == category)
    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                EquipmentModel.name.ilike(s),
                EquipmentModel.vendor.ilike(s),
                EquipmentModel.specs_template.ilike(s)
            )
        )

    models = query.order_by(EquipmentModel.name).all()

    # Подсчитываем количество устройств (units_count) для каждой модели
    result = []
    for m in models:
        m_name_clean = m.name.strip()
        # Ищем устройства в парке по прямому совпадению или подстроке
        count = db.query(func.count(Asset.id)).filter(
            or_(
                Asset.name.ilike(f"%{m_name_clean}%"),
                func.lower(m_name_clean).contains(func.lower(Asset.name))
            )
        ).scalar() or 0

        result.append(EquipmentModelResponse(
            id=m.id,
            name=m.name,
            category=m.category,
            vendor=m.vendor,
            specs_template=m.specs_template,
            notes=m.notes,
            units_count=count,
            created_at=m.created_at
        ))

    return result


@router.post("/sync-from-ad")
def sync_models_from_active_directory(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """
    Автоматическое формирование и пополнение справочника моделей на основе
    данных компьютеров, собранных из Active Directory и реестра техники.
    """
    return ModelParserService.sync_models_from_ad_computers(db=db)


@router.get("/suggest-specs", response_model=ModelParseSuggestResponse)
def suggest_model_specs(
    name: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    vendor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user)
):
    """
    Умный парсинг названия модели:
    - Автоматически выявляет производителя (Vendor)
    - Автоматически выявляет категорию/тип техники
    - Вычисляет средние типовые характеристики по парку компьютеров организации
    """
    parsed = ModelParserService.parse_model_details(name)
    resolved_vendor = vendor or parsed["vendor"]
    resolved_category = category or parsed["category"]

    stats = ModelParserService.calculate_average_specs(
        db=db,
        category=resolved_category,
        vendor=resolved_vendor,
        model_name=name
    )

    return ModelParseSuggestResponse(
        name=name.strip(),
        vendor=resolved_vendor,
        category=resolved_category,
        specs_template=stats.get("specs_template", ""),
        sample_size=stats.get("sample_size", 0),
        average_ram_gb=stats.get("average_ram_gb", 16),
        common_cpu=stats.get("common_cpu"),
        common_storage=stats.get("common_storage"),
        common_os=stats.get("common_os")
    )


@router.post("", response_model=EquipmentModelResponse)
def create_equipment_model(
    payload: EquipmentModelCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Добавить новую модель в справочник."""
    name_clean = payload.name.strip()
    existing = db.query(EquipmentModel).filter(EquipmentModel.name.ilike(name_clean)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Модель с таким наименованием уже существует")

    # Если вендор или характеристики не заполнены вручную, применим авто-парсинг
    parsed = ModelParserService.parse_model_details(name_clean)
    final_vendor = payload.vendor.strip() if payload.vendor else parsed.get("vendor")
    final_category = payload.category or parsed.get("category", "workstation")
    
    final_specs = payload.specs_template
    if not final_specs:
        stats = ModelParserService.calculate_average_specs(db, category=final_category, vendor=final_vendor, model_name=name_clean)
        final_specs = stats.get("specs_template")

    model_obj = EquipmentModel(
        name=name_clean,
        category=final_category,
        vendor=final_vendor,
        specs_template=final_specs,
        notes=payload.notes
    )
    db.add(model_obj)
    db.commit()
    db.refresh(model_obj)

    count = db.query(func.count(Asset.id)).filter(
        or_(
            Asset.name.ilike(f"%{name_clean}%"),
            func.lower(name_clean).contains(func.lower(Asset.name))
        )
    ).scalar() or 0

    return EquipmentModelResponse(
        id=model_obj.id,
        name=model_obj.name,
        category=model_obj.category,
        vendor=model_obj.vendor,
        specs_template=model_obj.specs_template,
        notes=model_obj.notes,
        units_count=count,
        created_at=model_obj.created_at
    )


@router.put("/{model_id}", response_model=EquipmentModelResponse)
def update_equipment_model(
    model_id: int,
    payload: EquipmentModelUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Редактировать модель в справочнике."""
    model_obj = db.query(EquipmentModel).filter(EquipmentModel.id == model_id).first()
    if not model_obj:
        raise HTTPException(status_code=404, detail="Модель не найдена")

    if payload.name is not None:
        name = payload.name.strip()
        existing = db.query(EquipmentModel).filter(
            EquipmentModel.name.ilike(name),
            EquipmentModel.id != model_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Модель с таким наименованием уже существует")
        model_obj.name = name

    if payload.category is not None:
        model_obj.category = payload.category
    if payload.vendor is not None:
        model_obj.vendor = payload.vendor.strip() if payload.vendor else None
    if payload.specs_template is not None:
        model_obj.specs_template = payload.specs_template
    if payload.notes is not None:
        model_obj.notes = payload.notes

    db.commit()
    db.refresh(model_obj)

    count = db.query(func.count(Asset.id)).filter(
        or_(
            Asset.name.ilike(f"%{model_obj.name}%"),
            func.lower(model_obj.name).contains(func.lower(Asset.name))
        )
    ).scalar() or 0

    return EquipmentModelResponse(
        id=model_obj.id,
        name=model_obj.name,
        category=model_obj.category,
        vendor=model_obj.vendor,
        specs_template=model_obj.specs_template,
        notes=model_obj.notes,
        units_count=count,
        created_at=model_obj.created_at
    )


@router.delete("/{model_id}")
def delete_equipment_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_role(["superadmin", "admin", "technician"]))
):
    """Удалить модель из справочника."""
    model_obj = db.query(EquipmentModel).filter(EquipmentModel.id == model_id).first()
    if not model_obj:
        raise HTTPException(status_code=404, detail="Модель не найдена")

    db.delete(model_obj)
    db.commit()
    return {"success": True, "message": "Модель успешно удалена"}
