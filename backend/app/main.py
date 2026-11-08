from fastapi import FastAPI

from app.bootstrap import configurar_integraciones
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.modules.auth.routers import router as auth_module_router
from app.modules.cases.routers import router as cases_module_router
from app.modules.evaluations.routers import router as evaluations_module_router
from app.modules.notifications.routers import router as notifications_module_router
from app.modules.participations.routers import router as participations_module_router
from app.modules.reports.routers import router as reports_module_router
from app.modules.sessions.routers import router as sessions_module_router


def create_app() -> FastAPI:
    settings = get_settings()
    configurar_integraciones()
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Backend del Simulador de Psicología Social (Inter Nos): módulos 1 a 7.",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    register_exception_handlers(app)

    # Cada módulo aporta su router (módulos 1 a 7).
    app.include_router(auth_module_router, prefix=settings.API_V1_PREFIX)
    app.include_router(cases_module_router, prefix=settings.API_V1_PREFIX)
    app.include_router(sessions_module_router, prefix=settings.API_V1_PREFIX)
    app.include_router(participations_module_router, prefix=settings.API_V1_PREFIX)
    app.include_router(evaluations_module_router, prefix=settings.API_V1_PREFIX)
    app.include_router(notifications_module_router, prefix=settings.API_V1_PREFIX)
    app.include_router(reports_module_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["Sistema"], summary="Comprobación de disponibilidad")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
