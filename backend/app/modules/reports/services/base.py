"""Comportamiento común de los servicios de reportes.

- Autorización: los datos de una sesión solo los ve su docente RESPONSABLE (`Sesion.docente_id`).
  Ser autor del caso NO autoriza a ver sesiones de otros docentes que lo usen: el historial del
  caso exige la autoría (módulo 2) y, además, solo agrega las sesiones del propio docente. Una
  sesión, caso o espacio sin acceso responde 404, igual que en los módulos 2, 3 y 5.
- Coherencia: cada reporte se calcula dentro de `_lectura()`, una transacción READ ONLY con
  aislamiento REPEATABLE READ. Todas sus consultas ven la misma instantánea de PostgreSQL:
  un intento que finaliza, una nota que se registra o una convocatoria que se revoca durante
  el cálculo aparecen en el reporte completo o no aparecen, nunca a medias.
- No modifica nada: READ ONLY hace fallar cualquier escritura y la transacción se revierte.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import Reloj, RelojSistema
from app.core.exceptions import NotFoundError
from app.modules.evaluations.dominio import redondear
from app.modules.evaluations.services import mapeo
from app.modules.reports import calculations as calc
from app.modules.reports import schemas as s
from app.modules.reports.repositories import FiltroSesiones, ReportesRepository
from app.modules.sessions.models import EstadoSesionEnum

SESION_NO_ENCONTRADA = "Sesión no encontrada."
ESPACIO_NO_ENCONTRADO = "Espacio académico no encontrado."


def dos(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else redondear(valor)


def indicador(valor: calc.Indicador) -> s.IndicadorRead:
    return s.IndicadorRead(numerador=valor.numerador, denominador=valor.denominador, porcentaje=valor.porcentaje)


def estadisticas(e: calc.EstadisticasNotas) -> s.EstadisticasNotasRead:
    return s.EstadisticasNotasRead(
        evaluados=e.evaluados,
        escala_max=dos(e.escala_max),
        minimo=dos(e.minimo),
        maximo=dos(e.maximo),
        promedio=e.promedio,
        mediana=e.mediana,
        promedio_porcentaje_escala=e.promedio_porcentaje_escala,
        distribucion=[
            s.TramoRead(desde=t.desde, hasta=t.hasta, incluye_hasta=t.incluye_hasta, cantidad=t.cantidad, porcentaje=t.porcentaje_de(e.evaluados))
            for t in e.distribucion
        ],
    )


def sesion_resumen(fila, conv: calc.ConteosConvocatorias, intentos: calc.ConteosIntentos) -> s.SesionResumenRead:
    return s.SesionResumenRead(
        id=fila.id,
        caso=s.CasoRef(id=fila.caso_id, nombre=fila.caso_nombre, estado=fila.caso_estado),
        espacio_academico=s.EspacioRef(id=fila.espacio_id, nombre=fila.espacio_nombre, periodo=fila.espacio_periodo),
        inicio=fila.inicio,
        fin=fila.fin,
        estado=fila.estado,
        convocatorias_activas=conv.activas,
        convocatorias_revocadas=conv.revocadas,
        estudiantes_con_intento=conv.activas_con_intento,
        intentos=intentos.total,
        en_progreso=intentos.en_progreso,
        finalizados=intentos.finalizados,
        expirados=intentos.expirados,
        calificados=intentos.calificados,
        tasa_participacion=indicador(calc.Indicador(conv.activas_con_intento, conv.activas)),
    )


def por_estado(conteos: dict[EstadoSesionEnum, int]) -> s.SesionesPorEstadoRead:
    return s.SesionesPorEstadoRead(
        sin_iniciar=conteos.get(EstadoSesionEnum.SIN_INICIAR, 0),
        en_curso=conteos.get(EstadoSesionEnum.EN_CURSO, 0),
        finalizadas=conteos.get(EstadoSesionEnum.FINALIZADO, 0),
    )


def totales(intentos: calc.ConteosIntentos) -> s.TotalesAcademicosRead:
    return s.TotalesAcademicosRead(
        intentos=intentos.total,
        en_progreso=intentos.en_progreso,
        finalizados=intentos.finalizados,
        expirados=intentos.expirados,
        evaluaciones_registradas=intentos.calificados,
    )


class ServicioReportesBase:
    def __init__(self, session: Session, reloj: Reloj | None = None) -> None:
        self._session = session
        self._reloj = reloj or RelojSistema()
        self._repo = ReportesRepository(session)

    @contextmanager
    def _lectura(self) -> Iterator[None]:
        self._repo.iniciar_lectura()
        try:
            yield
        finally:
            self._repo.terminar_lectura()

    def _sesion(self, sesion_id: uuid.UUID, docente_id: uuid.UUID):
        fila = self._repo.sesion(sesion_id, docente_id)
        if fila is None:
            raise NotFoundError(SESION_NO_ENCONTRADA)
        return fila

    def _espacio_visible(self, espacio_id: uuid.UUID, docente_id: uuid.UUID):
        """Visible si está activo (como en el módulo 3) o si el docente tiene sesiones en él (historial)."""
        espacio = self._repo.espacio(espacio_id)
        if espacio is None or not (espacio.activo or self._repo.docente_tiene_sesiones_en_espacio(espacio_id, docente_id)):
            raise NotFoundError(ESPACIO_NO_ENCONTRADO)
        return espacio

    def _listado(self, filtro: FiltroSesiones, *, skip: int, limit: int) -> s.SesionesReporteList:
        """Página de sesiones y sus métricas en tres consultas, sin importar el tamaño de la página."""
        filas = self._repo.pagina_sesiones(filtro, skip=skip, limit=limit)
        ids = [f.id for f in filas]
        convocatorias = self._repo.conteos_convocatorias(ids)
        intentos = self._repo.conteos_intentos(ids, self._reloj.ahora())
        return s.SesionesReporteList(
            items=[
                sesion_resumen(f, convocatorias.get(f.id, calc.ConteosConvocatorias()), intentos.get(f.id, calc.ConteosIntentos()))
                for f in filas
            ],
            total=self._repo.contar_sesiones(filtro),
            skip=skip,
            limit=limit,
        )

    def _criterios(self, caso_id: uuid.UUID, sesiones) -> s.CriteriosReporteRead:
        rubrica = self._repo.rubrica(caso_id)
        preguntas = self._repo.preguntas_del_caso(caso_id)
        considerados = self._repo.conteos_intentos(sesiones, self._reloj.ahora(), agrupar=False).get(None, calc.ConteosIntentos()).cerrados
        criterios = [mapeo.criterio(c) for c in rubrica.criterios] if rubrica is not None else []
        por_criterio: dict = defaultdict(int)
        for p in preguntas:
            por_criterio[p.criterio_id] += 1
        filas = self._repo.correccion_por_criterio(sesiones) if considerados else []
        resultados = calc.estadisticas_criterios(criterios, rubrica.escala_max if rubrica else None, por_criterio, filas, considerados)
        return s.CriteriosReporteRead(
            escala_max=dos(rubrica.escala_max) if rubrica else None,
            intentos_considerados=considerados,
            preguntas_sin_criterio=por_criterio.get(None, 0),
            criterios=[
                s.CriterioReporteRead(
                    criterio_id=r.criterio_id,
                    descripcion=r.descripcion,
                    peso=dos(r.peso),
                    evaluable=r.evaluable,
                    total_preguntas=r.total_preguntas,
                    intentos_considerados=r.intentos_considerados,
                    aciertos=r.aciertos,
                    errores=r.errores,
                    sin_responder=r.sin_responder,
                    porcentaje_aciertos=r.porcentaje_aciertos,
                    intentos_calificados=r.intentos_calificados,
                    puntaje_promedio=r.puntaje_promedio,
                    advertencia=r.advertencia,
                )
                for r in resultados
            ],
        )
