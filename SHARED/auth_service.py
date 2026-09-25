import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from SHARED.config import SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS
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
    @staticmethod
    def hash_password(password: str) -> str:
        """Хэширует пароль с солью (PBKDF2-HMAC-SHA256)."""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100000
        )
        return f"{salt}${key.hex()}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Сверяет открытый пароль с сохраненным хэшем."""
        if not hashed or "$" not in hashed:
            return False
        try:
            salt, stored_key = hashed.split("$", 1)
            key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations=100000
            )
            return secrets.compare_digest(key.hex(), stored_key)
        except Exception:
            return False

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Создает подписанный JWT токен доступа для SSO."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
        """Декодирует и проверяет валидность JWT токена."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except (jwt.PyJWTError, Exception):
            return None

    @staticmethod
    def authenticate_local_user(db: Session, username: str, password: str) -> Optional[AppUser]:
        """Локальная аутентификация пользователя."""
        user = db.query(AppUser).filter(
            AppUser.username == username.strip(),
            AppUser.is_active == True
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
        - пользователь с branch_id = None имеет доступ ко всем филиалам
        - иначе target_branch_id должен совпадать с user.branch_id
        """
        if user.role == "superadmin" or user.branch_id is None:
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
