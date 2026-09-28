from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import AppUser, Branch

security = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {
    "superadmin": 40,
    "admin": 30,
    "technician": 20,
    "operator": 20,
    "viewer": 10
}


class AuthService:
    from SHARED.passwords import hash_password as _hash, verify_password as _verify
    hash_password = staticmethod(_hash)
    verify_password = staticmethod(_verify)

    from SHARED.tokens import create_access_token as _create, decode_access_token as _decode
    create_access_token = staticmethod(_create)
    decode_access_token = staticmethod(_decode)

    @staticmethod
    def authenticate_local_user(db: Session, username: str, password: str) -> Optional[AppUser]:
        """Локальная аутентификация пользователя."""
        user = db.query(AppUser).filter(
            AppUser.username == username.strip(),
            AppUser.is_active == True, AppUser.auth_type == "local"
        ).first()
        if not user or not user.password_hash:
            return None
        if AuthService.verify_password(password, user.password_hash):
            return user
        return None

    @staticmethod
    def check_branch_access(user: AppUser, target_branch_id: Optional[int]) -> bool:
        """
        Проверка прав доступа к филиалу:
        - superadmin имеет доступ ко всем филиалам (target_branch_id любой)
        - пользователь без филиала не получает глобальный доступ
        - иначе target_branch_id должен совпадать с user.branch_id
        """
        if user.role == "superadmin":
            return True
        if target_branch_id is None:
            return False
        return user.branch_id == target_branch_id


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> AppUser:
    """Dependency для получения текущего авторизованного пользователя из Bearer JWT."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация в системе",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = AuthService.decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия устарела или токен недействителен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректная структура токена авторизации",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(AppUser).filter(AppUser.username == username, AppUser.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь заблокирован или не найден",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_business_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    """Global API/print guard using the same request session as router dependencies."""
    path = request.url.path
    login_paths = {"/api/auth/login", "/api/v1/auth/login", "/cartridges/api/auth/login"}
    if request.method != "OPTIONS" and path not in login_paths and ("/api/" in path or "/print/" in path):
        return get_current_user(credentials, db)
    return None


def require_role(allowed_roles: List[str]):
    """Генератор dependency для проверки ролей."""
    def role_checker(current_user: AppUser = Depends(get_current_user)) -> AppUser:
        user_role = current_user.role or "viewer"
        if "superadmin" in allowed_roles and user_role == "superadmin":
            return current_user
        if user_role not in allowed_roles and user_role != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав. Требуется одна из ролей: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


def require_superadmin(current_user: AppUser = Depends(get_current_user)) -> AppUser:
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Данное действие доступно только Главному Администратору (SuperAdmin)"
        )
    return current_user

