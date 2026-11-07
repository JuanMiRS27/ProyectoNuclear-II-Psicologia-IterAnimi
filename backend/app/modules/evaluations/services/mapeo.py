"""Traducción de las entidades ORM (módulos 2 a 4) al dominio puro del módulo 5."""

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.cases.models import CasoEstudio, CriterioRubrica, Rubrica
from app.modules.evaluations.dominio import (
    CriterioEvaluable,
    Nivel,
    OpcionEvaluable,
    PreguntaEvaluable,
    RubricaEvaluable,
    SituacionAcademica,
)
from app.modules.participations.services import ParticipacionParaEvaluacion
from app.modules.sessions.models import Convocatoria


def _decimal(valor: Any) -> Decimal:
    if isinstance(valor, bool) or valor is None:
        raise ValueError("valor no numérico")
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def nivel(dato: Any) -> Nivel:
    """Acepta la forma almacenada (`min_aciertos_pct`) y la de CaseDSL (`minAciertosPct`)."""
    if not isinstance(dato, dict) or not isinstance(dato.get("nombre"), str):
        raise ValueError("nivel mal formado")
    umbral = dato.get("min_aciertos_pct", dato.get("minAciertosPct"))
    return Nivel(nombre=dato["nombre"], valor=_decimal(dato.get("valor")), min_aciertos_pct=None if umbral is None else _decimal(umbral))


def criterio(entidad: CriterioRubrica) -> CriterioEvaluable:
    try:
        niveles = tuple(nivel(n) for n in (entidad.niveles or []))
        invalidos = False
    except (ValueError, TypeError, InvalidOperation):
        niveles, invalidos = (), True
    return CriterioEvaluable(entidad.id, entidad.descripcion, entidad.peso, niveles, invalidos)


def rubrica(entidad: Rubrica | None) -> RubricaEvaluable | None:
    if entidad is None:
        return None
    return RubricaEvaluable(entidad.escala_max, tuple(criterio(c) for c in entidad.criterios))


def preguntas(caso: CasoEstudio) -> tuple[PreguntaEvaluable, ...]:
    return tuple(
        PreguntaEvaluable(
            id=p.id,
            enunciado=p.enunciado,
            criterio_id=p.criterio_id,
            opciones=tuple(OpcionEvaluable(o.id, o.texto, o.es_correcta, o.justificacion) for o in p.opciones),
            escenario=e.titulo,
        )
        for e in caso.escenarios
        for p in e.preguntas
    )


def situacion_de_participacion(datos: ParticipacionParaEvaluacion) -> SituacionAcademica:
    return SituacionAcademica(
        estudiante_id=datos.estudiante_id,
        convocatoria_id=datos.convocatoria_id,
        sesion_id=datos.sesion_id,
        rubrica=rubrica(datos.rubrica),
        preguntas=preguntas(datos.caso),
        participacion_id=datos.participacion_id,
        numero_intento=datos.numero_intento,
        estado=datos.estado,
        motivo_cierre=datos.motivo_cierre,
        respuestas=dict(datos.respuestas),
    )


def situacion_de_ausencia(convocatoria: Convocatoria, sesion_id: uuid.UUID) -> SituacionAcademica:
    return SituacionAcademica(
        estudiante_id=convocatoria.estudiante_id,
        convocatoria_id=convocatoria.id,
        sesion_id=sesion_id,
        rubrica=None,
        preguntas=(),
    )
