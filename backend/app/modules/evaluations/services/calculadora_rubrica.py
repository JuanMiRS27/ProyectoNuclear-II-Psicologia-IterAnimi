"""Calculadora de rúbrica: el algoritmo académico COMÚN a todas las estrategias.

Es una función pura de (rúbrica, preguntas, respuestas guardadas): no consulta la base de
datos, no conoce el estado de la participación y no decide si la nota se registra. Esa
decisión es de cada estrategia (`strategies/`), que reutiliza esta calculadora en lugar de
duplicar la fórmula.

Política de calificación del módulo 5 (ver README, "Módulo 5"):

1. Corrección. Una pregunta es ACIERTO si la opción elegida tiene `es_correcta = true`
   (cualquiera de las correctas sirve), ERROR si es incorrecta y SIN_RESPUESTA si no hay
   respuesta guardada. SIN_RESPUESTA nunca cuenta como acierto.
2. Agrupación. Las preguntas se agrupan por `criterio_id`. Para cada criterio:
   porcentaje = aciertos × 100 / total de preguntas del criterio (valor exacto).
3. Criterios sin preguntas: se excluyen (SIN_EVIDENCIA) y los pesos de los demás se
   renormalizan. Si ningún criterio tiene preguntas, no hay nota posible (error).
4. Puntaje del criterio:
   - NIVELES, si TODOS sus niveles tienen `min_aciertos_pct`: se elige el nivel de mayor
     umbral que no supere el porcentaje (comparación exacta, sin redondear) y su `valor`
     es el puntaje. Los umbrales deben ser distintos, incluir uno de 0 (nivel base) y los
     valores no pueden superar `escala_max` ni decrecer al subir el umbral.
   - LINEAL, si algún nivel carece de umbral: puntaje = escala_max × porcentaje / 100. El
     nivel cualitativo queda sin asignar (no se inventan umbrales).
   Ambas políticas producen puntajes en la MISMA escala [0, escala_max], por eso pueden
   combinarse en una rúbrica.
5. Nota = Σ(puntaje × peso) / Σ(pesos de los criterios evaluables). Una sola división al
   final: equivale a Σ(puntaje × peso_efectivo / 100) sin arrastrar errores de la
   normalización. Se redondea UNA vez, a dos decimales, con ROUND_HALF_UP.
"""

import decimal
import uuid
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.modules.evaluations.dominio import (
    CERO,
    CIEN,
    NOTA_MAXIMA_ALMACENABLE,
    CorreccionPregunta,
    CriterioEvaluable,
    DesgloseRubrica,
    EvaluacionNoPosibleError,
    Nivel,
    PoliticaCriterio,
    PreguntaEvaluable,
    ResultadoCriterio,
    ResultadoPregunta,
    RubricaEvaluable,
    redondear,
)

# Contexto decimal propio: el resultado no depende de la configuración global del proceso.
_CONTEXTO = decimal.Context(prec=28, rounding=decimal.ROUND_HALF_EVEN, traps=[decimal.InvalidOperation, decimal.DivisionByZero])
SUMA_PESOS_REQUERIDA = Decimal("100.00")


class CalculadoraRubrica:
    def calcular(
        self,
        rubrica: RubricaEvaluable | None,
        preguntas: Sequence[PreguntaEvaluable],
        respuestas: Mapping[uuid.UUID, uuid.UUID],
    ) -> DesgloseRubrica:
        with decimal.localcontext(_CONTEXTO):
            rubrica = self.validar_rubrica(rubrica)
            correcciones = self.corregir(rubrica, preguntas, respuestas)
            return self._ponderar(rubrica, correcciones)

    # --- 0. Validación ------------------------------------------------------------------------

    @staticmethod
    def validar_rubrica(rubrica: RubricaEvaluable | None) -> RubricaEvaluable:
        if rubrica is None:
            raise EvaluacionNoPosibleError("RUBRICA_INEXISTENTE", "El caso no tiene rúbrica.")
        if rubrica.escala_max is None or rubrica.escala_max <= CERO:
            raise EvaluacionNoPosibleError("RUBRICA_ESCALA_INVALIDA", "La escala máxima de la rúbrica debe ser positiva.")
        if rubrica.escala_max > NOTA_MAXIMA_ALMACENABLE:
            raise EvaluacionNoPosibleError(
                "RUBRICA_ESCALA_INVALIDA", f"La escala máxima no puede superar {NOTA_MAXIMA_ALMACENABLE}."
            )
        if not rubrica.criterios:
            raise EvaluacionNoPosibleError("RUBRICA_SIN_CRITERIOS", "La rúbrica no tiene criterios.")
        for criterio in rubrica.criterios:
            if criterio.peso is None or not (CERO < criterio.peso <= CIEN):
                raise EvaluacionNoPosibleError(
                    "CRITERIO_PESO_INVALIDO", f"El peso del criterio «{criterio.descripcion}» debe estar entre 0 y 100."
                )
        suma = sum((c.peso for c in rubrica.criterios), CERO)
        if suma != SUMA_PESOS_REQUERIDA:
            raise EvaluacionNoPosibleError(
                "RUBRICA_PESOS_NO_SUMAN_100", f"Los pesos de la rúbrica deben sumar 100 (suman {redondear(suma)})."
            )
        return rubrica

    # --- 1. Corrección ----------------------------------------------------------------------------

    @staticmethod
    def corregir(
        rubrica: RubricaEvaluable, preguntas: Sequence[PreguntaEvaluable], respuestas: Mapping[uuid.UUID, uuid.UUID]
    ) -> tuple[CorreccionPregunta, ...]:
        ids_criterios = {c.id for c in rubrica.criterios}
        por_id = {p.id: p for p in preguntas}
        ajenas = set(respuestas) - set(por_id)
        if ajenas:
            raise EvaluacionNoPosibleError("RESPUESTA_PREGUNTA_AJENA", "Hay respuestas a preguntas que no pertenecen al caso.")

        correcciones = []
        for pregunta in preguntas:
            if pregunta.criterio_id is None or pregunta.criterio_id not in ids_criterios:
                raise EvaluacionNoPosibleError(
                    "PREGUNTA_SIN_CRITERIO_VALIDO", "Hay preguntas sin un criterio de la rúbrica del caso."
                )
            correctas = tuple(o.id for o in pregunta.opciones if o.es_correcta)
            if not correctas:
                raise EvaluacionNoPosibleError(
                    "PREGUNTA_SIN_OPCION_CORRECTA", "Hay preguntas sin ninguna opción correcta: no se pueden corregir."
                )
            elegida = respuestas.get(pregunta.id)
            if elegida is None:
                resultado = ResultadoPregunta.SIN_RESPUESTA
            elif elegida not in {o.id for o in pregunta.opciones}:
                raise EvaluacionNoPosibleError("RESPUESTA_OPCION_AJENA", "Hay respuestas con opciones de otra pregunta.")
            else:
                resultado = ResultadoPregunta.ACIERTO if elegida in correctas else ResultadoPregunta.ERROR
            correcciones.append(CorreccionPregunta(pregunta.id, pregunta.criterio_id, resultado, elegida, correctas))
        return tuple(correcciones)

    # --- 2 a 5. Agrupación, niveles y ponderación -----------------------------------------------------

    def _ponderar(self, rubrica: RubricaEvaluable, correcciones: tuple[CorreccionPregunta, ...]) -> DesgloseRubrica:
        por_criterio: dict[uuid.UUID, list[CorreccionPregunta]] = {c.id: [] for c in rubrica.criterios}
        for correccion in correcciones:
            por_criterio[correccion.criterio_id].append(correccion)  # type: ignore[index]

        evaluables = [c for c in rubrica.criterios if por_criterio[c.id]]
        if not evaluables:
            raise EvaluacionNoPosibleError(
                "RUBRICA_SIN_EVIDENCIA", "Ningún criterio de la rúbrica tiene preguntas asociadas: no hay nota posible."
            )
        suma_evaluables = sum((c.peso for c in evaluables), CERO)

        resultados = []
        suma_aportes = CERO
        for criterio in rubrica.criterios:
            grupo = por_criterio[criterio.id]
            if not grupo:
                resultados.append(
                    ResultadoCriterio(
                        criterio_id=criterio.id,
                        descripcion=criterio.descripcion,
                        peso=criterio.peso,
                        politica=PoliticaCriterio.SIN_EVIDENCIA,
                        total_preguntas=0,
                        aciertos=0,
                        errores=0,
                        sin_responder=0,
                        porcentaje_aciertos=None,
                        peso_efectivo=CERO,
                        puntaje=None,
                        aporte=CERO,
                        advertencia="Sin preguntas asociadas: no hubo evidencia evaluable y no se penaliza.",
                    )
                )
                continue
            aciertos = sum(1 for c in grupo if c.resultado == ResultadoPregunta.ACIERTO)
            errores = sum(1 for c in grupo if c.resultado == ResultadoPregunta.ERROR)
            porcentaje = Decimal(aciertos) * CIEN / Decimal(len(grupo))
            politica, puntaje, nivel, advertencia = self.puntuar(criterio, porcentaje, rubrica.escala_max)
            ponderado = puntaje * criterio.peso
            suma_aportes += ponderado
            resultados.append(
                ResultadoCriterio(
                    criterio_id=criterio.id,
                    descripcion=criterio.descripcion,
                    peso=criterio.peso,
                    politica=politica,
                    total_preguntas=len(grupo),
                    aciertos=aciertos,
                    errores=errores,
                    sin_responder=len(grupo) - aciertos - errores,
                    porcentaje_aciertos=porcentaje,
                    peso_efectivo=criterio.peso * CIEN / suma_evaluables,
                    puntaje=puntaje,
                    aporte=ponderado / suma_evaluables,
                    nivel=nivel,
                    advertencia=advertencia,
                )
            )

        nota_exacta = suma_aportes / suma_evaluables
        nota = redondear(nota_exacta)
        if not (CERO <= nota <= rubrica.escala_max):  # garantía; no debería ocurrir con niveles validados
            raise EvaluacionNoPosibleError("NOTA_FUERA_DE_ESCALA", "La nota calculada está fuera de la escala de la rúbrica.")
        return DesgloseRubrica(rubrica.escala_max, tuple(resultados), correcciones, nota_exacta, nota)

    @classmethod
    def puntuar(
        cls, criterio: CriterioEvaluable, porcentaje: Decimal, escala_max: Decimal
    ) -> tuple[PoliticaCriterio, Decimal, str | None, str | None]:
        """Política del criterio y su puntaje en [0, escala_max]."""
        if criterio.niveles_invalidos:
            raise EvaluacionNoPosibleError(
                "CRITERIO_NIVELES_INVALIDOS", f"Los niveles del criterio «{criterio.descripcion}» no se pueden interpretar."
            )
        niveles = criterio.niveles
        if niveles and all(n.min_aciertos_pct is not None for n in niveles):
            nivel = cls.seleccionar_nivel(criterio, porcentaje, escala_max)
            return PoliticaCriterio.NIVELES, nivel.valor, nivel.nombre, None
        advertencia = (
            "El criterio no define umbrales en todos sus niveles: se calcula de forma lineal y sin nivel cualitativo."
            if niveles
            else "El criterio no define niveles: se calcula de forma lineal."
        )
        return PoliticaCriterio.LINEAL, escala_max * porcentaje / CIEN, None, advertencia

    @staticmethod
    def validar_niveles(criterio: CriterioEvaluable, escala_max: Decimal) -> list[Nivel]:
        """Reglas aplazadas por el módulo 2, exigidas aquí SOLO para calificar (no para publicar)."""
        nombre = criterio.descripcion
        ordenados = sorted(criterio.niveles, key=lambda n: n.min_aciertos_pct)  # type: ignore[arg-type, return-value]
        umbrales = [n.min_aciertos_pct for n in ordenados]
        if len(set(umbrales)) != len(umbrales):
            raise EvaluacionNoPosibleError("NIVELES_UMBRAL_DUPLICADO", f"El criterio «{nombre}» repite umbrales de aciertos.")
        if umbrales[0] != CERO:
            raise EvaluacionNoPosibleError(
                "NIVELES_SIN_NIVEL_BASE", f"El criterio «{nombre}» no tiene un nivel base con 0 % de aciertos."
            )
        if any(not (CERO <= u <= CIEN) for u in umbrales):  # type: ignore[operator]
            raise EvaluacionNoPosibleError("NIVELES_UMBRAL_INVALIDO", f"El criterio «{nombre}» tiene umbrales fuera de 0-100.")
        for nivel in ordenados:
            if not (CERO <= nivel.valor <= escala_max):
                raise EvaluacionNoPosibleError(
                    "NIVELES_VALOR_FUERA_DE_ESCALA",
                    f"El nivel «{nivel.nombre}» del criterio «{nombre}» tiene un valor fuera de la escala 0-{escala_max}.",
                )
        if any(b.valor < a.valor for a, b in zip(ordenados, ordenados[1:], strict=False)):
            raise EvaluacionNoPosibleError(
                "NIVELES_NO_MONOTONOS", f"En el criterio «{nombre}» un umbral mayor tiene un valor menor."
            )
        return ordenados

    @classmethod
    def seleccionar_nivel(cls, criterio: CriterioEvaluable, porcentaje: Decimal, escala_max: Decimal) -> Nivel:
        """Nivel de MAYOR umbral que no supera el porcentaje obtenido (comparación exacta)."""
        ordenados = cls.validar_niveles(criterio, escala_max)
        alcanzados = [n for n in ordenados if n.min_aciertos_pct <= porcentaje]  # type: ignore[operator]
        return alcanzados[-1]  # siempre existe: el nivel base tiene umbral 0
