"""Retroalimentación académica construida SOLO con el contenido definido por el docente.

No genera explicaciones nuevas (ni con IA ni con plantillas psicológicas): por cada pregunta
reúne el enunciado, la opción elegida, si fue acierto, las opciones correctas y sus
justificaciones (módulo 2) y el criterio asociado. El resumen general solo enuncia cifras
del cálculo y las observaciones de la estrategia aplicada.

Es determinista y no se persiste: se deriva siempre de datos inmutables (contenido de un
caso publicado y respuestas de un intento cerrado). `participacion.retroalimentacion_general`
queda reservada al texto que escriba el docente, que así nunca se sobrescribe.
"""

import uuid
from dataclasses import dataclass

from app.modules.evaluations.dominio import (
    PoliticaCriterio,
    PreguntaEvaluable,
    ResultadoEvaluacion,
    ResultadoPregunta,
    RubricaEvaluable,
    redondear,
)


@dataclass(frozen=True, slots=True)
class OpcionRetro:
    id: uuid.UUID
    texto: str
    justificacion: str | None


@dataclass(frozen=True, slots=True)
class RetroPregunta:
    pregunta_id: uuid.UUID
    escenario: str
    enunciado: str
    criterio_id: uuid.UUID | None
    criterio: str | None
    resultado: ResultadoPregunta
    opcion_elegida: OpcionRetro | None
    opciones_correctas: tuple[OpcionRetro, ...]
    mensaje: str


_MENSAJES = {
    ResultadoPregunta.ACIERTO: "Respuesta correcta.",
    ResultadoPregunta.ERROR: "Respuesta incorrecta.",
    ResultadoPregunta.SIN_RESPUESTA: "No respondiste esta pregunta.",
}


class RetroalimentacionService:
    def por_pregunta(
        self, resultado: ResultadoEvaluacion, preguntas: tuple[PreguntaEvaluable, ...], rubrica: RubricaEvaluable | None
    ) -> list[RetroPregunta]:
        if resultado.desglose is None:
            return []
        criterios = {c.id: c.descripcion for c in (rubrica.criterios if rubrica else ())}
        por_id = {p.id: p for p in preguntas}
        retro = []
        for correccion in resultado.desglose.correcciones:
            pregunta = por_id[correccion.pregunta_id]
            opciones = {o.id: o for o in pregunta.opciones}
            elegida = opciones.get(correccion.opcion_elegida_id) if correccion.opcion_elegida_id else None
            retro.append(
                RetroPregunta(
                    pregunta_id=pregunta.id,
                    escenario=pregunta.escenario,
                    enunciado=pregunta.enunciado,
                    criterio_id=pregunta.criterio_id,
                    criterio=criterios.get(pregunta.criterio_id) if pregunta.criterio_id else None,
                    resultado=correccion.resultado,
                    opcion_elegida=OpcionRetro(elegida.id, elegida.texto, elegida.justificacion) if elegida else None,
                    opciones_correctas=tuple(
                        OpcionRetro(o.id, o.texto, o.justificacion) for o in pregunta.opciones if o.es_correcta
                    ),
                    mensaje=_MENSAJES[correccion.resultado],
                )
            )
        return retro

    def general(self, resultado: ResultadoEvaluacion) -> str:
        partes = list(resultado.observaciones)
        desglose = resultado.desglose
        if desglose is not None:
            total = len(desglose.correcciones)
            partes.append(
                f"Aciertos: {desglose.aciertos} de {total}; errores: {desglose.errores}; sin responder: {desglose.sin_responder}."
            )
            for criterio in desglose.criterios:
                if criterio.politica == PoliticaCriterio.SIN_EVIDENCIA:
                    partes.append(f"«{criterio.descripcion}»: sin preguntas asociadas, no se evaluó.")
                    continue
                nivel = f", nivel {criterio.nivel}" if criterio.nivel else ""
                partes.append(
                    f"«{criterio.descripcion}»: {criterio.aciertos} de {criterio.total_preguntas} aciertos "
                    f"({redondear(criterio.porcentaje_aciertos)} %){nivel}."  # type: ignore[arg-type]
                )
            if resultado.nota is not None:
                partes.append(f"Nota: {resultado.nota} sobre {desglose.escala_max}.")
        return " ".join(partes)
