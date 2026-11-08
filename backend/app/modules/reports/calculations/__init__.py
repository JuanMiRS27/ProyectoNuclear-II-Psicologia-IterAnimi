"""Cálculos PUROS del módulo 7: indicadores, estadísticas y clasificaciones.

No conocen SQLAlchemy ni FastAPI y se prueban sin PostgreSQL. Reciben conteos y valores ya
proyectados por el repositorio y devuelven estructuras inmutables.

Reglas comunes:

- Toda magnitud académica es `Decimal`; nunca `float`. Las cifras que se muestran se
  redondean una sola vez, a dos decimales, con el mismo redondeo del módulo 5
  (`ROUND_HALF_UP`, `evaluations.dominio.redondear`).
- Un porcentaje con denominador cero no se calcula: vale `None` (ausencia de datos), nunca
  0 % ni 100 %.
- Una nota nula NO es un cero: las estadísticas solo usan las notas registradas.
- No se consolida una nota por estudiante: las estadísticas son por INTENTO evaluado.
"""

import decimal
import enum
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.core.exceptions import UnprocessableEntityError
from app.modules.evaluations.dominio import CERO, CIEN, CriterioEvaluable, EvaluacionNoPosibleError, redondear
from app.modules.evaluations.services.calculadora_rubrica import CalculadoraRubrica
from app.modules.evaluations.strategies.incompleta import CIERRES_ADMINISTRATIVOS
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum
from app.modules.sessions.models import EstadoSesionEnum

# Contexto decimal propio (como la calculadora del módulo 5): independiente de la configuración global.
_CONTEXTO = decimal.Context(prec=28, rounding=decimal.ROUND_HALF_EVEN, traps=[decimal.InvalidOperation, decimal.DivisionByZero])
# Tramos de la distribución de notas, en porcentaje de la escala de la rúbrica.
TRAMOS_DISTRIBUCION = 5


# --- Porcentajes e indicadores ----------------------------------------------------------------


def porcentaje(numerador: int | Decimal, denominador: int | Decimal) -> Decimal | None:
    """numerador × 100 / denominador, redondeado a dos decimales; `None` si el denominador es 0."""
    if denominador == 0:
        return None
    if numerador < 0 or denominador < 0:
        raise ValueError("Los conteos no pueden ser negativos.")
    with decimal.localcontext(_CONTEXTO):
        return redondear(Decimal(numerador) * CIEN / Decimal(denominador))


@dataclass(frozen=True, slots=True)
class Indicador:
    """Tasa con su numerador y denominador explícitos (auditables)."""

    numerador: int
    denominador: int

    @property
    def porcentaje(self) -> Decimal | None:
        return porcentaje(self.numerador, self.denominador)


@dataclass(frozen=True, slots=True)
class ConteosConvocatorias:
    activas: int = 0
    revocadas: int = 0
    activas_con_intento: int = 0
    revocadas_con_intento: int = 0

    @property
    def activas_sin_intento(self) -> int:
        return self.activas - self.activas_con_intento


@dataclass(frozen=True, slots=True)
class ConteosIntentos:
    """Conteos por INTENTO (participación), no por estudiante."""

    en_progreso: int = 0
    finalizados: int = 0
    expirados: int = 0
    calificados: int = 0
    sin_calificar: int = 0  # cerrados sin nota por la política del módulo 5 (no son pendientes)
    pendientes: int = 0  # cerrados que el módulo 5 calificaría pero aún no tienen nota registrada
    expirados_tiempo: int = 0
    expirados_revocacion: int = 0
    expirados_fin_sesion: int = 0
    vencidos_sin_cerrar: int = 0  # EN_PROGRESO con el tiempo ya agotado (los cerrará el worker o la próxima consulta)

    @property
    def total(self) -> int:
        return self.en_progreso + self.finalizados + self.expirados

    @property
    def cerrados(self) -> int:
        return self.finalizados + self.expirados


@dataclass(frozen=True, slots=True)
class Indicadores:
    tasa_participacion: Indicador
    tasa_finalizacion: Indicador
    tasa_expiracion: Indicador
    tasa_calificacion: Indicador


def indicadores(convocatorias: ConteosConvocatorias, intentos: ConteosIntentos) -> Indicadores:
    """Fórmulas del módulo 7 (ver README, "Módulo 7").

    tasa_participacion = estudiantes con convocatoria ACTIVA y al menos un intento / convocatorias ACTIVAS
    tasa_finalizacion  = intentos FINALIZADOS (cierre voluntario) / intentos iniciados
    tasa_expiracion    = intentos EXPIRADOS / intentos iniciados
    tasa_calificacion  = intentos con nota registrada / intentos cerrados

    "Intentos iniciados" incluye los EN_PROGRESO; por eso finalización + expiración puede
    sumar menos de 100 % mientras la sesión está en curso.
    """
    return Indicadores(
        tasa_participacion=Indicador(convocatorias.activas_con_intento, convocatorias.activas),
        tasa_finalizacion=Indicador(intentos.finalizados, intentos.total),
        tasa_expiracion=Indicador(intentos.expirados, intentos.total),
        tasa_calificacion=Indicador(intentos.calificados, intentos.cerrados),
    )


# --- Clasificaciones ------------------------------------------------------------------------------


class CondicionConvocado(str, enum.Enum):
    PARTICIPO = "PARTICIPO"  # convocatoria activa con al menos un intento
    PENDIENTE = "PENDIENTE"  # convocatoria activa sin intentos y sesión aún no finalizada: no es ausencia
    AUSENTE = "AUSENTE"  # convocatoria activa sin intentos con la sesión FINALIZADA (política del módulo 5)
    REVOCADA = "REVOCADA"  # convocatoria retirada: se conserva su historial, pero no es una ausencia


def condicion_convocado(*, revocada: bool, intentos: int, estado_sesion: EstadoSesionEnum) -> CondicionConvocado:
    """La ausencia del módulo 5 (convocatoria activa sin intentos) solo se declara al FINALIZAR la sesión.

    Mientras la sesión está SIN_INICIAR o EN_CURSO el estudiante aún figura como PENDIENTE,
    aunque haya vencido el plazo de ingreso: la condición académica definitiva es la del cierre.
    """
    if revocada:
        return CondicionConvocado.REVOCADA
    if intentos > 0:
        return CondicionConvocado.PARTICIPO
    if estado_sesion == EstadoSesionEnum.FINALIZADO:
        return CondicionConvocado.AUSENTE
    return CondicionConvocado.PENDIENTE


class SituacionIntento(str, enum.Enum):
    EN_PROGRESO = "EN_PROGRESO"  # sin resultados académicos todavía
    CALIFICADO = "CALIFICADO"  # tiene `nota_final` registrada
    SIN_CALIFICAR = "SIN_CALIFICAR"  # cerrado y, por la política del módulo 5, sin nota (no es un cero)
    PENDIENTE_CALIFICACION = "PENDIENTE_CALIFICACION"  # el módulo 5 lo calificaría, pero aún no se procesó


def calificable(estado: EstadoParticipacionEnum, motivo: MotivoCierreEnum | None, respondidas: int) -> bool:
    """Misma decisión que las estrategias del módulo 5 (sin duplicar su fuente).

    FINALIZADA: siempre se califica (`EstrategiaEvaluacionCompleta`). EXPIRADA: se califica
    salvo un cierre administrativo sin respuestas (`EstrategiaEvaluacionIncompleta`, cuyo
    conjunto `CIERRES_ADMINISTRATIVOS` se reutiliza).
    """
    if estado == EstadoParticipacionEnum.FINALIZADA:
        return True
    if estado == EstadoParticipacionEnum.EXPIRADA:
        return respondidas > 0 or motivo not in CIERRES_ADMINISTRATIVOS
    return False


def situacion_intento(
    estado: EstadoParticipacionEnum, motivo: MotivoCierreEnum | None, nota: Decimal | None, respondidas: int
) -> SituacionIntento:
    if estado == EstadoParticipacionEnum.EN_PROGRESO:
        return SituacionIntento.EN_PROGRESO
    if nota is not None:
        return SituacionIntento.CALIFICADO
    if calificable(estado, motivo, respondidas):
        return SituacionIntento.PENDIENTE_CALIFICACION
    return SituacionIntento.SIN_CALIFICAR


def duracion_segundos(inicio: datetime, fin: datetime | None) -> int | None:
    """Duración registrada (fin − inicio); `None` para un intento sin cerrar."""
    if fin is None:
        return None
    return int((fin - inicio).total_seconds())


# --- Estadísticas de calificaciones -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TramoDistribucion:
    desde: Decimal
    hasta: Decimal
    cantidad: int
    incluye_hasta: bool

    def porcentaje_de(self, total: int) -> Decimal | None:
        return porcentaje(self.cantidad, total)


@dataclass(frozen=True, slots=True)
class EstadisticasNotas:
    evaluados: int
    escala_max: Decimal | None
    minimo: Decimal | None
    maximo: Decimal | None
    promedio: Decimal | None
    mediana: Decimal | None
    promedio_porcentaje_escala: Decimal | None
    distribucion: tuple[TramoDistribucion, ...]


def mediana(valores: Sequence[Decimal]) -> Decimal | None:
    """Mediana exacta: valor central o media de los dos centrales (sin redondear)."""
    if not valores:
        return None
    ordenados = sorted(valores)
    return _media_de_centrales(ordenados[(len(ordenados) - 1) // 2], ordenados[len(ordenados) // 2])


def _media_de_centrales(inferior: Decimal, superior: Decimal) -> Decimal:
    with decimal.localcontext(_CONTEXTO):
        return inferior if inferior == superior else (inferior + superior) / Decimal(2)


def indice_tramo(nota: Decimal, escala_max: Decimal) -> int:
    """Tramo (0..4) de una nota: floor(nota × 5 / escala), con la nota máxima en el último.

    PostgreSQL usa la MISMA expresión (`least(floor(nota * 5 / escala), 4)`) al agrupar.
    """
    if nota < CERO or nota > escala_max:
        raise ValueError("Hay notas fuera de la escala de la rúbrica; no se combinan.")
    with decimal.localcontext(_CONTEXTO):
        return min(int(nota * Decimal(TRAMOS_DISTRIBUCION) / escala_max), TRAMOS_DISTRIBUCION - 1)


def tramos(cantidades: Mapping[int, int], escala_max: Decimal | None) -> tuple[TramoDistribucion, ...]:
    """Cinco tramos de igual amplitud sobre la escala de la rúbrica: [0, 20 %), …, [80 %, 100 %].

    Una nota en un límite pertenece al tramo superior; la nota máxima, al último tramo.
    Sin escala no hay tramos (no se supone una escala de 5,0).
    """
    if escala_max is None or escala_max <= CERO:
        return ()
    if set(cantidades) - set(range(TRAMOS_DISTRIBUCION)):
        raise ValueError("Tramo de distribución inexistente.")
    with decimal.localcontext(_CONTEXTO):
        limites = [escala_max * Decimal(k) / Decimal(TRAMOS_DISTRIBUCION) for k in range(TRAMOS_DISTRIBUCION + 1)]
    return tuple(
        TramoDistribucion(redondear(limites[i]), redondear(limites[i + 1]), cantidades.get(i, 0), i == TRAMOS_DISTRIBUCION - 1)
        for i in range(TRAMOS_DISTRIBUCION)
    )


def distribucion(notas: Sequence[Decimal], escala_max: Decimal | None) -> tuple[TramoDistribucion, ...]:
    if escala_max is None or escala_max <= CERO:
        return ()
    cantidades: dict[int, int] = {}
    for nota in notas:
        indice = indice_tramo(nota, escala_max)
        cantidades[indice] = cantidades.get(indice, 0) + 1
    return tramos(cantidades, escala_max)


@dataclass(frozen=True, slots=True)
class AgregadoNotas:
    """Resumen de un conjunto de notas, calculable en PostgreSQL sin traer las notas una a una.

    `mediana_inferior`/`mediana_superior` son los valores centrales (iguales si el total es
    impar): en SQL, `percentile_disc(0.5)` en orden ascendente y descendente.
    """

    evaluados: int = 0
    minimo: Decimal | None = None
    maximo: Decimal | None = None
    suma: Decimal | None = None
    mediana_inferior: Decimal | None = None
    mediana_superior: Decimal | None = None
    tramos: Mapping[int, int] = field(default_factory=dict)


def agregar_notas(notas: Iterable[Decimal | None], escala_max: Decimal | None) -> AgregadoNotas:
    """Equivalente en Python de la agregación SQL (los `None` se descartan)."""
    valores = sorted(n for n in notas if n is not None)
    if not valores:
        return AgregadoNotas()
    cantidades: dict[int, int] = {}
    if escala_max is not None and escala_max > CERO:
        for nota in valores:
            indice = indice_tramo(nota, escala_max)
            cantidades[indice] = cantidades.get(indice, 0) + 1
    return AgregadoNotas(
        len(valores), valores[0], valores[-1], sum(valores, CERO), valores[(len(valores) - 1) // 2], valores[len(valores) // 2], cantidades
    )


def estadisticas_agregadas(agregado: AgregadoNotas, escala_max: Decimal | None) -> EstadisticasNotas:
    """Presenta un agregado: promedio y mediana exactos, redondeados una sola vez."""
    if agregado.evaluados == 0:
        return EstadisticasNotas(0, escala_max, None, None, None, None, None, tramos({}, escala_max))
    if escala_max is not None and agregado.maximo is not None and agregado.maximo > escala_max:
        raise ValueError("Hay notas fuera de la escala de la rúbrica; no se combinan.")
    with decimal.localcontext(_CONTEXTO):
        promedio_exacto = agregado.suma / Decimal(agregado.evaluados)
        promedio_pct = None
        if escala_max is not None and escala_max > CERO:
            promedio_pct = redondear(promedio_exacto * CIEN / escala_max)
    medio = _media_de_centrales(agregado.mediana_inferior, agregado.mediana_superior)
    return EstadisticasNotas(
        evaluados=agregado.evaluados,
        escala_max=escala_max,
        minimo=agregado.minimo,
        maximo=agregado.maximo,
        promedio=redondear(promedio_exacto),
        mediana=redondear(medio),
        promedio_porcentaje_escala=promedio_pct,
        distribucion=tramos(agregado.tramos, escala_max),
    )


def estadisticas_notas(notas: Iterable[Decimal | None], escala_max: Decimal | None) -> EstadisticasNotas:
    """Estadísticas descriptivas de las notas REGISTRADAS de un conjunto de intentos de la misma escala.

    Los `None` (sin calificar o pendientes) se descartan: nunca cuentan como cero.
    """
    return estadisticas_agregadas(agregar_notas(notas, escala_max), escala_max)


def normalizar(nota: Decimal, escala_max: Decimal) -> Decimal:
    """Nota como porcentaje de su escala (exacto): permite comparar casos con escalas distintas."""
    if escala_max <= CERO:
        raise ValueError("La escala debe ser positiva.")
    with decimal.localcontext(_CONTEXTO):
        return nota * CIEN / escala_max


def asegurar_escala_unica(escalas: Iterable[Decimal | None]) -> Decimal | None:
    """Impide promediar notas de escalas distintas sin normalizar."""
    distintas = {e for e in escalas if e is not None}
    if len(distintas) > 1:
        raise ValueError("Las notas pertenecen a escalas distintas: se requiere normalizarlas.")
    return next(iter(distintas), None)


# --- Desempeño por criterio -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilaCriterioIntento:
    """Corrección de UN intento cerrado agrupada por criterio (proyección SQL)."""

    participacion_id: uuid.UUID
    criterio_id: uuid.UUID | None
    preguntas: int
    respondidas: int
    aciertos: int
    calificado: bool


@dataclass(frozen=True, slots=True)
class EstadisticaCriterio:
    criterio_id: uuid.UUID
    descripcion: str
    peso: Decimal
    evaluable: bool
    total_preguntas: int
    intentos_considerados: int
    aciertos: int
    errores: int
    sin_responder: int
    porcentaje_aciertos: Decimal | None
    intentos_calificados: int
    puntaje_promedio: Decimal | None
    advertencia: str | None = None


SIN_PREGUNTAS = "Sin preguntas asociadas: no evaluable (SIN_EVIDENCIA en el módulo 5)."


def estadisticas_criterios(
    criterios: Sequence[CriterioEvaluable],
    escala_max: Decimal | None,
    preguntas_por_criterio: Mapping[uuid.UUID, int],
    filas: Iterable[FilaCriterioIntento],
    intentos_considerados: int,
) -> list[EstadisticaCriterio]:
    """Agrega por criterio la corrección de los intentos cerrados.

    - Denominador del porcentaje: preguntas del criterio × intentos considerados (cada intento
      corrige TODAS las preguntas del caso; una sin respuesta no es acierto).
    - `puntaje_promedio`: promedio, sobre los intentos CALIFICADOS, del puntaje que asigna
      `CalculadoraRubrica.puntuar` (módulo 5) al porcentaje del criterio en cada intento. No es
      otra fórmula: es la misma función, aplicada criterio por criterio.
    - Un criterio sin preguntas es no evaluable: sin porcentaje ni puntaje.
    """
    por_criterio: dict[uuid.UUID, list[FilaCriterioIntento]] = {c.id: [] for c in criterios}
    for fila in filas:
        if fila.criterio_id in por_criterio:
            por_criterio[fila.criterio_id].append(fila)

    resultado = []
    for criterio in criterios:
        total = preguntas_por_criterio.get(criterio.id, 0)
        if total == 0:
            resultado.append(
                EstadisticaCriterio(
                    criterio.id, criterio.descripcion, criterio.peso, False, 0, intentos_considerados,
                    0, 0, 0, None, 0, None, SIN_PREGUNTAS,
                )
            )
            continue
        grupo = por_criterio[criterio.id]
        aciertos = sum(f.aciertos for f in grupo)
        respondidas = sum(f.respondidas for f in grupo)
        posibles = total * intentos_considerados
        puntaje, calificados, advertencia = _puntaje_promedio(criterio, escala_max, [f for f in grupo if f.calificado])
        resultado.append(
            EstadisticaCriterio(
                criterio_id=criterio.id,
                descripcion=criterio.descripcion,
                peso=criterio.peso,
                evaluable=True,
                total_preguntas=total,
                intentos_considerados=intentos_considerados,
                aciertos=aciertos,
                errores=respondidas - aciertos,
                sin_responder=posibles - respondidas,
                porcentaje_aciertos=porcentaje(aciertos, posibles),
                intentos_calificados=calificados,
                puntaje_promedio=puntaje,
                advertencia=advertencia,
            )
        )
    return resultado


def _puntaje_promedio(
    criterio: CriterioEvaluable, escala_max: Decimal | None, filas: Sequence[FilaCriterioIntento]
) -> tuple[Decimal | None, int, str | None]:
    if not filas or escala_max is None:
        return None, len(filas), None
    try:
        with decimal.localcontext(_CONTEXTO):
            puntajes = [
                CalculadoraRubrica.puntuar(criterio, Decimal(f.aciertos) * CIEN / Decimal(f.preguntas), escala_max)[1]
                for f in filas
            ]
            return redondear(sum(puntajes, CERO) / Decimal(len(puntajes))), len(filas), None
    except EvaluacionNoPosibleError as exc:
        return None, len(filas), f"Puntaje no disponible: {exc.detail}"


# --- Desempeño por pregunta -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EstadisticaPregunta:
    intentos_considerados: int
    aciertos: int | None
    errores: int | None
    sin_responder: int
    porcentaje_aciertos: Decimal | None
    corregible: bool


def estadistica_pregunta(*, intentos: int, respondidas: int, aciertos: int, corregible: bool) -> EstadisticaPregunta:
    """Regla del módulo 5: ACIERTO si la opción elegida es correcta (cualquiera de las correctas).

    Una pregunta sin ninguna opción correcta no se puede corregir (el módulo 5 rechaza su
    evaluación): se informan las respuestas, pero no aciertos ni errores.
    """
    if respondidas > intentos or aciertos > respondidas:
        raise ValueError("Conteos de pregunta incoherentes.")
    if not corregible:
        return EstadisticaPregunta(intentos, None, None, intentos - respondidas, None, False)
    return EstadisticaPregunta(intentos, aciertos, respondidas - aciertos, intentos - respondidas, porcentaje(aciertos, intentos), True)


# --- Filtros temporales -----------------------------------------------------------------------------


class RangoFechasInvalido(UnprocessableEntityError):
    default_detail = "El rango de fechas no es válido."


def validar_rango(desde: datetime | None, hasta: datetime | None) -> None:
    """Semántica del rango: intervalo semiabierto [desde, hasta) sobre `sesion.inicio`, en UTC."""
    for valor in (desde, hasta):
        if valor is not None and valor.tzinfo is None:
            raise RangoFechasInvalido("Las fechas deben incluir zona horaria (p. ej., 2026-11-03T00:00:00Z).")
    if desde is not None and hasta is not None and desde >= hasta:
        raise RangoFechasInvalido("`desde` debe ser anterior a `hasta`.")
