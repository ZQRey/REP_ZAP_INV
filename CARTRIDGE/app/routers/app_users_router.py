from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from SHARED.authentication import require_admin
from SHARED.database import get_db
from SHARED.models import AppUser, Branch
from SHARED.policies.core import Principal, require_user_management
from CARTRIDGE.app.schemas import AppUserCreate, AppUserUpdate, AppUserResponse
from CARTRIDGE.app.services.auth_service import AuthService

router = APIRouter(prefix="/api/app-users", tags=["AppUsers"])


@router.get("", response_model=List[AppUserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    """List application users visible to the current administrator."""
    return (
        db.query(AppUser)
        .options(joinedload(AppUser.branch))
        .order_by(AppUser.username.asc())
        .all()
    )


@router.post("", response_model=AppUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AppUserCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    """Create an application account within the administrator's allowed scope."""
    principal = Principal.from_user(current_user)
    username = payload.username.strip()
    existing = db.query(AppUser).filter(AppUser.username.ilike(username)).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Пользователь '{username}' уже существует.")

    role = payload.role
    branch_id = payload.branch_id
    if current_user.role != "superadmin":
        # Branch administrators can create only lower roles in their own branch.
        branch_id = current_user.branch_id

    require_user_management(principal, role=role, branch_id=branch_id)

    password_hash = None
    if payload.auth_type == "local":
        if not payload.password:
            raise HTTPException(
                status_code=400,
                detail="Для локального пользователя необходимо задать пароль.",
            )
        password_hash = AuthService.hash_password(payload.password)

    if branch_id is not None:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="Указанный филиал не существует.")

    user = AppUser(
        username=username,
        full_name=payload.full_name.strip(),
        password_hash=password_hash,
        auth_type=payload.auth_type,
        role=role,
        is_active=payload.is_active,
        branch_id=branch_id,
    )
    db.add(user)
    db.commit()

    return (
        db.query(AppUser)
        .options(joinedload(AppUser.branch))
        .filter(AppUser.id == user.id)
        .first()
    )


@router.put("/{user_id}", response_model=AppUserResponse)
def update_user(
    user_id: int,
    payload: AppUserUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    """Update an application user within the administrator's allowed scope."""
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    principal = Principal.from_user(current_user)
    requested_branch = payload.branch_id
    if current_user.role != "superadmin" and requested_branch is None:
        requested_branch = user.branch_id
    require_user_management(
        principal,
        target=user,
        role=payload.role,
        branch_id=requested_branch,
    )

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()

    if payload.password and payload.password.strip():
        user.password_hash = AuthService.hash_password(payload.password.strip())

    if payload.role is not None:
        if user.username == "admin" and payload.role != "superadmin":
            raise HTTPException(
                status_code=400,
                detail="Нельзя понизить роль главного администратора admin.",
            )
        user.role = payload.role

    if payload.is_active is not None:
        if user.username == "admin" and not payload.is_active:
            raise HTTPException(
                status_code=400,
                detail="Нельзя заблокировать главного администратора системы.",
            )
        user.is_active = payload.is_active

    if payload.branch_id is not None:
        if payload.branch_id in (0, -1):
            if current_user.role != "superadmin":
                raise HTTPException(403, "Branch administrator cannot grant global scope")
            user.branch_id = None
        else:
            branch = db.query(Branch).filter(Branch.id == payload.branch_id).first()
            if not branch:
                raise HTTPException(status_code=404, detail="Указанный филиал не существует.")
            user.branch_id = payload.branch_id

    db.commit()

    return (
        db.query(AppUser)
        .options(joinedload(AppUser.branch))
        .filter(AppUser.id == user.id)
        .first()
    )


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    """Delete an application account within the administrator's allowed scope."""
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    require_user_management(Principal.from_user(current_user), target=user)

    if user.username == "admin":
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить главного администратора admin.",
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить свою собственную учетную запись.",
        )

    db.delete(user)
    db.commit()
    return {"success": True, "message": f"Пользователь '{user.username}' удален."}


@router.post("/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_admin),
):
    """Enable or disable an application account within administrator scope."""
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")

    require_user_management(Principal.from_user(current_user), target=user)

    if user.username == "admin" and user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Нельзя заблокировать главного администратора системы.",
        )

    user.is_active = not user.is_active
    db.commit()
    return {
        "success": True,
        "is_active": user.is_active,
        "message": f"Пользователь '{user.username}' {'разблокирован' if user.is_active else 'заблокирован'}.",
    }
