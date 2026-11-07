"""Consulta de resultados por el estudiante, de solo lectura y solo con la sesión FINALIZADA."""

import uuid

from fastapi import APIRouter, Request, Response

from app.modules.auth.schemas import MessageResponse
from app.modules.evaluations.dependencies import AccesoResultadosDep, AccesoResultadosServiceDep, ConsultaResultadosDep
from app.modules.evaluations.schemas import (
    ResultadoEstudianteDetalle,
    ResultadosEstudianteRead,
    ResultadosLoginRequest,
    ResultadosTokenResponse,
)
from app.modules.sessions.dependencies import LimitadorDep

router = APIRouter(tags=["Resultados del estudiante"])

NO_STORE = {"Cache-Control": "no-store"}


def _r(*codigos: int) -> dict:
    textos = {
        401: "Credenciales o token de resultados ausente, inválido, expirado o revocado.",
        403: "Convocatoria revocada, cuenta desactivada o sesión aún no finalizada.",
        404: "Resultado inexistente o de otro estudiante.",
        409: "La evaluación de este intento aún no está registrada.",
        429: "Demasiados intentos fallidos; ver cabecera Retry-After.",
    }
    return {c: {"model": MessageResponse, "description": textos[c]} for c in codigos}


@router.post(
    "/auth/student/results-login",
    response_model=ResultadosTokenResponse,
    summary="Acceso de solo lectura a los resultados (correo + código de convocatoria)",
    description="Solo con la sesión FINALIZADA. El token emitido no sirve para participar, responder ni entrar a rutas "
    "docentes, y comparte el límite de intentos fallidos con el ingreso estudiantil.",
    responses=_r(401, 403, 429),
)
def results_login(
    data: ResultadosLoginRequest, request: Request, response: Response, service: AccesoResultadosServiceDep, limitador: LimitadorDep
) -> ResultadosTokenResponse:
    response.headers.update(NO_STORE)
    ip = request.client.host if request.client else "desconocida"
    token = service.ingresar_resultados(data.correo, data.codigo, ip, limitador)
    return ResultadosTokenResponse(
        access_token=token.access_token, expires_in=token.expires_in, sesion_id=token.sesion_id, convocatoria_id=token.convocatoria_id
    )


@router.get("/student/results", response_model=ResultadosEstudianteRead, summary="Mis resultados en la convocatoria", responses=_r(401))
def my_results(acceso: AccesoResultadosDep, service: ConsultaResultadosDep, response: Response) -> ResultadosEstudianteRead:
    response.headers.update(NO_STORE)
    return service.resultados_estudiante(acceso)


@router.get(
    "/student/results/{participation_id}",
    response_model=ResultadoEstudianteDetalle,
    summary="Calificación y retroalimentación de un intento propio",
    responses=_r(401, 404, 409),
)
def my_result(
    participation_id: uuid.UUID, acceso: AccesoResultadosDep, service: ConsultaResultadosDep, response: Response
) -> ResultadoEstudianteDetalle:
    response.headers.update(NO_STORE)
    return service.detalle_estudiante(acceso, participation_id)
