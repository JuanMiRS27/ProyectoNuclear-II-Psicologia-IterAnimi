"""Dependencias del módulo 5.

- Rutas docentes: `DocenteUser` (módulo 1) + ser el docente responsable de la sesión (404 si no).
- Rutas de resultados del estudiante: token `student_results` (solo lectura, tras el cierre).
  El token de resolución (`student`) y el de docentes (`access`) no sirven aquí, y este no
  sirve en ninguna otra ruta.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError
from app.modules.auth.dependencies.auth import DbSession
from app.modules.evaluations.services.acceso_resultados_service import AccesoResultados, AccesoResultadosService
from app.modules.evaluations.services.consulta_resultados_service import ConsultaResultadosService
from app.modules.evaluations.services.evaluacion_service import EvaluacionService
from app.modules.sessions.dependencies import RelojDep

_bearer_resultados = HTTPBearer(auto_error=False, description="Token de resultados obtenido en /api/v1/auth/student/results-login")


def get_evaluacion_service(db: DbSession) -> EvaluacionService:
    return EvaluacionService(db)


def get_consulta_resultados_service(db: DbSession) -> ConsultaResultadosService:
    return ConsultaResultadosService(db)


def get_acceso_resultados_service(db: DbSession, reloj: RelojDep) -> AccesoResultadosService:
    return AccesoResultadosService(db, reloj)


EvaluacionServiceDep = Annotated[EvaluacionService, Depends(get_evaluacion_service)]
ConsultaResultadosDep = Annotated[ConsultaResultadosService, Depends(get_consulta_resultados_service)]
AccesoResultadosServiceDep = Annotated[AccesoResultadosService, Depends(get_acceso_resultados_service)]


def acceso_resultados_actual(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_resultados)],
    service: AccesoResultadosServiceDep,
) -> AccesoResultados:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Se requiere un token de consulta de resultados.")
    return service.resolver_resultados(credentials.credentials)


AccesoResultadosDep = Annotated[AccesoResultados, Depends(acceso_resultados_actual)]
