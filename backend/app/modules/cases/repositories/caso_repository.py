import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.cases.models import CasoEstudio, Escenario, EstadoCasoEnum, Pregunta, Rubrica

# Carga completa del agregado en consultas separadas (compatible con SELECT ... FOR UPDATE).
_CONTENIDO_COMPLETO = (
    selectinload(CasoEstudio.escenarios).selectinload(Escenario.preguntas).selectinload(Pregunta.opciones),
    selectinload(CasoEstudio.rubrica).selectinload(Rubrica.criterios),
)


class CasoRepository:
    """Acceso a `caso_estudio` (raíz del agregado).

    Edición: solo los casos del autor (`get_owned`). Lectura y programación: los del autor y los PUBLICADOS de
    cualquier docente (`get_visible`, `list_visible`); los borradores y archivados ajenos siguen siendo invisibles.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_owned(
        self,
        caso_id: uuid.UUID,
        autor_id: uuid.UUID,
        *,
        for_update: bool = False,
        cargar_contenido: bool = False,
    ) -> CasoEstudio | None:
        """Devuelve el caso solo si pertenece al autor; un caso ajeno es indistinguible de uno inexistente.

        `for_update` bloquea la fila del caso hasta el fin de la transacción: todas las
        operaciones que modifican el caso o su contenido lo usan, de modo que una
        edición y una publicación concurrentes se ejecutan en serie.
        """
        stmt = select(CasoEstudio).where(CasoEstudio.id == caso_id, CasoEstudio.autor_id == autor_id)
        if for_update:
            stmt = stmt.with_for_update(of=CasoEstudio)
        if cargar_contenido:
            stmt = stmt.options(*_CONTENIDO_COMPLETO)
        # populate_existing: tras obtener el bloqueo se usan los valores actuales, no los de la caché de la sesión.
        stmt = stmt.execution_options(populate_existing=True)
        return self._session.scalars(stmt).first()

    @staticmethod
    def _visible(usuario_id: uuid.UUID):
        """Casos que un docente puede consultar: los suyos y los publicados por otros docentes."""
        return or_(CasoEstudio.autor_id == usuario_id, CasoEstudio.estado == EstadoCasoEnum.PUBLICADO)

    def get_visible(self, caso_id: uuid.UUID, usuario_id: uuid.UUID, *, cargar_contenido: bool = False) -> CasoEstudio | None:
        """Lectura (sin bloqueo): el caso si es del docente o si está publicado. Un caso no visible es indistinguible
        de uno inexistente."""
        stmt = select(CasoEstudio).where(CasoEstudio.id == caso_id, self._visible(usuario_id))
        if cargar_contenido:
            stmt = stmt.options(*_CONTENIDO_COMPLETO)
        return self._session.scalars(stmt.execution_options(populate_existing=True)).first()

    def list_visible(
        self, usuario_id: uuid.UUID, *, estado: EstadoCasoEnum | None, skip: int, limit: int
    ) -> tuple[list[CasoEstudio], int]:
        """Listado del docente: sus casos (en cualquier estado) y los publicados por otros docentes."""
        filters = [self._visible(usuario_id)]
        if estado is not None:
            filters.append(CasoEstudio.estado == estado)
        total = self._session.scalar(select(func.count()).select_from(CasoEstudio).where(*filters)) or 0
        stmt = (
            select(CasoEstudio)
            .where(*filters)
            .order_by(CasoEstudio.actualizado_en.desc(), CasoEstudio.id)
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.scalars(stmt)), total

    def list_by_author(
        self, autor_id: uuid.UUID, *, estado: EstadoCasoEnum | None, skip: int, limit: int
    ) -> tuple[list[CasoEstudio], int]:
        filters = [CasoEstudio.autor_id == autor_id]
        if estado is not None:
            filters.append(CasoEstudio.estado == estado)
        total = self._session.scalar(select(func.count()).select_from(CasoEstudio).where(*filters)) or 0
        stmt = (
            select(CasoEstudio)
            .where(*filters)
            .order_by(CasoEstudio.actualizado_en.desc(), CasoEstudio.id)
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.scalars(stmt)), total

    def add(self, caso: CasoEstudio) -> CasoEstudio:
        """Persiste el caso y, por cascada, todo su contenido (escenarios, preguntas, opciones, rúbrica)."""
        self._session.add(caso)
        self._session.flush()
        return caso

    def delete(self, caso: CasoEstudio) -> None:
        self._session.delete(caso)
        self._session.flush()
