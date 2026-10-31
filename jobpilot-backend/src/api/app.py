from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from src.api import checks, companies, health, jobs, profile, settings_api
from src.config.settings import settings
from src.discovery.service import recover_runs

CLIENT_HEADER = "X-JobPilot"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _testing_router() -> APIRouter:
    router = APIRouter()

    @router.post("/health-echo")
    async def echo(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    return router


def create_app(testing: bool = False) -> FastAPI:
    app = FastAPI(title="JobPilot API")

    @app.on_event("startup")
    def _recover() -> None:
        if not testing:
            try:
                recover_runs()
            except Exception:  # DB not migrated yet: health reports db state
                pass

    @app.middleware("http")
    async def require_client_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # A cross-site form post cannot set custom headers, so this blocks CSRF.
        if request.method in MUTATING_METHODS and request.headers.get(CLIENT_HEADER) != "1":
            return JSONResponse({"detail": "missing_client_header"}, status_code=403)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_hosts))

    app.include_router(health.router, prefix="/api")
    app.include_router(companies.router, prefix="/api")
    app.include_router(checks.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")
    app.include_router(settings_api.router, prefix="/api")
    if testing:
        app.include_router(_testing_router(), prefix="/api")
    return app
