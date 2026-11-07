"""Consultas de resultados para docentes autorizados y estudiantes (solo lectura).

La nota que se muestra es SIEMPRE la registrada en `participacion.nota_final`. El desglose
se deriva con la misma estrategia; si la nota registrada no coincide con la calculada hoy
(p. ej., datos modificados fuera de la aplicación), el docente lo ve marcado y el estudiante
no recibe un detalle incoherente hasta que el docente lo recalcule.

Regla de seguridad: el estudiante solo ve respuestas correctas y justificaciones con la
sesión FINALIZADA (lo garantiza su token de resultados) y la evaluación resuelta.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.models import Usuario
from app.modules.evaluations import schemas as s
from app.modules.evaluations.dominio import EvaluacionNoPosibleError, ResultadoEvaluacion, SituacionAcademica, redondear
from app.modules.evaluations.repositories import EvaluacionRepository
from app.modules.evaluations.services.acceso_resultados_service import AccesoResultados
from app.modules.evaluations.services.evaluacion_service import EvaluacionCalculada, EvaluacionService
from app.modules.evaluations.services.retroalimentacion_service import RetroalimentacionService, RetroPregunta
from app.modules.evaluations.strategies import SelectorEstrategia
from app.modules.participations.models import EstadoParticipacionEnum, Participacion
from app.modules.participations.services import ConsultaEvaluacionService

EVALUACION_PENDIENTE = "La evaluación de este intento aún no está registrada."


def dos_decimales(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else redondear(valor)


def resuelta(participacion: Participacion, resultado: ResultadoEvaluacion) -> bool:
    """Registrada y coherente: la nota guardada es la que produce la estrategia (o ambas son SIN_CALIFICAR)."""
    return participacion.nota_final == resultado.nota


class ConsultaResultadosService:
    def __init__(self, session: Session, evaluacion: EvaluacionService | None = None) -> None:
        self._repo = EvaluacionRepository(session)
        self._consulta = ConsultaEvaluacionService(session)
        self._evaluacion = evaluacion or EvaluacionService(session)
        self._retro = RetroalimentacionService()
        self._selector = SelectorEstrategia()

    # --- Docente -----------------------------------------------------------------------------

    def resultados_sesion(self, sesion_id: uuid.UUID, docente: Usuario) -> s.ResultadosSesionRead:
        sesion = self._evaluacion.sesion_autorizada(sesion_id, docente)
        filas: list[s.ResultadoParticipacionResumen] = []
        cuenta = {"FINALIZADA": 0, "EXPIRADA": 0, "EN_PROGRESO": 0, "evaluadas": 0}
        for participacion in self._repo.participaciones_de_sesion(sesion.id):
            cuenta[participacion.estado.value] += 1
            convocatoria = participacion.convocatoria
            condicion = calificacion = None
            al_dia = False
            if participacion.estado != EstadoParticipacionEnum.EN_PROGRESO:
                resultado = self._evaluar_o_none(participacion.id)
                condicion = self._selector.seleccionar(self._situacion_minima(participacion, sesion.id)).condicion
                if resultado is not None:
                    calificacion = resultado.calificacion
                    al_dia = resuelta(participacion, resultado)
                cuenta["evaluadas"] += al_dia
            filas.append(
                s.ResultadoParticipacionResumen(
                    participacion_id=participacion.id,
                    convocatoria_id=convocatoria.id,
                    estudiante_id=convocatoria.estudiante_id,
                    estudiante_nombre=convocatoria.estudiante.nombre_completo,
                    estudiante_correo=convocatoria.estudiante.correo,
                    numero_intento=participacion.numero_intento,
                    estado=participacion.estado,
                    motivo_cierre=participacion.motivo_cierre,
                    condicion=condicion,
                    calificacion=calificacion,
                    nota_final=dos_decimales(participacion.nota_final),
                    evaluacion_registrada=al_dia,
                    requiere_procesamiento=condicion is not None and not al_dia,
                    tiene_retroalimentacion_docente=participacion.retroalimentacion_general is not None,
                )
            )
        ausencias = self.ausencias(sesion_id, docente)
        cerradas = cuenta["FINALIZADA"] + cuenta["EXPIRADA"]
        return s.ResultadosSesionRead(
            sesion_id=sesion.id,
            estado_sesion=sesion.estado,
            escala_max=self._escala(sesion.caso.rubrica),
            resumen=s.ResumenSesionRead(
                finalizadas=cuenta["FINALIZADA"],
                expiradas=cuenta["EXPIRADA"],
                en_progreso=cuenta["EN_PROGRESO"],
                ausencias=len(ausencias),
                evaluadas=cuenta["evaluadas"],
                pendientes=cerradas - cuenta["evaluadas"],
            ),
            participaciones=filas,
            ausencias=ausencias,
        )

    def ausencias(self, sesion_id: uuid.UUID, docente: Usuario) -> list[s.AusenciaRead]:
        sesion = self._evaluacion.sesion_autorizada(sesion_id, docente)
        convocatorias = {c.id: c for c in self._consulta.ausencias(sesion.id)}
        return [
            s.AusenciaRead(
                convocatoria_id=r.convocatoria_id,
                estudiante_id=r.estudiante_id,
                estudiante_nombre=convocatorias[r.convocatoria_id].estudiante.nombre_completo,
                estudiante_correo=convocatorias[r.convocatoria_id].estudiante.correo,
                observaciones=list(r.observaciones),
            )
            for r in sorted(self._evaluacion.evaluar_ausencias(sesion), key=lambda r: str(r.estudiante_id))
        ]

    def detalle_docente(self, participacion_id: uuid.UUID, docente: Usuario) -> s.EvaluacionDetalleRead:
        participacion, _ = self._evaluacion.participacion_autorizada(participacion_id, docente)
        if participacion.estado == EstadoParticipacionEnum.EN_PROGRESO:
            raise ConflictError("La participación sigue en progreso: solo se evalúan intentos cerrados.")
        return self.detalle(participacion, self._evaluacion.evaluar(participacion.id))

    def detalle(self, participacion: Participacion, calculada: EvaluacionCalculada) -> s.EvaluacionDetalleRead:
        resultado = calculada.resultado
        return s.EvaluacionDetalleRead(
            participacion_id=participacion.id,
            convocatoria_id=participacion.convocatoria_id,
            estudiante_id=resultado.estudiante_id,
            numero_intento=participacion.numero_intento,
            estado=participacion.estado,
            motivo_cierre=participacion.motivo_cierre,
            condicion=resultado.condicion,
            estrategia=resultado.estrategia,
            calificacion=resultado.calificacion,
            escala_max=dos_decimales(resultado.escala_max),
            nota_final=dos_decimales(participacion.nota_final),
            nota_calculada=dos_decimales(resultado.nota),
            evaluacion_registrada=resuelta(participacion, resultado),
            observaciones=list(resultado.observaciones),
            totales=self._totales(resultado),
            criterios=self._criterios(resultado),
            preguntas=self._preguntas(calculada),
            retroalimentacion_automatica=self._retro.general(resultado),
            retroalimentacion_general=participacion.retroalimentacion_general,
        )

    # --- Estudiante ---------------------------------------------------------------------------------

    def resultados_estudiante(self, acceso: AccesoResultados) -> s.ResultadosEstudianteRead:
        filas = []
        for participacion in self._repo.de_convocatoria(acceso.convocatoria.id):
            if participacion.estado == EstadoParticipacionEnum.EN_PROGRESO:  # imposible con la sesión FINALIZADA
                continue
            resultado = self._evaluar_o_none(participacion.id)
            disponible = resultado is not None and resuelta(participacion, resultado)
            filas.append(
                s.ResultadoEstudianteResumen(
                    participacion_id=participacion.id,
                    numero_intento=participacion.numero_intento,
                    estado=participacion.estado,
                    motivo_cierre=participacion.motivo_cierre,
                    condicion=self._selector.seleccionar(self._situacion_minima(participacion, acceso.sesion.id)).condicion,
                    calificacion=resultado.calificacion if disponible else None,  # type: ignore[union-attr]
                    nota_final=dos_decimales(participacion.nota_final) if disponible else None,
                    escala_max=self._escala(acceso.sesion.caso.rubrica),
                    disponible=disponible,
                )
            )
        return s.ResultadosEstudianteRead(
            sesion_id=acceso.sesion.id,
            caso_nombre=acceso.sesion.caso.nombre,
            convocatoria_id=acceso.convocatoria.id,
            resultados=filas,
        )

    def detalle_estudiante(self, acceso: AccesoResultados, participacion_id: uuid.UUID) -> s.ResultadoEstudianteDetalle:
        participacion = next((p for p in self._repo.de_convocatoria(acceso.convocatoria.id) if p.id == participacion_id), None)
        if participacion is None:  # inexistente o de otro estudiante: indistinguibles
            raise NotFoundError("Resultado no encontrado.")
        calculada = self._calcular_o_none(participacion.id)
        if calculada is None or not resuelta(participacion, calculada.resultado):
            raise ConflictError(EVALUACION_PENDIENTE)
        detalle = self.detalle(participacion, calculada)
        return s.ResultadoEstudianteDetalle(
            **detalle.model_dump(
                include={
                    "participacion_id", "numero_intento", "estado", "motivo_cierre", "condicion", "calificacion",
                    "escala_max", "nota_final", "observaciones", "retroalimentacion_automatica", "retroalimentacion_general",
                }
            ),
            totales=detalle.totales,
            criterios=detalle.criterios,
            preguntas=detalle.preguntas,
        )

    # --- Internos --------------------------------------------------------------------------------------

    def _evaluar_o_none(self, participacion_id: uuid.UUID) -> ResultadoEvaluacion | None:
        calculada = self._calcular_o_none(participacion_id)
        return calculada.resultado if calculada else None

    def _calcular_o_none(self, participacion_id: uuid.UUID) -> EvaluacionCalculada | None:
        """La consulta no falla por una rúbrica no evaluable: la muestra como pendiente."""
        try:
            return self._evaluacion.evaluar(participacion_id)
        except EvaluacionNoPosibleError:
            return None

    @staticmethod
    def _situacion_minima(participacion: Participacion, sesion_id: uuid.UUID) -> SituacionAcademica:
        """Basta para SELECCIONAR la estrategia (depende del estado), sin calcular nada."""
        return SituacionAcademica(
            estudiante_id=participacion.convocatoria.estudiante_id,
            convocatoria_id=participacion.convocatoria_id,
            sesion_id=sesion_id,
            rubrica=None,
            preguntas=(),
            participacion_id=participacion.id,
            estado=participacion.estado,
            motivo_cierre=participacion.motivo_cierre,
        )

    @staticmethod
    def _escala(rubrica) -> Decimal | None:
        return dos_decimales(rubrica.escala_max) if rubrica is not None else None

    @staticmethod
    def _totales(resultado: ResultadoEvaluacion) -> s.TotalesRead | None:
        d = resultado.desglose
        if d is None:
            return None
        return s.TotalesRead(total_preguntas=len(d.correcciones), aciertos=d.aciertos, errores=d.errores, sin_responder=d.sin_responder)

    @staticmethod
    def _criterios(resultado: ResultadoEvaluacion) -> list[s.ResultadoCriterioRead]:
        if resultado.desglose is None:
            return []
        return [
            s.ResultadoCriterioRead(
                criterio_id=c.criterio_id,
                descripcion=c.descripcion,
                peso=dos_decimales(c.peso),
                peso_efectivo=dos_decimales(c.peso_efectivo),
                politica=c.politica,
                total_preguntas=c.total_preguntas,
                aciertos=c.aciertos,
                errores=c.errores,
                sin_responder=c.sin_responder,
                porcentaje_aciertos=dos_decimales(c.porcentaje_aciertos),
                nivel=c.nivel,
                puntaje=dos_decimales(c.puntaje),
                aporte=dos_decimales(c.aporte),
                advertencia=c.advertencia,
            )
            for c in resultado.desglose.criterios
        ]

    def _preguntas(self, calculada: EvaluacionCalculada) -> list[s.RetroPreguntaRead]:
        situacion = calculada.situacion
        return [_pregunta(r) for r in self._retro.por_pregunta(calculada.resultado, situacion.preguntas, situacion.rubrica)]


def _pregunta(r: RetroPregunta) -> s.RetroPreguntaRead:
    def opcion(o):
        return s.OpcionRetroRead(id=o.id, texto=o.texto, justificacion=o.justificacion)

    return s.RetroPreguntaRead(
        pregunta_id=r.pregunta_id,
        escenario=r.escenario,
        enunciado=r.enunciado,
        criterio_id=r.criterio_id,
        criterio=r.criterio,
        resultado=r.resultado,
        opcion_elegida=opcion(r.opcion_elegida) if r.opcion_elegida else None,
        opciones_correctas=[opcion(o) for o in r.opciones_correctas],
        mensaje=r.mensaje,
    )


__all__ = ["ConsultaResultadosService"]
