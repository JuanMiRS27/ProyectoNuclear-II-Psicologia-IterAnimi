"""Exportaciones CSV: mismas autorizaciones, filtros y cálculos que la consulta REST.

Cada exportación se resuelve con UNA sola llamada a un reporte (una instantánea) y se arma
en memoria con un máximo de filas. Las columnas se declaran explícitamente: nunca incluyen
códigos de convocatoria, contraseñas, tokens ni claves.
"""

import uuid
from dataclasses import dataclass

from app.modules.reports import calculations as calc
from app.modules.reports import exporters
from app.modules.reports import schemas as s
from app.modules.reports.repositories import FiltroEstudiantes, FiltroSesiones
from app.modules.reports.services.base import ServicioReportesBase, sesion_resumen
from app.modules.reports.services.reportes_sesion import ReportesSesionService, construir_estudiantes, intento_detalle


@dataclass(frozen=True, slots=True)
class ArchivoExportado:
    nombre: str
    contenido: bytes


def _pct(indicador: s.IndicadorRead) -> list[tuple[str, object]]:
    return [("porcentaje", indicador.porcentaje), ("numerador", indicador.numerador), ("denominador", indicador.denominador)]


class ExportacionService(ServicioReportesBase):
    def __init__(self, session, reloj=None, limite: int = exporters.MAX_FILAS_EXPORTACION) -> None:
        super().__init__(session, reloj)
        self._sesiones = ReportesSesionService(session, self._reloj)
        self._limite = limite

    def exportar_sesion(
        self, sesion_id: uuid.UUID, docente_id: uuid.UUID, tipo: str, filtro: FiltroEstudiantes
    ) -> ArchivoExportado:
        constructor = {
            "resumen": self._resumen,
            "estudiantes": self._estudiantes,
            "intentos": self._intentos,
            "criterios": self._criterios_csv,
            "preguntas": self._preguntas,
        }[tipo]
        contenido = constructor(sesion_id, docente_id, filtro)
        return ArchivoExportado(exporters.nombre_archivo("sesion", sesion_id, tipo, self._reloj.ahora()), contenido)

    # --- Sesión ----------------------------------------------------------------------------------

    def _resumen(self, sesion_id, docente_id, _filtro) -> bytes:
        r = self._sesiones.resumen(sesion_id, docente_id)
        ses, conv, it, ind = r.sesion, r.convocatorias, r.intentos, r.indicadores
        filas: list[tuple[str, object]] = [
            ("Generado en (UTC)", r.generado_en),
            ("Sesión", ses.id),
            ("Caso académico", ses.caso.nombre),
            ("Estado del caso", ses.caso.estado),
            ("Espacio académico", ses.espacio_academico.nombre),
            ("Periodo", ses.espacio_academico.periodo),
            ("Docente responsable", ses.docente.nombre_completo),
            ("Inicio (UTC)", ses.inicio),
            ("Fin (UTC)", ses.fin),
            ("Límite de ingreso (UTC)", ses.limite_ingreso),
            ("Estado de la sesión", ses.estado),
            ("Tiempo máximo individual (min)", ses.tiempo_max_min),
            ("Escala máxima de la rúbrica", ses.escala_max),
            ("Convocatorias activas", conv.activas),
            ("Convocatorias revocadas", conv.revocadas),
            ("Estudiantes vigentes con al menos un intento", conv.activas_con_intento),
            ("Estudiantes vigentes sin participaciones", conv.activas_sin_intento),
            ("Ausencias (sesión finalizada)", conv.ausentes),
            ("Pendientes (sesión no finalizada)", conv.pendientes),
            ("Revocadas con intentos", conv.revocadas_con_intento),
            ("Intentos registrados", it.total),
            ("Intentos en progreso", it.en_progreso),
            ("Intentos finalizados", it.finalizados),
            ("Intentos expirados", it.expirados),
            ("Expirados por tiempo agotado", it.expirados_por_tiempo),
            ("Expirados por convocatoria revocada", it.expirados_por_revocacion),
            ("Expirados por fin de sesión", it.expirados_por_fin_de_sesion),
            ("Intentos calificados", it.calificados),
            ("Intentos pendientes de calificación", it.pendientes_de_calificacion),
            ("Intentos sin calificar (política del módulo 5)", it.sin_calificar),
            ("En progreso con el tiempo agotado", it.vencidos_sin_cerrar),
        ]
        for nombre, valor in (
            ("Tasa de participación", ind.tasa_participacion),
            ("Tasa de finalización", ind.tasa_finalizacion),
            ("Tasa de expiración", ind.tasa_expiracion),
            ("Tasa de calificación", ind.tasa_calificacion),
        ):
            filas += [(f"{nombre} ({parte})", v) for parte, v in _pct(valor)]
        return exporters.construir_csv(["Indicador", "Valor"], filas, self._limite)

    def _estudiantes(self, sesion_id, docente_id, filtro: FiltroEstudiantes) -> bytes:
        with self._lectura():
            sesion = self._sesion(sesion_id, docente_id)
            filas = self._repo.estudiantes_para_exportar(sesion.id, sesion.estado, filtro, self._limite + 1)
            if len(filas) > self._limite:
                raise exporters.ExportacionExcedeLimiteError(self._limite)
            estudiantes = construir_estudiantes(self._repo, sesion, filas)
        encabezados = [
            "ID del estudiante", "Nombre", "Correo institucional", "Código institucional", "Convocatoria activa",
            "Revocada en (UTC)", "Intentos autorizados", "Intentos utilizados", "Intento activo", "Intentos calificados",
            "Condición", "Notas por intento",
        ]
        return exporters.construir_csv(
            encabezados,
            (
                [
                    e.estudiante_id, e.nombre_completo, e.correo, e.codigo_institucional, e.convocatoria_activa, e.revocada_en,
                    e.intentos_autorizados, e.intentos_utilizados, e.intento_activo, e.intentos_calificados, e.condicion,
                    "; ".join(
                        f"{i.numero_intento}: {exporters.celda(i.nota_final) or 'sin nota'} ({i.situacion.value})" for i in e.intentos
                    ),
                ]
                for e in estudiantes
            ),
            self._limite,
        )

    def _intentos(self, sesion_id, docente_id, filtro: FiltroEstudiantes) -> bytes:
        with self._lectura():
            sesion = self._sesion(sesion_id, docente_id)
            convocatorias = self._repo.ids_convocatorias(sesion.id, sesion.estado, filtro)
            filas = self._repo.intentos_detallados(sesion.id, convocatorias=convocatorias, limite=self._limite + 1)
            if len(filas) > self._limite:
                raise exporters.ExportacionExcedeLimiteError(self._limite)
            total = self._repo.total_preguntas(sesion.caso_id)
        encabezados = [
            "ID del estudiante", "Nombre", "Correo institucional", "Código institucional", "Número de intento", "Estado",
            "Motivo de cierre", "Condición académica", "Inicio (UTC)", "Fin (UTC)", "Duración (s)", "Preguntas totales",
            "Preguntas respondidas", "Preguntas sin responder", "Aciertos", "Errores", "Nota final", "Escala máxima", "Situación",
        ]

        def fila(f):
            d = intento_detalle(f, sesion.id, total, sesion.escala_max)
            return [
                f.estudiante_id, f.nombre_completo, f.correo, f.codigo_institucional, d.numero_intento, d.estado, d.motivo_cierre,
                d.condicion, d.inicio, d.fin, d.duracion_segundos, d.preguntas_totales, d.preguntas_respondidas,
                d.preguntas_sin_responder, d.aciertos, d.errores, d.nota_final, d.escala_max, d.situacion,
            ]

        return exporters.construir_csv(encabezados, (fila(f) for f in filas), self._limite)

    def _criterios_csv(self, sesion_id, docente_id, _filtro) -> bytes:
        r = self._sesiones.criterios(sesion_id, docente_id)
        encabezados = [
            "ID del criterio", "Descripción", "Peso", "Evaluable", "Total de preguntas", "Intentos considerados", "Aciertos",
            "Errores", "Sin responder", "Porcentaje de aciertos", "Intentos calificados", "Puntaje promedio", "Advertencia",
        ]
        return exporters.construir_csv(
            encabezados,
            (
                [
                    c.criterio_id, c.descripcion, c.peso, c.evaluable, c.total_preguntas, c.intentos_considerados, c.aciertos,
                    c.errores, c.sin_responder, c.porcentaje_aciertos, c.intentos_calificados, c.puntaje_promedio, c.advertencia,
                ]
                for c in r.criterios
            ),
            self._limite,
        )

    def _preguntas(self, sesion_id, docente_id, _filtro) -> bytes:
        r = self._sesiones.preguntas(sesion_id, docente_id)
        encabezados = [
            "ID de la pregunta", "Escenario", "Orden del escenario", "Orden", "Enunciado", "Criterio", "Intentos considerados",
            "Aciertos", "Errores", "Sin responder", "Porcentaje de aciertos", "Corregible",
        ]
        return exporters.construir_csv(
            encabezados,
            (
                [
                    p.pregunta_id, p.escenario, p.orden_escenario, p.orden, p.enunciado, p.criterio, p.intentos_considerados,
                    p.aciertos, p.errores, p.sin_responder, p.porcentaje_aciertos, p.corregible,
                ]
                for p in r.preguntas
            ),
            self._limite,
        )

    # --- Espacio académico -------------------------------------------------------------------------

    def exportar_espacio(self, espacio_id: uuid.UUID, filtro: FiltroSesiones) -> ArchivoExportado:
        with self._lectura():
            self._espacio_visible(espacio_id, filtro.docente_id)
            filas = self._repo.pagina_sesiones(filtro, skip=0, limit=self._limite + 1)
            if len(filas) > self._limite:
                raise exporters.ExportacionExcedeLimiteError(self._limite)
            ahora = self._reloj.ahora()
            convocatorias = self._repo.conteos_convocatorias(filtro.ids())
            intentos = self._repo.conteos_intentos(filtro.ids(), ahora)
        encabezados = [
            "ID de la sesión", "Caso académico", "Estado del caso", "Espacio académico", "Periodo", "Inicio (UTC)", "Fin (UTC)",
            "Estado de la sesión", "Convocatorias activas", "Convocatorias revocadas", "Estudiantes con intento", "Intentos",
            "En progreso", "Finalizados", "Expirados", "Calificados", "Tasa de participación (%)",
        ]

        def fila(f):
            r = sesion_resumen(f, convocatorias.get(f.id, calc.ConteosConvocatorias()), intentos.get(f.id, calc.ConteosIntentos()))
            return [
                r.id, r.caso.nombre, r.caso.estado, r.espacio_academico.nombre, r.espacio_academico.periodo, r.inicio, r.fin,
                r.estado, r.convocatorias_activas, r.convocatorias_revocadas, r.estudiantes_con_intento, r.intentos,
                r.en_progreso, r.finalizados, r.expirados, r.calificados, r.tasa_participacion.porcentaje,
            ]

        contenido = exporters.construir_csv(encabezados, (fila(f) for f in filas), self._limite)
        return ArchivoExportado(exporters.nombre_archivo("espacio", espacio_id, "sesiones", ahora), contenido)
