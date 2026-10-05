"""Security configuration shared by all entry points. No embedded credentials."""
import os
from pathlib import Path
from urllib.parse import urlsplit


from SHARED.config_values import secret


ENVIRONMENT = os.getenv("APP_ENV", "production").lower()
if ENVIRONMENT not in {"production", "development", "test"}:
    raise RuntimeError("Invalid APP_ENV")
PRODUCTION = ENVIRONMENT == "production"
SECRET_KEY = secret("SECRET_KEY", required=True)
if len(SECRET_KEY.encode()) < 32 or len(set(SECRET_KEY)) < 12:
    raise RuntimeError("SECRET_KEY must be a randomly generated secret of at least 32 bytes")
DATABASE_URL = secret("DATABASE_URL", required=PRODUCTION)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///" + (Path(__file__).resolve().parents[1] / "BD/app_unified.db").as_posix()
if PRODUCTION and not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
    raise RuntimeError("Production requires PostgreSQL")
if PRODUCTION and not urlsplit(DATABASE_URL).password:
    raise RuntimeError("Production DATABASE_URL requires credentials")
REDIS_URL = secret("REDIS_URL", required=PRODUCTION)
if REDIS_URL and (urlsplit(REDIS_URL).scheme not in {"redis", "rediss"} or (PRODUCTION and not urlsplit(REDIS_URL).password)):
    raise RuntimeError("Invalid Redis URL or missing production Redis credentials")
EVOLUTION_API_KEY = secret("EVOLUTION_API_KEY", required=PRODUCTION and os.getenv("WHATSAPP_ENABLED") == "true")
NETWORK_CREDENTIAL_KEY = secret("NETWORK_CREDENTIAL_KEY", required=PRODUCTION)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
if not 1 <= ACCESS_TOKEN_EXPIRE_MINUTES <= 120:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 120")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = os.getenv("JWT_ISSUER", "rep-zap-inv")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "rep-zap-inv-web")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DEMO_ENABLED = os.getenv("DEMO_ENABLED", "false").lower() == "true"
if PRODUCTION and (DEBUG or DEMO_ENABLED):
    raise RuntimeError("DEBUG and DEMO_ENABLED are forbidden in production")
CORS_ORIGINS = [v.strip() for v in os.getenv("CORS_ORIGINS", "").split(",") if v.strip()]
for origin in CORS_ORIGINS:
    parsed = urlsplit(origin)
    if parsed.scheme not in ({"https"} if PRODUCTION else {"http", "https"}) or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or "*" in origin:
        raise RuntimeError("CORS_ORIGINS must contain explicit origins (HTTPS in production)")
TLS_CA_FILE = os.getenv("TLS_CA_FILE") or None
SSH_KNOWN_HOSTS = os.getenv("SSH_KNOWN_HOSTS") or None
