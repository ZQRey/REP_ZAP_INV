from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import AppUser
from app.services.ldap_service import LDAPService


security = HTTPBearer(auto_error=False)


class AuthService:
    from SHARED.passwords import hash_password as _hash, verify_password as _verify
    hash_password = staticmethod(_hash)
    verify_password = staticmethod(_verify)

    from SHARED.tokens import create_access_token as _create, decode_access_token as _decode
    create_access_token = staticmethod(_create)
    decode_access_token = staticmethod(_decode)

    @classmethod
    def authenticate_user(
        cls,
        db: Session,
        username: str,
        password: str,
        auth_type: str = "local"
    ) -> Optional[AppUser]:
        """
        Аутентифицирует пользователя локально или через Active Directory.
        """
        if auth_type not in ("local", "ad") or not username.strip() or not password:
            return None
        clean_user = username.strip()

        if auth_type == "ad":
            # Аутентифицируем в AD (поддерживает логин как без домена 'ivanov', так и 'ivanov@gp1.loc' или 'GP1\ivanov')
            success, sam_account, ad_profile = LDAPService.authenticate_ad_user(
                db=db,
                username=clean_user,
                password=password
            )
            if not success or not sam_account:
                return None

            # Если вход через AD успешен — ищем или создаем профиль AppUser по чистому sAMAccountName
            user = db.query(AppUser).filter(
                or_(
                    func.lower(AppUser.username) == sam_account.lower(),
                    func.lower(AppUser.username) == clean_user.lower()
                )
            ).first()

            if not user or user.auth_type != "ad" or not user.is_active:
                return None

            # Получаем или обновляем данные в ad_users
            from SHARED.models import ADUser
            ad_info = db.query(ADUser).filter(ADUser.samaccountname.ilike(sam_account)).first()
            if ad_profile:
                if not ad_info:
                    ad_info = ADUser(
                        samaccountname=ad_profile["samaccountname"],
                        display_name=ad_profile["display_name"],
                        department=ad_profile.get("department"),
                        cabinet=ad_profile.get("cabinet"),
                        phone=ad_profile.get("phone")
                    )
                    db.add(ad_info)
                    db.commit()
                else:
                    if ad_profile.get("display_name"):
                        ad_info.display_name = ad_profile["display_name"]
                    if ad_profile.get("department"):
                        ad_info.department = ad_profile["department"]
                    if ad_profile.get("cabinet"):
                        ad_info.cabinet = ad_profile["cabinet"]
                    if ad_profile.get("phone"):
                        ad_info.phone = ad_profile["phone"]
                    db.commit()

            display_name = (
                (ad_profile.get("display_name") if ad_profile else None)
                or (ad_info.display_name if ad_info else None)
                or sam_account
            )

            if not user.is_active:
                return None

            return user

        # Локальный вход
        user = db.query(AppUser).filter(func.lower(AppUser.username) == clean_user.lower()).first()
        if not user or user.auth_type != "local" or not user.password_hash:
            from SHARED.passwords import consume_dummy_check
            consume_dummy_check(password)
            return None

        if not cls.verify_password(password, user.password_hash) or not user.is_active:
            return None

        return user


def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[AppUser]:
    """Возвращает текущего пользователя из JWT токена, если токен передан."""
    if not auth:
        return None
    payload = AuthService.decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        return None
    username = payload["sub"]
    user = db.query(AppUser).filter(AppUser.username == username).first()
    if not user or not user.is_active:
        return None
    return user


def get_current_user(
    user: Optional[AppUser] = Depends(get_current_user_optional)
) -> AppUser:
    """Обязательная проверка авторизации для защищенных эндпоинтов."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация в системе.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_superadmin(user: AppUser = Depends(get_current_user)) -> AppUser:
    """Проверка прав: только Супер администратор (полный доступ к настройкам, пользователям и AD)."""
    if user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав. Требуются права Супер администратора."
        )
    return user


def require_admin(user: AppUser = Depends(get_current_user)) -> AppUser:
    """Проверка прав: Супер администратор или Администратор."""
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав. Требуются права Администратора."
        )
    return user


def require_operator(user: AppUser = Depends(get_current_user)) -> AppUser:
    """Проверка прав: Супер администратор, Администратор или Оператор (приемка, акты, выдача)."""
    if user.role not in ("operator", "admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав. Доступно только операторам и администраторам."
        )
    return user

