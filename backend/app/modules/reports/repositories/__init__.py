"""Consultas del módulo 7: proyecciones y agregaciones SQL de solo lectura.

Reglas:

- Toda consulta parte de las sesiones del docente (`Sesion.docente_id`); ningún filtro del
  cliente puede ampliar ese alcance.
- Se agrega en PostgreSQL (`count(*) FILTER`, `GROUP BY`) y se proyectan solo las columnas
  necesarias: nunca se cargan entidades completas de convocatoria (su código cifrado no sale
  de la base) ni todas las respuestas históricas.
- Los listados están paginados; las exportaciones piden `limite + 1` filas para detectar que
  superan el máximo sin leer el resto.
- Solo SELECT: el servicio abre una transacción READ ONLY (ver `services/base.py`).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, exists, false, func, or_, select, text, true
from sqlalchemy.orm import Session, selectinload

from app.modules.auth.models import Usuario
from app.modules.cases.models import CasoEstudio, CriterioRubrica, Escenario, Opcion, Pregunta, Rubrica
from app.modules.evaluations.strategies.incompleta import CIERRES_ADMINISTRATIVOS
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum, Participacion, Respuesta
from app.modules.reports.calculations import (
    TRAMOS_DISTRIBUCION,
    AgregadoNotas,
    CondicionConvocado,
    ConteosConvocatorias,
    ConteosIntentos,
    FilaCriterioIntento,
)
from app.modules.sessions.models import Convocatoria, EspacioAcademico, EstadoSesionEnum, Sesion

EN_PROGRESO = EstadoParticipacionEnum.EN_PROGRESO
FINALIZADA = EstadoParticipacionEnum.FINALIZADA
EXPIRADA = EstadoParticipacionEnum.EXPIRADA


@dataclass(frozen=True, slots=True)
class FiltroSesiones:
    docente_id: uuid.UUID
    estado: EstadoSesionEnum | None = None
    espacio_academico_id: uuid.UUID | None = None
    caso_id: uuid.UUID | None = None
    desde: datetime | None = None
    hasta: datetime | None = None

    def condiciones(self) -> list[ColumnElement[bool]]:
        condiciones = [Sesion.docente_id == self.docente_id]  # siempre: el alcance del docente
        if self.estado is not None:
            condiciones.append(Sesion.estado == self.estado)
        if self.espacio_academico_id is not None:
            condiciones.append(Sesion.espacio_academico_id == self.espacio_academico_id)
        if self.caso_id is not None:
            condiciones.append(Sesion.caso_id == self.caso_id)
        if self.desde is not None:
            condiciones.append(Sesion.inicio >= self.desde)
        if self.hasta is not None:
            condiciones.append(Sesion.inicio < self.hasta)
        return condiciones

    def ids(self) -> Select[tuple[uuid.UUID]]:
        return select(Sesion.id).where(*self.condiciones())


@dataclass(frozen=True, slots=True)
class FiltroEstudiantes:
    convocatoria: str = "todas"
    condicion: CondicionConvocado | None = None
    estado_participacion: EstadoParticipacionEnum | None = None
    con_nota: bool | None = None
    intento_activo: bool | None = None
    buscar: str | None = None


def _patron(texto: str) -> str:
    """Coincidencia parcial literal: `%`, `_` y `\\` del usuario no actúan como comodines."""
    escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


def _sesion_ref_columnas() -> tuple:
    return (
        Sesion.id,
        Sesion.estado,
        Sesion.inicio,
        Sesion.fin,
        Sesion.tiempo_max_min,
        CasoEstudio.id.label("caso_id"),
        CasoEstudio.nombre.label("caso_nombre"),
        CasoEstudio.estado.label("caso_estado"),
        EspacioAcademico.id.label("espacio_id"),
        EspacioAcademico.nombre.label("espacio_nombre"),
        EspacioAcademico.periodo.label("espacio_periodo"),
    )


def _con_referencias(stmt: Select) -> Select:
    return stmt.join(CasoEstudio, CasoEstudio.id == Sesion.caso_id).join(
        EspacioAcademico, EspacioAcademico.id == Sesion.espacio_academico_id
    )


class ReportesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Transacción de lectura -------------------------------------------------------------

    def iniciar_lectura(self) -> None:
        """Transacción READ ONLY y REPEATABLE READ: una sola instantánea para todo el reporte.

        Se confirma antes la transacción implícita de la autenticación (solo leyó el usuario),
        porque el nivel de aislamiento solo puede fijarse en la primera sentencia. Con MVCC
        de PostgreSQL esta lectura no bloquea ni es bloqueada por las operaciones académicas,
        y READ ONLY hace que cualquier escritura accidental falle.
        """
        self._session.commit()
        self._session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))

    def terminar_lectura(self) -> None:
        self._session.rollback()

    # --- Sesiones -------------------------------------------------------------------------------

    def sesion(self, sesion_id: uuid.UUID, docente_id: uuid.UUID) -> Any | None:
        """Sesión del docente con su caso, espacio, docente y escala; una ajena es indistinguible de una inexistente."""
        stmt = (
            _con_referencias(
                select(*_sesion_ref_columnas(), Usuario.id.label("docente_id"), Usuario.nombre_completo.label("docente_nombre"), Rubrica.escala_max)
            )
            .join(Usuario, Usuario.id == Sesion.docente_id)
            .outerjoin(Rubrica, Rubrica.caso_id == Sesion.caso_id)
            .where(Sesion.id == sesion_id, Sesion.docente_id == docente_id)
        )
        return self._session.execute(stmt).first()

    def contar_sesiones(self, filtro: FiltroSesiones) -> int:
        return self._session.scalar(select(func.count()).select_from(Sesion).where(*filtro.condiciones())) or 0

    def pagina_sesiones(self, filtro: FiltroSesiones, *, skip: int, limit: int) -> list[Any]:
        stmt = (
            _con_referencias(select(*_sesion_ref_columnas()))
            .where(*filtro.condiciones())
            .order_by(Sesion.inicio.desc(), Sesion.id)
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.execute(stmt))

    def sesiones_por_estado(self, filtro: FiltroSesiones) -> dict[EstadoSesionEnum, int]:
        stmt = select(Sesion.estado, func.count()).where(*filtro.condiciones()).group_by(Sesion.estado)
        return {estado: total for estado, total in self._session.execute(stmt)}

    # --- Conteos agregados ------------------------------------------------------------------------

    def conteos_convocatorias(self, sesiones: Select | Sequence[uuid.UUID]) -> dict[uuid.UUID, ConteosConvocatorias]:
        if isinstance(sesiones, Sequence) and not sesiones:
            return {}
        con_intento = exists().where(Participacion.convocatoria_id == Convocatoria.id)
        activa = Convocatoria.revocada_en.is_(None)
        stmt = (
            select(
                Convocatoria.sesion_id,
                func.count().filter(activa),
                func.count().filter(Convocatoria.revocada_en.is_not(None)),
                func.count().filter(and_(activa, con_intento)),
                func.count().filter(and_(Convocatoria.revocada_en.is_not(None), con_intento)),
            )
            .where(Convocatoria.sesion_id.in_(sesiones))
            .group_by(Convocatoria.sesion_id)
        )
        return {fila[0]: ConteosConvocatorias(*fila[1:]) for fila in self._session.execute(stmt)}

    def conteos_intentos(
        self, sesiones: Select | Sequence[uuid.UUID], ahora: datetime, *, agrupar: bool = True
    ) -> dict[uuid.UUID | None, ConteosIntentos]:
        """Conteos por intento; `agrupar=False` devuelve un único total (clave `None`)."""
        if isinstance(sesiones, Sequence) and not sesiones:
            return {}
        estado, nota, motivo = Participacion.estado, Participacion.nota_final, Participacion.motivo_cierre
        cerrada_sin_nota = and_(estado != EN_PROGRESO, nota.is_(None))
        # Misma regla que `EstrategiaEvaluacionIncompleta.permite_calificar` (y `calculations.calificable`).
        sin_calificar_por_politica = and_(
            estado == EXPIRADA,
            motivo.in_(CIERRES_ADMINISTRATIVOS),
            ~exists().where(Respuesta.participacion_id == Participacion.id),
        )
        vencida = and_(
            estado == EN_PROGRESO,
            Participacion.inicio + func.make_interval(0, 0, 0, 0, 0, Sesion.tiempo_max_min) <= ahora,
        )
        columnas = [
            func.count().filter(estado == EN_PROGRESO),
            func.count().filter(estado == FINALIZADA),
            func.count().filter(estado == EXPIRADA),
            func.count(nota),
            func.count().filter(and_(cerrada_sin_nota, sin_calificar_por_politica)),
            func.count().filter(and_(cerrada_sin_nota, ~sin_calificar_por_politica)),
            func.count().filter(motivo == MotivoCierreEnum.TIEMPO_AGOTADO),
            func.count().filter(motivo == MotivoCierreEnum.CONVOCATORIA_REVOCADA),
            func.count().filter(motivo == MotivoCierreEnum.SESION_FINALIZADA),
            func.count().filter(vencida),
        ]
        clave = Sesion.id if agrupar else None
        stmt = (
            select(*([clave] if agrupar else []), *columnas)
            .select_from(Participacion)
            .join(Convocatoria, Convocatoria.id == Participacion.convocatoria_id)
            .join(Sesion, Sesion.id == Convocatoria.sesion_id)
            .where(Sesion.id.in_(sesiones))
        )
        if agrupar:
            stmt = stmt.group_by(Sesion.id)
            return {fila[0]: ConteosIntentos(*fila[1:]) for fila in self._session.execute(stmt)}
        return {None: ConteosIntentos(*self._session.execute(stmt).one())}

    # --- Estudiantes de una sesión --------------------------------------------------------------

    def _estudiantes(self, sesion_id: uuid.UUID, estado_sesion: EstadoSesionEnum, filtro: FiltroEstudiantes) -> Select:
        por_convocatoria = (
            select(
                Participacion.convocatoria_id.label("convocatoria_id"),
                func.count().label("intentos"),
                func.count(Participacion.nota_final).label("calificados"),
                func.bool_or(Participacion.estado == EN_PROGRESO).label("activo"),
            )
            .join(Convocatoria, Convocatoria.id == Participacion.convocatoria_id)
            .where(Convocatoria.sesion_id == sesion_id)
            .group_by(Participacion.convocatoria_id)
            .subquery()
        )
        intentos = func.coalesce(por_convocatoria.c.intentos, 0)
        calificados = func.coalesce(por_convocatoria.c.calificados, 0)
        activo = func.coalesce(por_convocatoria.c.activo, false())
        revocada = Convocatoria.revocada_en.is_not(None)
        vigente = Convocatoria.revocada_en.is_(None)
        finalizada = estado_sesion == EstadoSesionEnum.FINALIZADO

        condiciones: list[ColumnElement[bool]] = [Convocatoria.sesion_id == sesion_id]
        if filtro.convocatoria == "activas":
            condiciones.append(vigente)
        elif filtro.convocatoria == "revocadas":
            condiciones.append(revocada)
        if filtro.condicion == CondicionConvocado.REVOCADA:
            condiciones.append(revocada)
        elif filtro.condicion == CondicionConvocado.PARTICIPO:
            condiciones += [vigente, intentos > 0]
        elif filtro.condicion == CondicionConvocado.AUSENTE:
            condiciones += [vigente, intentos == 0, true() if finalizada else false()]
        elif filtro.condicion == CondicionConvocado.PENDIENTE:
            condiciones += [vigente, intentos == 0, false() if finalizada else true()]
        if filtro.estado_participacion is not None:
            condiciones.append(
                exists().where(
                    Participacion.convocatoria_id == Convocatoria.id, Participacion.estado == filtro.estado_participacion
                )
            )
        if filtro.con_nota is not None:
            condiciones.append(calificados > 0 if filtro.con_nota else calificados == 0)
        if filtro.intento_activo is not None:
            condiciones.append(activo.is_(true()) if filtro.intento_activo else activo.is_(false()))
        if filtro.buscar:
            patron = _patron(filtro.buscar)
            condiciones.append(
                or_(
                    Usuario.nombre_completo.ilike(patron, escape="\\"),
                    Usuario.correo.ilike(patron, escape="\\"),
                    Usuario.codigo_institucional.ilike(patron, escape="\\"),
                )
            )
        return (
            select(
                Convocatoria.id.label("convocatoria_id"),
                Convocatoria.revocada_en,
                Convocatoria.intentos_autorizados,
                Usuario.id.label("estudiante_id"),
                Usuario.nombre_completo,
                Usuario.correo,
                Usuario.codigo_institucional,
                intentos.label("intentos"),
                calificados.label("calificados"),
                activo.label("activo"),
            )
            .select_from(Convocatoria)
            .join(Usuario, Usuario.id == Convocatoria.estudiante_id)
            .outerjoin(por_convocatoria, por_convocatoria.c.convocatoria_id == Convocatoria.id)
            .where(*condiciones)
        )

    def contar_estudiantes(self, sesion_id: uuid.UUID, estado_sesion: EstadoSesionEnum, filtro: FiltroEstudiantes) -> int:
        consulta = self._estudiantes(sesion_id, estado_sesion, filtro).subquery()
        return self._session.scalar(select(func.count()).select_from(consulta)) or 0

    def pagina_estudiantes(
        self, sesion_id: uuid.UUID, estado_sesion: EstadoSesionEnum, filtro: FiltroEstudiantes, *, skip: int, limit: int
    ) -> list[Any]:
        stmt = (
            self._estudiantes(sesion_id, estado_sesion, filtro)
            .order_by(Usuario.nombre_completo, Usuario.id)
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.execute(stmt))

    def convocatoria_de_estudiante(self, sesion_id: uuid.UUID, estudiante_id: uuid.UUID) -> Any | None:
        return self._session.execute(
            select(
                Convocatoria.id.label("convocatoria_id"),
                Convocatoria.revocada_en,
                Convocatoria.intentos_autorizados,
                Usuario.id.label("estudiante_id"),
                Usuario.nombre_completo,
                Usuario.correo,
                Usuario.codigo_institucional,
            )
            .join(Usuario, Usuario.id == Convocatoria.estudiante_id)
            .where(Convocatoria.sesion_id == sesion_id, Convocatoria.estudiante_id == estudiante_id)
        ).first()

    # --- Intentos ---------------------------------------------------------------------------------

    def intentos_breves(self, convocatoria_ids: Sequence[uuid.UUID]) -> list[Any]:
        """Intentos de una página de convocatorias (una sola consulta: sin N+1)."""
        if not convocatoria_ids:
            return []
        respondidas = select(func.count()).where(Respuesta.participacion_id == Participacion.id).scalar_subquery()
        stmt = (
            select(
                Participacion.id,
                Participacion.convocatoria_id,
                Participacion.numero_intento,
                Participacion.estado,
                Participacion.motivo_cierre,
                Participacion.nota_final,
                respondidas.label("respondidas"),
            )
            .where(Participacion.convocatoria_id.in_(convocatoria_ids))
            .order_by(Participacion.convocatoria_id, Participacion.numero_intento)
        )
        return list(self._session.execute(stmt))

    def intentos_detallados(
        self, sesion_id: uuid.UUID, *, convocatoria_id: uuid.UUID | None = None, convocatorias: Select | None = None, limite: int | None = None
    ) -> list[Any]:
        """Un intento por fila con respondidas y aciertos (regla del módulo 5: opción elegida `es_correcta`)."""
        condiciones = [Convocatoria.sesion_id == sesion_id]
        if convocatoria_id is not None:
            condiciones.append(Convocatoria.id == convocatoria_id)
        if convocatorias is not None:
            condiciones.append(Convocatoria.id.in_(convocatorias))
        stmt = (
            select(
                Participacion.id,
                Participacion.numero_intento,
                Participacion.inicio,
                Participacion.fin,
                Participacion.estado,
                Participacion.motivo_cierre,
                Participacion.nota_final,
                Convocatoria.id.label("convocatoria_id"),
                Usuario.id.label("estudiante_id"),
                Usuario.nombre_completo,
                Usuario.correo,
                Usuario.codigo_institucional,
                func.count(Respuesta.id).label("respondidas"),
                func.count(Respuesta.id).filter(Opcion.es_correcta.is_(True)).label("aciertos"),
            )
            .select_from(Participacion)
            .join(Convocatoria, Convocatoria.id == Participacion.convocatoria_id)
            .join(Usuario, Usuario.id == Convocatoria.estudiante_id)
            .outerjoin(Respuesta, Respuesta.participacion_id == Participacion.id)
            .outerjoin(Opcion, Opcion.id == Respuesta.opcion_id)
            .where(*condiciones)
            .group_by(Participacion.id, Convocatoria.id, Usuario.id)
            .order_by(Usuario.nombre_completo, Usuario.id, Participacion.numero_intento)
        )
        if limite is not None:
            stmt = stmt.limit(limite)
        return list(self._session.execute(stmt))

    def ids_convocatorias(self, sesion_id: uuid.UUID, estado_sesion: EstadoSesionEnum, filtro: FiltroEstudiantes) -> Select:
        return self._estudiantes(sesion_id, estado_sesion, filtro).with_only_columns(Convocatoria.id)

    def estudiantes_para_exportar(
        self, sesion_id: uuid.UUID, estado_sesion: EstadoSesionEnum, filtro: FiltroEstudiantes, limite: int
    ) -> list[Any]:
        stmt = self._estudiantes(sesion_id, estado_sesion, filtro).order_by(Usuario.nombre_completo, Usuario.id).limit(limite)
        return list(self._session.execute(stmt))

    # --- Notas ------------------------------------------------------------------------------------

    def agregado_notas(
        self, sesiones: Select | Sequence[uuid.UUID], escala_max: Decimal | None, *, por_estado: bool = False
    ) -> dict[EstadoParticipacionEnum | None, AgregadoNotas]:
        """Estadísticas de las notas REGISTRADAS calculadas en PostgreSQL (sin traer las notas).

        Mediana exacta: `percentile_disc(0.5)` en orden ascendente y descendente da los dos
        valores centrales (numeric, sin pasar por coma flotante). Tramos con la misma expresión
        que `calculations.indice_tramo`. `por_estado` agrupa por FINALIZADA / EXPIRADA.
        """
        nota = Participacion.nota_final
        filtros = (Convocatoria.sesion_id.in_(sesiones), nota.is_not(None), Participacion.estado != EN_PROGRESO)
        clave = [Participacion.estado] if por_estado else []

        def base(*columnas):
            return (
                select(*clave, *columnas)
                .select_from(Participacion)
                .join(Convocatoria, Convocatoria.id == Participacion.convocatoria_id)
                .where(*filtros)
            )

        stmt = base(
            func.count(),
            func.min(nota),
            func.max(nota),
            func.sum(nota),
            func.percentile_disc(0.5).within_group(nota.asc()),
            func.percentile_disc(0.5).within_group(nota.desc()),
        )
        if por_estado:
            stmt = stmt.group_by(Participacion.estado)
        resumen = {(f[0] if por_estado else None): f[len(clave):] for f in self._session.execute(stmt)}

        tramos: dict = {k: {} for k in resumen}
        if escala_max is not None and escala_max > 0:
            indice = func.least(func.floor(nota * TRAMOS_DISTRIBUCION / escala_max), TRAMOS_DISTRIBUCION - 1)
            stmt = base(indice, func.count()).group_by(*clave, indice)
            for f in self._session.execute(stmt):
                k = f[0] if por_estado else None
                tramos.setdefault(k, {})[int(f[len(clave)])] = f[len(clave) + 1]
        return {
            k: AgregadoNotas(r[0], r[1], r[2], r[3], r[4], r[5], tramos.get(k, {})) if r[0] else AgregadoNotas()
            for k, r in resumen.items()
        }

    def estudiantes_con_nota(self, sesiones: Select | Sequence[uuid.UUID]) -> int:
        stmt = (
            select(func.count(func.distinct(Convocatoria.estudiante_id)))
            .join(Participacion, Participacion.convocatoria_id == Convocatoria.id)
            .where(Convocatoria.sesion_id.in_(sesiones), Participacion.nota_final.is_not(None))
        )
        return self._session.scalar(stmt) or 0

    def promedio_normalizado(self, sesiones: Select) -> Decimal | None:
        """Promedio de nota × 100 / escala de la rúbrica de CADA caso (normalización explícita)."""
        stmt = (
            select(func.avg(Participacion.nota_final * 100 / Rubrica.escala_max))
            .select_from(Participacion)
            .join(Convocatoria, Convocatoria.id == Participacion.convocatoria_id)
            .join(Sesion, Sesion.id == Convocatoria.sesion_id)
            .join(Rubrica, Rubrica.caso_id == Sesion.caso_id)
            .where(Sesion.id.in_(sesiones), Participacion.nota_final.is_not(None))
        )
        return self._session.scalar(stmt)

    def casos_utilizados(self, sesiones: Select) -> list[Any]:
        stmt = (
            select(
                CasoEstudio.id,
                CasoEstudio.nombre,
                CasoEstudio.estado,
                Rubrica.escala_max,
                func.count(func.distinct(Sesion.id)).label("sesiones"),
                func.count(Participacion.nota_final).label("evaluaciones"),
                func.avg(Participacion.nota_final).label("promedio"),
            )
            .select_from(Sesion)
            .join(CasoEstudio, CasoEstudio.id == Sesion.caso_id)
            .outerjoin(Rubrica, Rubrica.caso_id == CasoEstudio.id)
            .outerjoin(Convocatoria, Convocatoria.sesion_id == Sesion.id)
            .outerjoin(Participacion, Participacion.convocatoria_id == Convocatoria.id)
            .where(Sesion.id.in_(sesiones))
            .group_by(CasoEstudio.id, Rubrica.id)
            .order_by(CasoEstudio.nombre, CasoEstudio.id)
        )
        return list(self._session.execute(stmt))

    # --- Contenido del caso: rúbrica y preguntas -----------------------------------------------------

    def rubrica(self, caso_id: uuid.UUID) -> Rubrica | None:
        stmt = select(Rubrica).where(Rubrica.caso_id == caso_id).options(selectinload(Rubrica.criterios))
        return self._session.scalars(stmt).first()

    def preguntas_del_caso(self, caso_id: uuid.UUID) -> list[Any]:
        corregible = exists().where(Opcion.pregunta_id == Pregunta.id, Opcion.es_correcta.is_(True))
        stmt = (
            select(
                Pregunta.id,
                Pregunta.enunciado,
                Pregunta.orden,
                Pregunta.criterio_id,
                Escenario.titulo.label("escenario"),
                Escenario.orden.label("orden_escenario"),
                CriterioRubrica.descripcion.label("criterio"),
                corregible.label("corregible"),
            )
            .join(Escenario, Escenario.id == Pregunta.escenario_id)
            .outerjoin(CriterioRubrica, CriterioRubrica.id == Pregunta.criterio_id)
            .where(Escenario.caso_id == caso_id)
            .order_by(Escenario.orden, Pregunta.orden)
        )
        return list(self._session.execute(stmt))

    def total_preguntas(self, caso_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Pregunta).join(Escenario, Escenario.id == Pregunta.escenario_id).where(Escenario.caso_id == caso_id)
        return self._session.scalar(stmt) or 0

    # --- Corrección agregada (intentos cerrados) ------------------------------------------------------

    def _correccion(self, sesiones: Select | Sequence[uuid.UUID]) -> Select:
        """Cada intento cerrado × cada pregunta del caso de su sesión, con la respuesta guardada si existe."""
        return (
            select()
            .select_from(Participacion)
            .join(Convocatoria, Convocatoria.id == Participacion.convocatoria_id)
            .join(Sesion, Sesion.id == Convocatoria.sesion_id)
            .join(Escenario, Escenario.caso_id == Sesion.caso_id)
            .join(Pregunta, Pregunta.escenario_id == Escenario.id)
            .outerjoin(Respuesta, and_(Respuesta.participacion_id == Participacion.id, Respuesta.pregunta_id == Pregunta.id))
            .outerjoin(Opcion, Opcion.id == Respuesta.opcion_id)
            .where(Sesion.id.in_(sesiones), Participacion.estado != EN_PROGRESO)
        )

    def correccion_por_criterio(self, sesiones: Select | Sequence[uuid.UUID]) -> list[FilaCriterioIntento]:
        stmt = self._correccion(sesiones).add_columns(
            Participacion.id,
            Pregunta.criterio_id,
            func.count(Pregunta.id),
            func.count(Respuesta.id),
            func.count(Respuesta.id).filter(Opcion.es_correcta.is_(True)),
            case((Participacion.nota_final.is_not(None), True), else_=False),
        ).group_by(Participacion.id, Pregunta.criterio_id)
        return [FilaCriterioIntento(*fila) for fila in self._session.execute(stmt)]

    def correccion_por_pregunta(self, sesiones: Select | Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int, int]]:
        """pregunta_id -> (intentos considerados, respondidas, aciertos)."""
        stmt = self._correccion(sesiones).add_columns(
            Pregunta.id,
            func.count(Participacion.id),
            func.count(Respuesta.id),
            func.count(Respuesta.id).filter(Opcion.es_correcta.is_(True)),
        ).group_by(Pregunta.id)
        return {fila[0]: (fila[1], fila[2], fila[3]) for fila in self._session.execute(stmt)}

    # --- Espacios y casos -------------------------------------------------------------------------------

    def espacio(self, espacio_id: uuid.UUID) -> Any | None:
        stmt = select(EspacioAcademico.id, EspacioAcademico.nombre, EspacioAcademico.periodo, EspacioAcademico.activo).where(
            EspacioAcademico.id == espacio_id
        )
        return self._session.execute(stmt).first()

    def docente_tiene_sesiones_en_espacio(self, espacio_id: uuid.UUID, docente_id: uuid.UUID) -> bool:
        stmt = select(exists().where(Sesion.espacio_academico_id == espacio_id, Sesion.docente_id == docente_id))
        return bool(self._session.scalar(stmt))

    def caso_del_autor(self, caso_id: uuid.UUID, autor_id: uuid.UUID) -> Any | None:
        """Misma regla de propiedad que el módulo 2 (`CasoRepository.get_owned`), en cualquier estado."""
        stmt = (
            select(CasoEstudio.id, CasoEstudio.nombre, CasoEstudio.estado, Rubrica.escala_max)
            .outerjoin(Rubrica, Rubrica.caso_id == CasoEstudio.id)
            .where(CasoEstudio.id == caso_id, CasoEstudio.autor_id == autor_id)
        )
        return self._session.execute(stmt).first()


__all__ = ["FiltroEstudiantes", "FiltroSesiones", "ReportesRepository"]
