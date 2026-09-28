from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from SHARED.database import get_db
from SHARED.models import AppUser, Branch


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
        from SHARED.policies.core import Principal, require_branch_access
        try:
            require_branch_access(Principal.from_user(user), target_branch_id)
            return True
        except HTTPException:
            return False



from SHARED.authentication import (require_authenticated_user, get_current_user, require_role, require_superadmin)
from SHARED.policies.http import authorize_request as require_business_auth
