"""Rutas del módulo 7 (`/api/v1`). Solo GET: ningún parámetro modifica datos.

Sin cálculos ni SQL: validan parámetros, exigen `DocenteUser` y delegan en los servicios.
Los filtros son modelos con `extra="forbid"`: un parámetro desconocido (p. ej., `docente_id`)
responde 422 en lugar de ignorarse, así que no pueden ampliar el alcance del docente.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.modules.auth.dependencies import DocenteUser
from app.modules.auth.schemas import MessageResponse
from app.modules.reports import exporters
from app.modules.reports import schemas as s
from app.modules.reports.dependencies import ExportacionDep, ReportesAcademicosDep, ReportesSesionDep
from app.modules.reports.repositories import FiltroEstudiantes, FiltroSesiones
from app.modules.reports.services import ArchivoExportado

router = APIRouter(tags=["Seguimiento y reportes"])

NO_STORE = {"Cache-Control": "no-store"}


def _r(*codigos: int) -> dict:
    textos = {
        401: "No autenticado (también con tokens `student` o `student_results`).",
        403: "Se requiere rol DOCENTE.",
        404: "Sesión, estudiante, caso o espacio inexistente o sin acceso para este docente.",
        422: "Parámetros inválidos o desconocidos, rango de fechas inválido o exportación que supera el máximo de filas.",
    }
    return {c: {"model": MessageResponse, "description": textos[c]} for c in codigos}


LECTURA = _r(401, 403, 404, 422)
CSV = {200: {"content": {"text/csv": {}}, "description": "Archivo CSV (UTF-8 con BOM)."}}


def _estudiantes(f: s.FiltrosEstudiantes | s.ExportacionSesion) -> FiltroEstudiantes:
    return FiltroEstudiantes(
        convocatoria=f.convocatoria,
        condicion=f.condicion,
        estado_participacion=f.estado_participacion,
        con_nota=f.con_nota,
        intento_activo=f.intento_activo,
        buscar=f.buscar,
    )


def _descarga(archivo: ArchivoExportado) -> Response:
    return Response(content=archivo.contenido, media_type=exporters.TIPO_CONTENIDO_CSV, headers=exporters.cabeceras_descarga(archivo.nombre))


# --- Sesión ----------------------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}/reports/summary",
    response_model=s.ResumenSesionRead,
    summary="Resumen de seguimiento de la sesión",
    description="Información de la sesión, convocatorias, intentos por estado e indicadores con numerador y denominador. "
    "Disponible en cualquier estado de la sesión (seguimiento operativo).",
    responses=LECTURA,
)
def session_summary(session_id: uuid.UUID, docente: DocenteUser, service: ReportesSesionDep, response: Response) -> s.ResumenSesionRead:
    response.headers.update(NO_STORE)
    return service.resumen(session_id, docente.id)


@router.get(
    "/sessions/{session_id}/reports/students",
    response_model=s.EstudiantesReporteList,
    summary="Estudiantes convocados y su participación (paginado)",
    responses=LECTURA,
)
def session_students(
    session_id: uuid.UUID,
    filtros: Annotated[s.FiltrosEstudiantes, Query()],
    docente: DocenteUser,
    service: ReportesSesionDep,
    response: Response,
) -> s.EstudiantesReporteList:
    response.headers.update(NO_STORE)
    return service.estudiantes(session_id, docente.id, _estudiantes(filtros), skip=filtros.skip, limit=filtros.limit)


@router.get(
    "/sessions/{session_id}/reports/students/{student_id}",
    response_model=s.DesempenoEstudianteRead,
    summary="Historial de intentos de un estudiante en la sesión",
    description="Cada intento por separado, ordenado por número de intento. No se consolida una nota.",
    responses=LECTURA,
)
def session_student(
    session_id: uuid.UUID, student_id: uuid.UUID, docente: DocenteUser, service: ReportesSesionDep, response: Response
) -> s.DesempenoEstudianteRead:
    response.headers.update(NO_STORE)
    return service.desempeno_estudiante(session_id, student_id, docente.id)


@router.get(
    "/sessions/{session_id}/reports/grades",
    response_model=s.NotasSesionRead,
    summary="Estadísticas de las calificaciones registradas (por intento)",
    responses=LECTURA,
)
def session_grades(session_id: uuid.UUID, docente: DocenteUser, service: ReportesSesionDep, response: Response) -> s.NotasSesionRead:
    response.headers.update(NO_STORE)
    return service.notas(session_id, docente.id)


@router.get(
    "/sessions/{session_id}/reports/criteria",
    response_model=s.CriteriosSesionRead,
    summary="Desempeño por criterio de la rúbrica",
    responses=LECTURA,
)
def session_criteria(session_id: uuid.UUID, docente: DocenteUser, service: ReportesSesionDep, response: Response) -> s.CriteriosSesionRead:
    response.headers.update(NO_STORE)
    return service.criterios(session_id, docente.id)


@router.get(
    "/sessions/{session_id}/reports/questions",
    response_model=s.PreguntasSesionRead,
    summary="Desempeño por pregunta",
    responses=LECTURA,
)
def session_questions(session_id: uuid.UUID, docente: DocenteUser, service: ReportesSesionDep, response: Response) -> s.PreguntasSesionRead:
    response.headers.update(NO_STORE)
    return service.preguntas(session_id, docente.id)


@router.get(
    "/sessions/{session_id}/reports/export",
    response_class=Response,
    summary="Exportar un reporte de la sesión (CSV)",
    description="`tipo`: resumen, estudiantes, intentos, criterios o preguntas. Los filtros de estudiantes se aplican a "
    f"`estudiantes` e `intentos`. Máximo {exporters.MAX_FILAS_EXPORTACION} filas.",
    responses={**CSV, **LECTURA},
)
def export_session(
    session_id: uuid.UUID, parametros: Annotated[s.ExportacionSesion, Query()], docente: DocenteUser, service: ExportacionDep
) -> Response:
    return _descarga(service.exportar_sesion(session_id, docente.id, parametros.tipo, _estudiantes(parametros)))


# --- Seguimiento académico ------------------------------------------------------------------------------


@router.get(
    "/reports/my-sessions",
    response_model=s.SesionesReporteList,
    summary="Mis sesiones con sus indicadores (paginado)",
    description="Filtro temporal sobre `inicio` de la sesión: intervalo semiabierto [desde, hasta), en UTC.",
    responses=_r(401, 403, 422),
)
def my_sessions(
    filtros: Annotated[s.FiltrosSesiones, Query()], docente: DocenteUser, service: ReportesAcademicosDep, response: Response
) -> s.SesionesReporteList:
    response.headers.update(NO_STORE)
    filtro = FiltroSesiones(
        docente.id, filtros.estado, filtros.espacio_academico_id, filtros.caso_id, filtros.desde, filtros.hasta
    )
    return service.mis_sesiones(filtro, skip=filtros.skip, limit=filtros.limit)


@router.get(
    "/academic-spaces/{space_id}/reports",
    response_model=s.EspacioReporteRead,
    summary="Seguimiento del espacio académico (solo mis sesiones)",
    responses=LECTURA,
)
def space_report(
    space_id: uuid.UUID,
    filtros: Annotated[s.FiltrosSesionesEspacio, Query()],
    docente: DocenteUser,
    service: ReportesAcademicosDep,
    response: Response,
) -> s.EspacioReporteRead:
    response.headers.update(NO_STORE)
    filtro = FiltroSesiones(docente.id, filtros.estado, space_id, filtros.caso_id, filtros.desde, filtros.hasta)
    return service.espacio(space_id, filtro, skip=filtros.skip, limit=filtros.limit)


@router.get(
    "/academic-spaces/{space_id}/reports/export",
    response_class=Response,
    summary="Exportar las sesiones del espacio académico (CSV, solo mis sesiones)",
    responses={**CSV, **LECTURA},
)
def export_space(
    space_id: uuid.UUID, parametros: Annotated[s.ExportacionEspacio, Query()], docente: DocenteUser, service: ExportacionDep
) -> Response:
    filtro = FiltroSesiones(docente.id, parametros.estado, space_id, parametros.caso_id, parametros.desde, parametros.hasta)
    return _descarga(service.exportar_espacio(space_id, filtro))


@router.get(
    "/cases/{case_id}/reports",
    response_model=s.CasoReporteRead,
    summary="Historial académico del caso (autor; también casos ARCHIVADOS)",
    responses=LECTURA,
)
def case_report(
    case_id: uuid.UUID,
    filtros: Annotated[s.FiltrosSesionesCaso, Query()],
    docente: DocenteUser,
    service: ReportesAcademicosDep,
    response: Response,
) -> s.CasoReporteRead:
    response.headers.update(NO_STORE)
    filtro = FiltroSesiones(docente.id, filtros.estado, filtros.espacio_academico_id, case_id, filtros.desde, filtros.hasta)
    return service.caso(case_id, filtro, skip=filtros.skip, limit=filtros.limit)


__all__ = ["router"]
