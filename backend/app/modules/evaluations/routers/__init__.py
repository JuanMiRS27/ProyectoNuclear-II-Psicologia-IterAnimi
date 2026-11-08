from fastapi import APIRouter

from app.modules.evaluations.routers.docente_router import router as docente_router
from app.modules.evaluations.routers.estudiante_router import router as estudiante_router

router = APIRouter()
router.include_router(docente_router)
router.include_router(estudiante_router)

__all__ = ["router"]
