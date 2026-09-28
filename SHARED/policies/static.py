"""Public application assets must not expose uploaded branch floor plans."""
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException


class LocationStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path.replace("\\", "/").split("/", 1)[0].lower() == "maps":
            raise HTTPException(404)
        return await super().get_response(path, scope)
