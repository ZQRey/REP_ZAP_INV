"""Shared fixed-window login limits. Redis is mandatory in production."""
import hashlib
import threading
import time
from fastapi import HTTPException, Request
from SHARED.security_config import PRODUCTION, REDIS_URL

_lock = threading.Lock()
_attempts = {}
_redis = None
WINDOW = 300
ACCOUNT_LIMIT = 10
IP_LIMIT = 50
_SCRIPT = """
local a = redis.call('INCR', KEYS[1])
if a == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local b = redis.call('INCR', KEYS[2])
if b == 1 then redis.call('EXPIRE', KEYS[2], ARGV[1]) end
return {a,b}
"""


def check_login(request: Request, username: str):
    global _redis
    # Never trust arbitrary forwarded headers. Uvicorn's trusted proxy configuration
    # determines request.client; account limit also applies across all source IPs.
    account = username.strip().casefold().split("@")[0].split("\\")[-1]
    identity = request.client.host if request.client else "unknown"
    keys = ["login:{limits}:" + kind + ":" + hashlib.sha256(value.encode()).hexdigest()
            for kind, value in (("account", account), ("ip", identity))]
    if REDIS_URL:
        try:
            if _redis is None:
                import redis
                _redis = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
            counts = _redis.eval(_SCRIPT, 2, *keys, WINDOW)
        except Exception:
            raise HTTPException(503, "Authentication temporarily unavailable") from None
    else:
        if PRODUCTION:
            raise HTTPException(503, "Authentication temporarily unavailable")
        with _lock:
            now = time.monotonic()
            for key in list(_attempts):
                if _attempts[key][1] <= now:
                    del _attempts[key]
            if len(_attempts) > 10000:
                raise HTTPException(503, "Authentication temporarily unavailable")
            counts = []
            for key in keys:
                count, expiry = _attempts.get(key, (0, now + WINDOW))
                _attempts[key] = (count + 1, expiry)
                counts.append(count + 1)
    if counts[0] > ACCOUNT_LIMIT or counts[1] > IP_LIMIT:
        raise HTTPException(429, "Too many login attempts", headers={"Retry-After": str(WINDOW)})
