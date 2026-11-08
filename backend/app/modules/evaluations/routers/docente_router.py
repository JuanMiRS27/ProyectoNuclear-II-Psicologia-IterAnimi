"""Rutas docentes del módulo 5. Sin fórmulas: todo el cálculo vive en los servicios."""

import uuid

from fastapi import APIRouter

from app.modules.auth.dependencies import DocenteUser
from app.modules.auth.schemas import MessageResponse
from app.modules.evaluations.dependencies import ConsultaResultadosDep, EvaluacionServiceDep
from app.modules.evaluations.schemas import (
    AusenciaRead,
    EvaluacionDetalleRead,
    ProcesoEvaluacionRead,
    ResultadoProcesoRead,
    ResultadosSesionRead,
    RetroalimentacionRead,
    RetroalimentacionUpdate,
)
from app.modules.evaluations.services.consulta_resultados_service import dos_decimales

router = APIRouter(tags=["Evaluación"])


def _r(*codigos: int) -> dict:
    textos = {
        401: "No autenticado.",
        403: "Se requiere rol DOCENTE.",
        404: "Sesión o participación inexistente o de otro docente.",
        409: "La participación sigue en progreso.",
        422: "La rúbrica del caso no permite calcular una nota coherente (no se registra nada).",
    }
    return {c: {"model": MessageResponse, "description": textos[c]} for c in codigos}


@router.post(
    "/sessions/{session_id}/evaluations/process",
    response_model=ProcesoEvaluacionRead,
    summary="Evaluar las participaciones cerradas de la sesión",
    description="Aplica la estrategia correspondiente (completa o incompleta) a cada intento FINALIZADO o EXPIRADO "
    "y registra `nota_final` en una sola transacción. Idempotente: repetirlo con los mismos datos no cambia nada. "
    "Los intentos EN_PROGRESO se omiten; las ausencias se informan sin crear participaciones.",
    responses=_r(401, 403, 404, 422),
)
def process_evaluations(session_id: uuid.UUID, docente: DocenteUser, service: EvaluacionServiceDep) -> ProcesoEvaluacionRead:
    resumen = service.procesar_sesion(session_id, docente)
    return ProcesoEvaluacionRead(
        sesion_id=resumen.sesion_id,
        procesadas=resumen.procesadas,
        registradas=resumen.registradas,
        actualizadas=resumen.actualizadas,
        sin_cambios=resumen.sin_cambios,
        sin_calificar=resumen.sin_calificar,
        en_progreso_omitidas=resumen.en_progreso,
        ausencias=resumen.ausencias,
        resultados=[
            ResultadoProcesoRead(
                participacion_id=r.participacion_id, condicion=r.condicion, calificacion=r.calificacion, nota_final=dos_decimales(r.nota)
            )
            for r in resumen.resultados
        ],
    )


@router.get(
    "/sessions/{session_id}/evaluations",
    response_model=ResultadosSesionRead,
    summary="Resultados de la sesión (todos los intentos y las ausencias)",
    responses=_r(401, 403, 404),
)
def list_evaluations(session_id: uuid.UUID, docente: DocenteUser, service: ConsultaResultadosDep) -> ResultadosSesionRead:
    return service.resultados_sesion(session_id, docente)


@router.get(
    "/sessions/{session_id}/absences",
    response_model=list[AusenciaRead],
    summary="Ausencias: convocatorias activas sin ningún intento",
    responses=_r(401, 403, 404),
)
def list_absences(session_id: uuid.UUID, docente: DocenteUser, service: ConsultaResultadosDep) -> list[AusenciaRead]:
    return service.ausencias(session_id, docente)


@router.get(
    "/participations/{participation_id}/evaluation",
    response_model=EvaluacionDetalleRead,
    summary="Evaluación detallada de un intento",
    responses=_r(401, 403, 404, 409),
)
def get_evaluation(participation_id: uuid.UUID, docente: DocenteUser, service: ConsultaResultadosDep) -> EvaluacionDetalleRead:
    return service.detalle_docente(participation_id, docente)


@router.post(
    "/participations/{participation_id}/evaluation/recalculate",
    response_model=EvaluacionDetalleRead,
    summary="Recalcular y registrar la nota de un intento",
    description="Determinista e idempotente. No modifica la retroalimentación escrita por el docente.",
    responses=_r(401, 403, 404, 409, 422),
)
def recalculate_evaluation(
    participation_id: uuid.UUID, docente: DocenteUser, service: EvaluacionServiceDep, consulta: ConsultaResultadosDep
) -> EvaluacionDetalleRead:
    service.recalcular(participation_id, docente)
    return consulta.detalle_docente(participation_id, docente)


@router.patch(
    "/participations/{participation_id}/feedback",
    response_model=RetroalimentacionRead,
    summary="Registrar o modificar la retroalimentación general del docente",
    responses=_r(401, 403, 404, 409),
)
def update_feedback(
    participation_id: uuid.UUID, data: RetroalimentacionUpdate, docente: DocenteUser, service: EvaluacionServiceDep
) -> RetroalimentacionRead:
    participacion = service.actualizar_retroalimentacion(participation_id, docente, data.retroalimentacion_general)
    return RetroalimentacionRead(participacion_id=participacion.id, retroalimentacion_general=participacion.retroalimentacion_general)
