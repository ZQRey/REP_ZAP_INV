"""Single bearer authentication implementation; roles come from DB, never JWT claims."""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from SHARED.database import get_db
from SHARED.models import AppUser
from SHARED.tokens import decode_access_token
from SHARED.policies.core import Principal

security = HTTPBearer(auto_error=False)


def require_authenticated_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(security), db: Session = Depends(get_db)):
    cached = getattr(request.state, "authenticated_user", None)
    if cached is not None: return cached
    payload = decode_access_token(credentials.credentials) if credentials else None
    user = db.query(AppUser).filter(AppUser.username == payload.get("sub"), AppUser.is_active.is_(True)).first() if payload else None
    if user is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    if user.must_change_password and request.url.path not in {
        '/api/v1/auth/me', '/api/auth/me', '/cartridges/api/auth/me',
        '/api/v1/auth/change-password'
    }:
        raise HTTPException(403, 'password_change_required')
    request.state.principal = Principal.from_user(user)
    request.state.authenticated_user = user
    return user


def require_role(allowed_roles):
    def dependency(user=Depends(require_authenticated_user)):
        if user.role not in set(allowed_roles) | {"superadmin"}:
            raise HTTPException(403, "Role permission denied")
        return user
    return dependency


require_superadmin = require_role(["superadmin"])
require_admin = require_role(["admin"])
require_operator = require_role(["operator", "admin"])
get_current_user = require_authenticated_user
