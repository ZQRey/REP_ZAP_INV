"""Do not reflect validation inputs or log credential-bearing URLs."""
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def install(app):
    from SHARED.logging_security import install as install_logging
    install_logging()
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": e["loc"], "type": e["type"], "msg": "Invalid value"} for e in exc.errors()
        ]})

    @app.middleware("http")
    async def security_headers(request, call_next):
        if "token" in request.query_params:
            return JSONResponse(status_code=400, content={"detail": "Credentials in URLs are forbidden"},
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        path = request.url.path
        login_paths = {"/api/auth/login", "/api/v1/auth/login", "/cartridges/api/auth/login"}
        protected = "/api/" in path or "/print/" in path
        if protected and path not in login_paths and request.method != "OPTIONS":
            from starlette.concurrency import run_in_threadpool
            from SHARED.tokens import decode_access_token
            value = request.headers.get("authorization", "")
            kind, _, token = value.partition(" ")
            claims = decode_access_token(token) if kind.lower() == "bearer" else None
            def active_account():
                from SHARED.database import SessionLocal
                from SHARED.models import AppUser
                with SessionLocal() as db:
                    return db.query(AppUser.id).filter(AppUser.username == claims["sub"], AppUser.is_active == True).first() is not None
            if not claims or not await run_in_threadpool(active_account):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"},
                                    headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "/api/" in request.url.path:
            response.headers["Cache-Control"] = "no-store"
        return response
