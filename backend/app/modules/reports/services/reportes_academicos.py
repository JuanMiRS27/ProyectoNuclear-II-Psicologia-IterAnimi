"""Seguimiento por espacio académico, historial por caso y listado de sesiones del docente.

Alcance: SIEMPRE las sesiones del docente autenticado. Un espacio académico es un catálogo
compartido (módulo 3): si contiene sesiones de otros docentes, no se revelan ni se agregan.
Un caso solo lo consulta su autor (módulo 2), en cualquier estado (también ARCHIVADO), y
aun así solo se agregan las sesiones del docente.
"""

import uuid

from app.core.exceptions import NotFoundError
from app.modules.reports import calculations as calc
from app.modules.reports import schemas as s
from app.modules.reports.repositories import FiltroSesiones
from app.modules.reports.services.base import ServicioReportesBase, dos, estadisticas, por_estado, totales

CASO_NO_ENCONTRADO = "Caso no encontrado."


class ReportesAcademicosService(ServicioReportesBase):
    def mis_sesiones(self, filtro: FiltroSesiones, *, skip: int, limit: int) -> s.SesionesReporteList:
        with self._lectura():
            return self._listado(filtro, skip=skip, limit=limit)

    # --- Espacio académico -------------------------------------------------------------------------

    def espacio(self, espacio_id: uuid.UUID, filtro: FiltroSesiones, *, skip: int, limit: int) -> s.EspacioReporteRead:
        with self._lectura():
            espacio = self._espacio_visible(espacio_id, filtro.docente_id)
            ahora = self._reloj.ahora()
            ids = filtro.ids()
            casos = self._repo.casos_utilizados(ids)
            return s.EspacioReporteRead(
                generado_en=ahora,
                espacio_academico=s.EspacioRef(id=espacio.id, nombre=espacio.nombre, periodo=espacio.periodo),
                activo=espacio.activo,
                sesiones_registradas=self._repo.contar_sesiones(filtro),
                sesiones_por_estado=por_estado(self._repo.sesiones_por_estado(filtro)),
                totales=totales(self._repo.conteos_intentos(ids, ahora, agrupar=False)[None]),
                promedio_porcentaje_escala=dos(self._repo.promedio_normalizado(ids)),
                casos_utilizados=[
                    s.CasoUtilizadoRead(
                        id=c.id,
                        nombre=c.nombre,
                        estado=c.estado,
                        escala_max=dos(c.escala_max),
                        sesiones=c.sesiones,
                        evaluaciones_registradas=c.evaluaciones,
                        promedio=dos(c.promedio),
                    )
                    for c in casos
                ],
                sesiones=self._listado(filtro, skip=skip, limit=limit),
            )

    # --- Caso académico ---------------------------------------------------------------------------------

    def caso(self, caso_id: uuid.UUID, filtro: FiltroSesiones, *, skip: int, limit: int) -> s.CasoReporteRead:
        with self._lectura():
            caso = self._repo.caso_del_autor(caso_id, filtro.docente_id)
            if caso is None:
                raise NotFoundError(CASO_NO_ENCONTRADO)
            ahora = self._reloj.ahora()
            ids = filtro.ids()
            agregado = self._repo.agregado_notas(ids, caso.escala_max).get(None, calc.AgregadoNotas())
            criterios = self._criterios(caso.id, ids)
            return s.CasoReporteRead(
                generado_en=ahora,
                caso=s.CasoRef(id=caso.id, nombre=caso.nombre, estado=caso.estado),
                escala_max=dos(caso.escala_max),
                sesiones_registradas=self._repo.contar_sesiones(filtro),
                sesiones_por_estado=por_estado(self._repo.sesiones_por_estado(filtro)),
                totales=totales(self._repo.conteos_intentos(ids, ahora, agrupar=False)[None]),
                # Un mismo caso tiene una sola rúbrica (no editable tras publicarse): sus notas son comparables.
                estadisticas=estadisticas(calc.estadisticas_agregadas(agregado, caso.escala_max)),
                criterios=criterios,
                sesiones=self._listado(filtro, skip=skip, limit=limit),
            )
