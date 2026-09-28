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
        response = await call_next(request)
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "/api/" in request.url.path:
            response.headers["Cache-Control"] = "no-store"
        return response
