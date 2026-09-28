"""Strict, short-lived JWTs used by both authentication implementations."""
from datetime import datetime, timedelta, timezone
import secrets
import jwt
from SHARED.security_config import (
    SECRET_KEY, JWT_ALGORITHM, JWT_ISSUER, JWT_AUDIENCE, ACCESS_TOKEN_EXPIRE_MINUTES,
)


def create_access_token(data, expires_delta=None):
    now = datetime.now(timezone.utc)
    lifetime = expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    if not timedelta(0) < lifetime <= timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES):
        raise ValueError("Invalid token lifetime")
    if not isinstance(data.get("sub"), str) or not data["sub"]:
        raise ValueError("Token subject required")
    return jwt.encode({**data, "iat": now, "nbf": now, "exp": now + lifetime,
                       "iss": JWT_ISSUER, "aud": JWT_AUDIENCE, "jti": secrets.token_urlsafe(24)},
                      SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM],
                          issuer=JWT_ISSUER, audience=JWT_AUDIENCE,
                          options={"require": ["sub", "iat", "nbf", "exp", "iss", "aud", "jti"]})
    except jwt.PyJWTError:
        return None
