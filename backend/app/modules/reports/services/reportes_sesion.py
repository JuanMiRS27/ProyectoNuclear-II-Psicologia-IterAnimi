"""Seguimiento operativo y académico de UNA sesión del docente responsable."""

import uuid
from collections import defaultdict
from dataclasses import dataclass

from app.core.exceptions import NotFoundError
from app.modules.evaluations.dominio import CondicionAcademica, SituacionAcademica
from app.modules.evaluations.strategies import SelectorEstrategia
from app.modules.participations.models import EstadoParticipacionEnum
from app.modules.reports import calculations as calc
from app.modules.reports import schemas as s
from app.modules.reports.repositories import FiltroEstudiantes
from app.modules.reports.services.base import ServicioReportesBase, dos, estadisticas, indicador
from app.modules.sessions.models import EstadoSesionEnum

ESTUDIANTE_NO_ENCONTRADO = "El estudiante no está convocado a esta sesión."
_SELECTOR = SelectorEstrategia()


def condicion_academica(fila, sesion_id: uuid.UUID) -> CondicionAcademica | None:
    """COMPLETA o INCOMPLETA según la selección de estrategia del módulo 5 (sin calcular la nota)."""
    if fila.estado == EstadoParticipacionEnum.EN_PROGRESO:
        return None
    situacion = SituacionAcademica(
        estudiante_id=fila.estudiante_id,
        convocatoria_id=fila.convocatoria_id,
        sesion_id=sesion_id,
        rubrica=None,
        preguntas=(),
        participacion_id=fila.id,
        estado=fila.estado,
        motivo_cierre=fila.motivo_cierre,
    )
    return _SELECTOR.seleccionar(situacion).condicion


def info_sesion(fila) -> s.SesionInfoRead:
    return s.SesionInfoRead(
        id=fila.id,
        caso=s.CasoRef(id=fila.caso_id, nombre=fila.caso_nombre, estado=fila.caso_estado),
        espacio_academico=s.EspacioRef(id=fila.espacio_id, nombre=fila.espacio_nombre, periodo=fila.espacio_periodo),
        docente=s.DocenteRef(id=fila.docente_id, nombre_completo=fila.docente_nombre),
        inicio=fila.inicio,
        fin=fila.fin,
        limite_ingreso=fila.inicio + (fila.fin - fila.inicio) / 2,
        estado=fila.estado,
        tiempo_max_min=fila.tiempo_max_min,
        escala_max=dos(fila.escala_max),
    )


def intento_detalle(fila, sesion_id: uuid.UUID, preguntas_totales: int, escala_max) -> s.IntentoDetalleRead:
    en_progreso = fila.estado == EstadoParticipacionEnum.EN_PROGRESO
    return s.IntentoDetalleRead(
        participacion_id=fila.id,
        numero_intento=fila.numero_intento,
        inicio=fila.inicio,
        fin=fila.fin,
        duracion_segundos=calc.duracion_segundos(fila.inicio, fila.fin),
        estado=fila.estado,
        motivo_cierre=fila.motivo_cierre,
        condicion=condicion_academica(fila, sesion_id),
        preguntas_totales=preguntas_totales,
        preguntas_respondidas=fila.respondidas,
        preguntas_sin_responder=preguntas_totales - fila.respondidas,
        # Mientras el intento sigue abierto no se exponen resultados (el módulo 5 tampoco lo evalúa).
        aciertos=None if en_progreso else fila.aciertos,
        errores=None if en_progreso else fila.respondidas - fila.aciertos,
        nota_final=dos(fila.nota_final),
        escala_max=dos(escala_max),
        situacion=calc.situacion_intento(fila.estado, fila.motivo_cierre, fila.nota_final, fila.respondidas),
    )


def construir_estudiantes(repo, sesion, filas) -> list[s.EstudianteReporteRead]:
    """Una consulta para la página y otra para TODOS sus intentos (sin N+1)."""
    intentos = defaultdict(list)
    for i in repo.intentos_breves([f.convocatoria_id for f in filas]):
        intentos[i.convocatoria_id].append(
            s.IntentoBreveRead(
                participacion_id=i.id,
                numero_intento=i.numero_intento,
                estado=i.estado,
                motivo_cierre=i.motivo_cierre,
                nota_final=dos(i.nota_final),
                situacion=calc.situacion_intento(i.estado, i.motivo_cierre, i.nota_final, i.respondidas),
            )
        )
    return [
        s.EstudianteReporteRead(
            estudiante_id=f.estudiante_id,
            nombre_completo=f.nombre_completo,
            correo=f.correo,
            codigo_institucional=f.codigo_institucional,
            convocatoria_id=f.convocatoria_id,
            convocatoria_activa=f.revocada_en is None,
            revocada_en=f.revocada_en,
            intentos_autorizados=f.intentos_autorizados,
            intentos_utilizados=f.intentos,
            intento_activo=bool(f.activo),
            intentos_calificados=f.calificados,
            condicion=calc.condicion_convocado(revocada=f.revocada_en is not None, intentos=f.intentos, estado_sesion=sesion.estado),
            intentos=intentos[f.convocatoria_id],
        )
        for f in filas
    ]


@dataclass(frozen=True, slots=True)
class ConteosSesion:
    convocatorias: calc.ConteosConvocatorias
    intentos: calc.ConteosIntentos


class ReportesSesionService(ServicioReportesBase):
    # --- Resumen ---------------------------------------------------------------------------------

    def resumen(self, sesion_id: uuid.UUID, docente_id: uuid.UUID) -> s.ResumenSesionRead:
        with self._lectura():
            return self._resumen(sesion_id, docente_id)

    def _resumen(self, sesion_id: uuid.UUID, docente_id: uuid.UUID) -> s.ResumenSesionRead:
        ahora = self._reloj.ahora()
        fila = self._sesion(sesion_id, docente_id)
        conteos = self._conteos(fila.id, ahora)
        conv, intentos = conteos.convocatorias, conteos.intentos
        finalizada = fila.estado == EstadoSesionEnum.FINALIZADO
        ind = calc.indicadores(conv, intentos)
        return s.ResumenSesionRead(
            generado_en=ahora,
            sesion=info_sesion(fila),
            convocatorias=s.ConvocatoriasRead(
                activas=conv.activas,
                revocadas=conv.revocadas,
                activas_con_intento=conv.activas_con_intento,
                activas_sin_intento=conv.activas_sin_intento,
                revocadas_con_intento=conv.revocadas_con_intento,
                ausentes=conv.activas_sin_intento if finalizada else 0,
                pendientes=0 if finalizada else conv.activas_sin_intento,
            ),
            intentos=s.IntentosRead(
                total=intentos.total,
                en_progreso=intentos.en_progreso,
                finalizados=intentos.finalizados,
                expirados=intentos.expirados,
                expirados_por_tiempo=intentos.expirados_tiempo,
                expirados_por_revocacion=intentos.expirados_revocacion,
                expirados_por_fin_de_sesion=intentos.expirados_fin_sesion,
                calificados=intentos.calificados,
                pendientes_de_calificacion=intentos.pendientes,
                sin_calificar=intentos.sin_calificar,
                vencidos_sin_cerrar=intentos.vencidos_sin_cerrar,
            ),
            indicadores=s.IndicadoresRead(
                tasa_participacion=indicador(ind.tasa_participacion),
                tasa_finalizacion=indicador(ind.tasa_finalizacion),
                tasa_expiracion=indicador(ind.tasa_expiracion),
                tasa_calificacion=indicador(ind.tasa_calificacion),
            ),
        )

    def _conteos(self, sesion_id: uuid.UUID, ahora) -> ConteosSesion:
        return ConteosSesion(
            self._repo.conteos_convocatorias([sesion_id]).get(sesion_id, calc.ConteosConvocatorias()),
            self._repo.conteos_intentos([sesion_id], ahora).get(sesion_id, calc.ConteosIntentos()),
        )

    # --- Estudiantes ----------------------------------------------------------------------------------

    def estudiantes(
        self, sesion_id: uuid.UUID, docente_id: uuid.UUID, filtro: FiltroEstudiantes, *, skip: int, limit: int
    ) -> s.EstudiantesReporteList:
        with self._lectura():
            fila = self._sesion(sesion_id, docente_id)
            pagina = self._repo.pagina_estudiantes(fila.id, fila.estado, filtro, skip=skip, limit=limit)
            total = self._repo.contar_estudiantes(fila.id, fila.estado, filtro)
            items = construir_estudiantes(self._repo, fila, pagina)
        return s.EstudiantesReporteList(sesion_id=fila.id, estado_sesion=fila.estado, items=items, total=total, skip=skip, limit=limit)

    # --- Desempeño individual -------------------------------------------------------------------------

    def desempeno_estudiante(self, sesion_id: uuid.UUID, estudiante_id: uuid.UUID, docente_id: uuid.UUID) -> s.DesempenoEstudianteRead:
        with self._lectura():
            fila = self._sesion(sesion_id, docente_id)
            conv = self._repo.convocatoria_de_estudiante(fila.id, estudiante_id)
            if conv is None:  # un estudiante solo de sesiones ajenas es indistinguible de uno inexistente
                raise NotFoundError(ESTUDIANTE_NO_ENCONTRADO)
            total = self._repo.total_preguntas(fila.caso_id)
            filas = self._repo.intentos_detallados(fila.id, convocatoria_id=conv.convocatoria_id)
        return s.DesempenoEstudianteRead(
            sesion_id=fila.id,
            estado_sesion=fila.estado,
            estudiante_id=conv.estudiante_id,
            nombre_completo=conv.nombre_completo,
            correo=conv.correo,
            codigo_institucional=conv.codigo_institucional,
            convocatoria_id=conv.convocatoria_id,
            convocatoria_activa=conv.revocada_en is None,
            intentos_autorizados=conv.intentos_autorizados,
            condicion=calc.condicion_convocado(revocada=conv.revocada_en is not None, intentos=len(filas), estado_sesion=fila.estado),
            intentos=[intento_detalle(f, fila.id, total, fila.escala_max) for f in filas],
        )

    # --- Calificaciones ----------------------------------------------------------------------------------

    def notas(self, sesion_id: uuid.UUID, docente_id: uuid.UUID) -> s.NotasSesionRead:
        with self._lectura():
            fila = self._sesion(sesion_id, docente_id)
            escala = fila.escala_max
            total = self._repo.agregado_notas([fila.id], escala).get(None, calc.AgregadoNotas())
            por_estado = self._repo.agregado_notas([fila.id], escala, por_estado=True)
            intentos = self._repo.conteos_intentos([fila.id], self._reloj.ahora()).get(fila.id, calc.ConteosIntentos())
            con_nota = self._repo.estudiantes_con_nota([fila.id])

        def de(estado):
            return estadisticas(calc.estadisticas_agregadas(por_estado.get(estado, calc.AgregadoNotas()), escala))

        return s.NotasSesionRead(
            sesion_id=fila.id,
            estado_sesion=fila.estado,
            intentos_cerrados=intentos.cerrados,
            intentos_sin_nota=intentos.cerrados - intentos.calificados,
            estudiantes_con_nota=con_nota,
            estadisticas=estadisticas(calc.estadisticas_agregadas(total, escala)),
            por_estado=s.NotasPorEstadoRead(finalizados=de(EstadoParticipacionEnum.FINALIZADA), expirados=de(EstadoParticipacionEnum.EXPIRADA)),
        )

    # --- Criterios y preguntas -----------------------------------------------------------------------------

    def criterios(self, sesion_id: uuid.UUID, docente_id: uuid.UUID) -> s.CriteriosSesionRead:
        with self._lectura():
            fila = self._sesion(sesion_id, docente_id)
            reporte = self._criterios(fila.caso_id, [fila.id])
        return s.CriteriosSesionRead(sesion_id=fila.id, **reporte.model_dump())

    def preguntas(self, sesion_id: uuid.UUID, docente_id: uuid.UUID) -> s.PreguntasSesionRead:
        with self._lectura():
            fila = self._sesion(sesion_id, docente_id)
            preguntas = self._repo.preguntas_del_caso(fila.caso_id)
            considerados = self._repo.conteos_intentos([fila.id], self._reloj.ahora()).get(fila.id, calc.ConteosIntentos()).cerrados
            correccion = self._repo.correccion_por_pregunta([fila.id]) if considerados else {}
        items = []
        for p in preguntas:
            intentos, respondidas, aciertos = correccion.get(p.id, (0, 0, 0))
            e = calc.estadistica_pregunta(intentos=intentos, respondidas=respondidas, aciertos=aciertos, corregible=p.corregible)
            items.append(
                s.PreguntaReporteRead(
                    pregunta_id=p.id,
                    enunciado=p.enunciado,
                    escenario=p.escenario,
                    orden_escenario=p.orden_escenario,
                    orden=p.orden,
                    criterio_id=p.criterio_id,
                    criterio=p.criterio,
                    intentos_considerados=e.intentos_considerados,
                    aciertos=e.aciertos,
                    errores=e.errores,
                    sin_responder=e.sin_responder,
                    porcentaje_aciertos=e.porcentaje_aciertos,
                    corregible=e.corregible,
                )
            )
        return s.PreguntasSesionRead(sesion_id=fila.id, intentos_considerados=considerados, preguntas=items)
