"""Pruebas unitarias del módulo 5 (Strategy, calculadora de rúbrica y retroalimentación).

No usan PostgreSQL: trabajan con el dominio puro y dobles de prueba. El conftest de
`tests/unit/` hace fallar cualquier intento de conexión.
"""

import decimal
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core import security
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, PermissionDeniedError
from app.modules.auth.models import RolUsuario
from app.modules.evaluations import eventos
from app.modules.evaluations.dominio import (
    CondicionAcademica,
    CriterioEvaluable,
    EstadoCalificacion,
    EvaluacionNoPosibleError,
    Nivel,
    OpcionEvaluable,
    PoliticaCriterio,
    PreguntaEvaluable,
    ResultadoPregunta,
    RubricaEvaluable,
    SituacionAcademica,
    redondear,
)
from app.modules.evaluations.security import TIPO_TOKEN_RESULTADOS, crear_token_resultados, decodificar_token_resultados
from app.modules.evaluations.services import mapeo
from app.modules.evaluations.services.acceso_resultados_service import AccesoResultadosService
from app.modules.evaluations.services.calculadora_rubrica import CalculadoraRubrica
from app.modules.evaluations.services.evaluacion_service import EvaluacionService, ResumenProceso
from app.modules.evaluations.services.retroalimentacion_service import RetroalimentacionService
from app.modules.evaluations.strategies import (
    ContextoEvaluacion,
    EstrategiaEvaluacion,
    EstrategiaEvaluacionAusencia,
    EstrategiaEvaluacionCompleta,
    EstrategiaEvaluacionIncompleta,
    SelectorEstrategia,
)
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum, Participacion
from app.modules.sessions.models import EstadoSesionEnum
from app.modules.sessions.security import decodificar_token_estudiante, huella_codigo
from tests.unit.fabricas import convocatoria, sesion, sesion_bd, usuario

D = Decimal
FIN, EXP = EstadoParticipacionEnum.FINALIZADA, EstadoParticipacionEnum.EXPIRADA

# --- Constructores del dominio ----------------------------------------------------------------


def niveles_estandar() -> tuple[Nivel, ...]:
    """Ejemplo del enunciado: Bajo 1.00 (0 %), Medio 3.00 (50 %), Alto 5.00 (80 %)."""
    return (Nivel("Bajo", D("1.00"), D("0")), Nivel("Medio", D("3.00"), D("50")), Nivel("Alto", D("5.00"), D("80")))


def criterio(peso="100", niveles=(), descripcion="Análisis", invalidos=False) -> CriterioEvaluable:
    return CriterioEvaluable(uuid.uuid4(), descripcion, D(peso), tuple(niveles), invalidos)


def pregunta(criterio_id, correctas=1, incorrectas=2, texto="¿Qué ocurre?") -> PreguntaEvaluable:
    opciones = [OpcionEvaluable(uuid.uuid4(), f"Correcta {i}", True, f"Justifica {i}") for i in range(correctas)]
    opciones += [OpcionEvaluable(uuid.uuid4(), f"Incorrecta {i}", False, f"Refuta {i}") for i in range(incorrectas)]
    return PreguntaEvaluable(uuid.uuid4(), texto, criterio_id, tuple(opciones), "Escenario 1")


def correcta(p: PreguntaEvaluable, i: int = 0) -> uuid.UUID:
    return [o.id for o in p.opciones if o.es_correcta][i]


def incorrecta(p: PreguntaEvaluable) -> uuid.UUID:
    return next(o.id for o in p.opciones if not o.es_correcta)


def rubrica(*criterios, escala="5.00") -> RubricaEvaluable:
    return RubricaEvaluable(D(escala), tuple(criterios))


def situacion(rub=None, preguntas=(), respuestas=None, estado=FIN, motivo=MotivoCierreEnum.VOLUNTARIO, ausente=False):
    return SituacionAcademica(
        estudiante_id=uuid.uuid4(),
        convocatoria_id=uuid.uuid4(),
        sesion_id=uuid.uuid4(),
        rubrica=rub,
        preguntas=tuple(preguntas),
        participacion_id=None if ausente else uuid.uuid4(),
        numero_intento=None if ausente else 1,
        estado=None if ausente else estado,
        motivo_cierre=None if ausente else motivo,
        respuestas=respuestas or {},
    )


def caso_lineal(n_preguntas=4, escala="5.00"):
    c = criterio()
    ps = [pregunta(c.id) for _ in range(n_preguntas)]
    return rubrica(c, escala=escala), ps


calc = CalculadoraRubrica()


# --- Selección de estrategia y contexto -------------------------------------------------------


class TestSeleccionEstrategia:
    @pytest.mark.parametrize(
        ("kwargs", "esperada"),
        [
            ({"estado": FIN}, EstrategiaEvaluacionCompleta),
            ({"estado": EXP, "motivo": MotivoCierreEnum.TIEMPO_AGOTADO}, EstrategiaEvaluacionIncompleta),
            ({"ausente": True}, EstrategiaEvaluacionAusencia),
        ],
    )
    def test_selecciona_segun_situacion(self, kwargs, esperada):
        assert isinstance(SelectorEstrategia().seleccionar(situacion(**kwargs)), esperada)

    def test_en_progreso_no_tiene_estrategia(self):
        with pytest.raises(ConflictError):
            SelectorEstrategia().seleccionar(situacion(estado=EstadoParticipacionEnum.EN_PROGRESO, motivo=None))

    def test_seleccion_ambigua_falla(self):
        siempre = MagicMock(spec=EstrategiaEvaluacion)
        siempre.aplica_a.return_value = True
        with pytest.raises(RuntimeError):
            SelectorEstrategia([siempre, siempre]).seleccionar(situacion())

    def test_las_estrategias_comparten_una_calculadora(self):
        selector = SelectorEstrategia()
        calculadoras = {id(e._calculadora) for e in selector._estrategias}
        assert len(calculadoras) == 1

    def test_contexto_delega_y_permite_intercambiar(self):
        rub, ps = caso_lineal()
        sit = situacion(rub, ps)
        contexto = ContextoEvaluacion.para(sit)
        assert isinstance(contexto.estrategia, EstrategiaEvaluacionCompleta)
        doble = MagicMock(spec=EstrategiaEvaluacion)
        contexto.cambiar_estrategia(doble)
        contexto.evaluar(sit)
        doble.evaluar.assert_called_once_with(sit)

    def test_estrategia_es_abstracta(self):
        with pytest.raises(TypeError):
            EstrategiaEvaluacion()  # type: ignore[abstract]


# --- Estrategias concretas --------------------------------------------------------------------------


class TestEstrategiaCompleta:
    def test_califica_con_preguntas_sin_responder(self):
        rub, ps = caso_lineal(4)
        r = EstrategiaEvaluacionCompleta().evaluar(situacion(rub, ps, {ps[0].id: correcta(ps[0])}))
        assert r.condicion == CondicionAcademica.COMPLETA
        assert r.calificacion == EstadoCalificacion.CALIFICADA
        assert r.nota == D("1.25")  # 1 de 4 -> 25 % de 5
        assert r.desglose.sin_responder == 3
        assert any("sin responder" in o for o in r.observaciones)

    def test_sin_ninguna_respuesta_se_califica_con_cero(self):
        rub, ps = caso_lineal(2)
        r = EstrategiaEvaluacionCompleta().evaluar(situacion(rub, ps))
        assert (r.calificada, r.nota) == (True, D("0.00"))

    def test_rechaza_estado_o_motivo_incoherente(self):
        rub, ps = caso_lineal()
        estrategia = EstrategiaEvaluacionCompleta()
        with pytest.raises(ConflictError):
            estrategia.evaluar(situacion(rub, ps, estado=EXP, motivo=MotivoCierreEnum.TIEMPO_AGOTADO))
        with pytest.raises(ConflictError):
            estrategia.evaluar(situacion(rub, ps, motivo=MotivoCierreEnum.TIEMPO_AGOTADO))

    def test_no_modifica_las_respuestas(self):
        rub, ps = caso_lineal(3)
        respuestas = {ps[0].id: correcta(ps[0])}
        sit = situacion(rub, ps, respuestas)
        EstrategiaEvaluacionCompleta().evaluar(sit)
        assert sit.respuestas == {ps[0].id: correcta(ps[0])}


class TestEstrategiaIncompleta:
    @pytest.mark.parametrize("motivo", [MotivoCierreEnum.TIEMPO_AGOTADO, MotivoCierreEnum.CONVOCATORIA_REVOCADA, MotivoCierreEnum.SESION_FINALIZADA])
    def test_usa_solo_respuestas_guardadas_y_explica_la_causa(self, motivo):
        rub, ps = caso_lineal(4)
        r = EstrategiaEvaluacionIncompleta().evaluar(situacion(rub, ps, {ps[0].id: correcta(ps[0]), ps[1].id: incorrecta(ps[1])}, EXP, motivo))
        assert r.condicion == CondicionAcademica.INCOMPLETA
        assert r.motivo_cierre == motivo
        assert r.nota == D("1.25")  # misma rúbrica, sin penalización adicional
        assert "Intento incompleto." in r.observaciones
        assert any("2 respuestas guardadas" in o for o in r.observaciones)

    def test_misma_nota_que_una_completa_con_las_mismas_respuestas(self):
        rub, ps = caso_lineal(4)
        resp = {ps[0].id: correcta(ps[0]), ps[2].id: correcta(ps[2])}
        completa = EstrategiaEvaluacionCompleta().evaluar(situacion(rub, ps, resp))
        incompleta = EstrategiaEvaluacionIncompleta().evaluar(situacion(rub, ps, resp, EXP, MotivoCierreEnum.TIEMPO_AGOTADO))
        assert completa.nota == incompleta.nota

    def test_tiempo_agotado_sin_respuestas_se_califica(self):
        rub, ps = caso_lineal()
        r = EstrategiaEvaluacionIncompleta().evaluar(situacion(rub, ps, estado=EXP, motivo=MotivoCierreEnum.TIEMPO_AGOTADO))
        assert (r.calificada, r.nota) == (True, D("0.00"))

    @pytest.mark.parametrize("motivo", [MotivoCierreEnum.CONVOCATORIA_REVOCADA, MotivoCierreEnum.SESION_FINALIZADA])
    def test_cierre_administrativo_sin_respuestas_queda_sin_calificar(self, motivo):
        rub, ps = caso_lineal()
        r = EstrategiaEvaluacionIncompleta().evaluar(situacion(rub, ps, estado=EXP, motivo=motivo))
        assert r.calificacion == EstadoCalificacion.SIN_CALIFICAR
        assert r.nota is None
        assert r.desglose is not None  # el desglose informa, pero no se registra un cero

    def test_rechaza_participaciones_que_no_son_expiradas(self):
        rub, ps = caso_lineal()
        with pytest.raises(ConflictError):
            EstrategiaEvaluacionIncompleta().evaluar(situacion(rub, ps))
        with pytest.raises(ConflictError):
            EstrategiaEvaluacionIncompleta().evaluar(situacion(rub, ps, estado=EXP, motivo=MotivoCierreEnum.VOLUNTARIO))


class TestEstrategiaAusencia:
    def test_ausencia_sin_nota_ni_desglose(self):
        calculadora = MagicMock(spec=CalculadoraRubrica)
        r = EstrategiaEvaluacionAusencia(calculadora).evaluar(situacion(ausente=True))
        assert r.condicion == CondicionAcademica.AUSENCIA
        assert r.calificacion == EstadoCalificacion.SIN_CALIFICAR
        assert (r.nota, r.desglose, r.participacion_id) == (None, None, None)
        calculadora.calcular.assert_not_called()

    def test_ausencia_distinta_de_cero_aciertos(self):
        rub, ps = caso_lineal()
        cero = EstrategiaEvaluacionCompleta().evaluar(situacion(rub, ps))
        ausencia = EstrategiaEvaluacionAusencia().evaluar(situacion(ausente=True))
        assert cero.nota == D("0.00") and ausencia.nota is None
        assert cero.condicion != ausencia.condicion

    def test_rechaza_participacion_existente(self):
        with pytest.raises(ConflictError):
            EstrategiaEvaluacionAusencia().evaluar(situacion())


# --- Corrección ----------------------------------------------------------------------------------


class TestCorreccion:
    def test_una_opcion_correcta(self):
        rub, ps = caso_lineal(2)
        d = calc.calcular(rub, ps, {ps[0].id: correcta(ps[0]), ps[1].id: incorrecta(ps[1])})
        assert [c.resultado for c in d.correcciones] == [ResultadoPregunta.ACIERTO, ResultadoPregunta.ERROR]

    def test_cualquiera_de_varias_correctas_es_acierto(self):
        c = criterio()
        p = pregunta(c.id, correctas=3)
        for i in range(3):
            d = calc.calcular(rubrica(c), [p], {p.id: correcta(p, i)})
            assert d.correcciones[0].acertada
            assert len(d.correcciones[0].opciones_correctas) == 3

    def test_sin_respuesta_no_es_acierto(self):
        rub, ps = caso_lineal(1)
        d = calc.calcular(rub, ps, {})
        assert d.correcciones[0].resultado == ResultadoPregunta.SIN_RESPUESTA
        assert (d.aciertos, d.errores, d.sin_responder) == (0, 0, 1)

    def test_respuesta_a_pregunta_ajena(self):
        rub, ps = caso_lineal(1)
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rub, ps, {uuid.uuid4(): uuid.uuid4()})
        assert exc.value.codigo == "RESPUESTA_PREGUNTA_AJENA"

    def test_opcion_de_otra_pregunta(self):
        rub, ps = caso_lineal(2)
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rub, ps, {ps[0].id: correcta(ps[1])})
        assert exc.value.codigo == "RESPUESTA_OPCION_AJENA"

    def test_pregunta_sin_criterio_de_la_rubrica(self):
        rub, _ = caso_lineal(1)
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rub, [pregunta(uuid.uuid4())], {})
        assert exc.value.codigo == "PREGUNTA_SIN_CRITERIO_VALIDO"

    def test_pregunta_sin_opcion_correcta(self):
        c = criterio()
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rubrica(c), [pregunta(c.id, correctas=0)], {})
        assert exc.value.codigo == "PREGUNTA_SIN_OPCION_CORRECTA"


# --- Agrupación, porcentajes y ponderación ---------------------------------------------------------


class TestPonderacion:
    def test_agrupa_por_criterio_y_calcula_porcentajes(self):
        a, b = criterio("60", descripcion="A"), criterio("40", descripcion="B")
        pa = [pregunta(a.id) for _ in range(4)]
        pb = [pregunta(b.id) for _ in range(2)]
        resp = {pa[0].id: correcta(pa[0]), pa[1].id: correcta(pa[1]), pa[2].id: incorrecta(pa[2]), pb[0].id: correcta(pb[0])}
        d = calc.calcular(rubrica(a, b), pa + pb, resp)
        ra, rb = d.criterios
        assert (ra.total_preguntas, ra.aciertos, ra.errores, ra.sin_responder, ra.porcentaje_aciertos) == (4, 2, 1, 1, D("50"))
        assert (rb.total_preguntas, rb.aciertos, rb.errores, rb.sin_responder, rb.porcentaje_aciertos) == (2, 1, 0, 1, D("50"))
        # lineal: 2.5 × 60 % + 2.5 × 40 % = 2.5
        assert d.nota == D("2.50")

    def test_ponderacion_con_pesos_distintos(self):
        a, b = criterio("70", descripcion="A"), criterio("30", descripcion="B")
        pa, pb = pregunta(a.id), pregunta(b.id)
        d = calc.calcular(rubrica(a, b, escala="10.00"), [pa, pb], {pa.id: correcta(pa)})
        assert d.nota == D("7.00")
        assert [redondear(c.aporte) for c in d.criterios] == [D("7.00"), D("0.00")]
        assert [c.peso_efectivo for c in d.criterios] == [D("70"), D("30")]

    def test_niveles_con_umbrales(self):
        c = criterio(niveles=niveles_estandar())
        ps = [pregunta(c.id) for _ in range(4)]
        resp = {p.id: correcta(p) for p in ps[:3]}  # 75 %
        d = calc.calcular(rubrica(c), ps, resp)
        assert (d.criterios[0].politica, d.criterios[0].nivel, d.criterios[0].puntaje) == (PoliticaCriterio.NIVELES, "Medio", D("3.00"))
        assert d.nota == D("3.00")

    @pytest.mark.parametrize(("aciertos", "nivel"), [(0, "Bajo"), (5, "Medio"), (8, "Alto"), (10, "Alto"), (4, "Bajo"), (7, "Medio")])
    def test_umbral_en_el_limite_exacto(self, aciertos, nivel):
        c = criterio(niveles=niveles_estandar())
        ps = [pregunta(c.id) for _ in range(10)]
        d = calc.calcular(rubrica(c), ps, {p.id: correcta(p) for p in ps[:aciertos]})
        assert d.criterios[0].nivel == nivel

    def test_comparacion_exacta_sin_redondear_el_porcentaje(self):
        """2 de 3 = 66.666…% no alcanza un umbral de 66.67 %."""
        c = criterio(niveles=(Nivel("Bajo", D("1"), D("0")), Nivel("Alto", D("5"), D("66.67"))))
        ps = [pregunta(c.id) for _ in range(3)]
        d = calc.calcular(rubrica(c), ps, {p.id: correcta(p) for p in ps[:2]})
        assert d.criterios[0].nivel == "Bajo"

    def test_niveles_sin_umbrales_usa_calculo_lineal(self):
        c = criterio(niveles=(Nivel("Bajo", D("1"), None), Nivel("Alto", D("5"), None)))
        ps = [pregunta(c.id) for _ in range(4)]
        d = calc.calcular(rubrica(c), ps, {ps[0].id: correcta(ps[0])})
        r = d.criterios[0]
        assert (r.politica, r.nivel, d.nota) == (PoliticaCriterio.LINEAL, None, D("1.25"))
        assert "lineal" in r.advertencia

    def test_umbrales_incompletos_usan_calculo_lineal(self):
        c = criterio(niveles=(Nivel("Bajo", D("1"), D("0")), Nivel("Alto", D("5"), None)))
        ps = [pregunta(c.id) for _ in range(2)]
        d = calc.calcular(rubrica(c), ps, {ps[0].id: correcta(ps[0])})
        assert (d.criterios[0].politica, d.criterios[0].nivel, d.nota) == (PoliticaCriterio.LINEAL, None, D("2.50"))

    def test_combina_criterios_por_niveles_y_lineales(self):
        a = criterio("50", niveles_estandar(), "A")
        b = criterio("50", (), "B")
        pa, pb = [pregunta(a.id) for _ in range(2)], [pregunta(b.id) for _ in range(2)]
        resp = {pa[0].id: correcta(pa[0]), pb[0].id: correcta(pb[0])}  # A 50 % -> Medio 3.00; B 50 % -> 2.50
        d = calc.calcular(rubrica(a, b), pa + pb, resp)
        assert d.nota == D("2.75")

    def test_criterio_sin_preguntas_se_excluye_y_renormaliza(self):
        a, b = criterio("60", descripcion="Con preguntas"), criterio("40", descripcion="Sin preguntas")
        ps = [pregunta(a.id) for _ in range(2)]
        d = calc.calcular(rubrica(a, b), ps, {p.id: correcta(p) for p in ps})
        ra, rb = d.criterios
        assert rb.politica == PoliticaCriterio.SIN_EVIDENCIA and not rb.evaluable
        assert (rb.peso_efectivo, rb.puntaje, rb.porcentaje_aciertos) == (D("0"), None, None)
        assert ra.peso_efectivo == D("100")
        assert d.nota == D("5.00")  # no se penaliza el criterio que no pudo responderse

    def test_normalizacion_con_tres_criterios(self):
        a, b, c = criterio("50", descripcion="A"), criterio("25", descripcion="B"), criterio("25", descripcion="C")
        pa, pb = pregunta(a.id), pregunta(b.id)
        d = calc.calcular(rubrica(a, b, c), [pa, pb], {pa.id: correcta(pa)})
        assert [redondear(x.peso_efectivo) for x in d.criterios] == [D("66.67"), D("33.33"), D("0.00")]
        assert d.nota_exacta == D("5") * D("50") / D("75")
        assert d.nota == D("3.33")

    def test_todos_los_criterios_sin_preguntas(self):
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rubrica(criterio()), [], {})
        assert exc.value.codigo == "RUBRICA_SIN_EVIDENCIA"


# --- Decimal, redondeo, escala y determinismo -----------------------------------------------------


class TestPrecision:
    def test_todos_los_valores_son_decimal(self):
        rub, ps = caso_lineal(3)
        d = calc.calcular(rub, ps, {ps[0].id: correcta(ps[0])})
        valores = [d.nota, d.nota_exacta] + [v for c in d.criterios for v in (c.porcentaje_aciertos, c.peso_efectivo, c.puntaje, c.aporte)]
        assert all(isinstance(v, Decimal) for v in valores)

    def test_redondeo_final_medio_hacia_arriba(self):
        assert redondear(D("2.345")) == D("2.35")
        assert redondear(D("2.344999")) == D("2.34")
        assert D("2.345").quantize(D("0.01"), rounding=decimal.ROUND_HALF_EVEN) == D("2.34")  # el modo importa

    def test_no_redondea_intermedios(self):
        """Pesos 33.33/33.33/33.34 con todo acertado dan exactamente 10.00, y un tercio de aciertos conserva
        su valor exacto (10/3) hasta el redondeo final."""
        cs = [criterio(p, descripcion=str(i)) for i, p in enumerate(("33.33", "33.33", "33.34"))]
        ps = [pregunta(c.id) for c in cs for _ in range(3)]
        resp = {p.id: correcta(p) for p in ps}
        d = calc.calcular(rubrica(*cs, escala="10.00"), ps, resp)
        assert d.nota == D("10.00")
        parcial = calc.calcular(rubrica(*cs, escala="10.00"), ps, {ps[0].id: correcta(ps[0])})
        assert parcial.nota_exacta == D("10") / D("3") * D("33.33") / D("100")
        assert parcial.nota == D("1.11")

    def test_nota_dentro_de_la_escala(self):
        rub, ps = caso_lineal(3, escala="99.99")
        d = calc.calcular(rub, ps, {p.id: correcta(p) for p in ps})
        assert d.nota == D("99.99")

    def test_independiente_del_contexto_decimal_global(self):
        rub, ps = caso_lineal(3)
        resp = {ps[0].id: correcta(ps[0])}
        esperado = calc.calcular(rub, ps, resp)
        with decimal.localcontext(decimal.Context(prec=3, rounding=decimal.ROUND_DOWN)):
            otro = calc.calcular(rub, ps, resp)
        assert otro.nota == esperado.nota == D("1.67")

    def test_resultados_deterministas(self):
        rub, ps = caso_lineal(5)
        resp = {ps[1].id: correcta(ps[1]), ps[3].id: incorrecta(ps[3])}
        resultados = {calc.calcular(rub, ps, dict(resp)) for _ in range(5)}
        assert len(resultados) == 1


# --- Rúbricas inválidas ---------------------------------------------------------------------------


class TestRubricaInvalida:
    @pytest.mark.parametrize(
        ("rub", "codigo"),
        [
            (None, "RUBRICA_INEXISTENTE"),
            (RubricaEvaluable(D("0"), ()), "RUBRICA_ESCALA_INVALIDA"),
            (RubricaEvaluable(D("100"), ()), "RUBRICA_ESCALA_INVALIDA"),
            (RubricaEvaluable(D("5"), ()), "RUBRICA_SIN_CRITERIOS"),
            (RubricaEvaluable(D("5"), (criterio("0"),)), "CRITERIO_PESO_INVALIDO"),
            (RubricaEvaluable(D("5"), (criterio("60"),)), "RUBRICA_PESOS_NO_SUMAN_100"),
        ],
    )
    def test_rubrica_no_evaluable(self, rub, codigo):
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rub, [], {})
        assert exc.value.codigo == codigo
        assert exc.value.status_code == 422

    @pytest.mark.parametrize(
        ("niveles", "codigo"),
        [
            ((Nivel("A", D("1"), D("0")), Nivel("B", D("2"), D("0"))), "NIVELES_UMBRAL_DUPLICADO"),
            ((Nivel("A", D("1"), D("10")), Nivel("B", D("2"), D("50"))), "NIVELES_SIN_NIVEL_BASE"),
            ((Nivel("A", D("1"), D("0")), Nivel("B", D("6"), D("50"))), "NIVELES_VALOR_FUERA_DE_ESCALA"),
            ((Nivel("A", D("4"), D("0")), Nivel("B", D("2"), D("50"))), "NIVELES_NO_MONOTONOS"),
            ((Nivel("A", D("1"), D("0")), Nivel("B", D("2"), D("150"))), "NIVELES_UMBRAL_INVALIDO"),
        ],
    )
    def test_niveles_no_interpretables(self, niveles, codigo):
        c = criterio(niveles=niveles)
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rubrica(c), [pregunta(c.id)], {})
        assert exc.value.codigo == codigo

    def test_niveles_mal_formados(self):
        c = criterio(invalidos=True)
        with pytest.raises(EvaluacionNoPosibleError) as exc:
            calc.calcular(rubrica(c), [pregunta(c.id)], {})
        assert exc.value.codigo == "CRITERIO_NIVELES_INVALIDOS"


# --- Mapeo desde las entidades ORM ------------------------------------------------------------------


class TestMapeo:
    def test_nivel_acepta_forma_almacenada_y_dsl(self):
        assert mapeo.nivel({"nombre": "A", "valor": D("1.00"), "min_aciertos_pct": D("0")}).min_aciertos_pct == D("0")
        assert mapeo.nivel({"nombre": "A", "valor": 1.5, "minAciertosPct": 50}).min_aciertos_pct == D("50")
        assert mapeo.nivel({"nombre": "A", "valor": D("1")}).min_aciertos_pct is None

    @pytest.mark.parametrize("dato", ["texto", {"valor": 1}, {"nombre": "A"}, {"nombre": "A", "valor": True}, {"nombre": "A", "valor": "x"}])
    def test_niveles_mal_formados_se_marcan(self, dato):
        from app.modules.cases.models import CriterioRubrica

        entidad = CriterioRubrica(id=uuid.uuid4(), descripcion="X", peso=D("100"), niveles=[dato])
        assert mapeo.criterio(entidad).niveles_invalidos

    def test_rubrica_y_preguntas_desde_un_caso(self):
        from tests.unit.fabricas import caso_valido

        caso = caso_valido()
        rub = mapeo.rubrica(caso.rubrica)
        assert rub.escala_max == caso.rubrica.escala_max and len(rub.criterios) == 2
        ps = mapeo.preguntas(caso)
        assert len(ps) == len(caso.preguntas) and all(p.opciones for p in ps)
        assert mapeo.rubrica(None) is None


# --- Retroalimentación ---------------------------------------------------------------------------------


class TestRetroalimentacion:
    def test_por_pregunta_usa_el_contenido_del_docente(self):
        rub, ps = caso_lineal(3)
        sit = situacion(rub, ps, {ps[0].id: correcta(ps[0]), ps[1].id: incorrecta(ps[1])})
        r = EstrategiaEvaluacionCompleta().evaluar(sit)
        retro = RetroalimentacionService().por_pregunta(r, sit.preguntas, rub)
        assert [x.resultado for x in retro] == [ResultadoPregunta.ACIERTO, ResultadoPregunta.ERROR, ResultadoPregunta.SIN_RESPUESTA]
        assert retro[0].opcion_elegida.justificacion == "Justifica 0"
        assert retro[1].opcion_elegida.justificacion == "Refuta 0"
        assert retro[2].opcion_elegida is None and retro[2].mensaje == "No respondiste esta pregunta."
        assert all(x.opciones_correctas and x.criterio == "Análisis" for x in retro)

    def test_general_resume_cifras_y_observaciones(self):
        c = criterio("100", niveles_estandar())
        ps = [pregunta(c.id) for _ in range(2)]
        r = EstrategiaEvaluacionIncompleta().evaluar(situacion(rubrica(c), ps, {ps[0].id: correcta(ps[0])}, EXP, MotivoCierreEnum.TIEMPO_AGOTADO))
        texto = RetroalimentacionService().general(r)
        assert "Intento incompleto." in texto and "tiempo máximo" in texto
        assert "Aciertos: 1 de 2" in texto and "nivel Medio" in texto and "Nota: 3.00 sobre 5.00" in texto

    def test_general_indica_criterio_sin_evidencia(self):
        a, b = criterio("50", descripcion="A"), criterio("50", descripcion="B")
        p = pregunta(a.id)
        r = EstrategiaEvaluacionCompleta().evaluar(situacion(rubrica(a, b), [p]))
        assert "«B»: sin preguntas asociadas" in RetroalimentacionService().general(r)

    def test_ausencia_sin_retroalimentacion_por_pregunta(self):
        r = EstrategiaEvaluacionAusencia().evaluar(situacion(ausente=True))
        assert RetroalimentacionService().por_pregunta(r, (), None) == []
        assert "Ausencia" in RetroalimentacionService().general(r)


# --- Servicio de evaluación (persistencia y eventos con dobles) --------------------------------------


class TestAplicarNotaYEventos:
    def _servicio(self):
        publicador = MagicMock()
        servicio = EvaluacionService(sesion_bd(), eventos_publicador=publicador)
        servicio._repo = MagicMock()
        return servicio, publicador

    def _resultado(self, nota):
        rub, ps = caso_lineal(1)
        r = EstrategiaEvaluacionCompleta().evaluar(situacion(rub, ps))
        return r if nota is None else type(r)(**{**{f: getattr(r, f) for f in r.__slots__}, "nota": D(nota)})

    @pytest.mark.parametrize(
        ("anterior", "nueva", "tipo", "campo"),
        [
            (None, "3.00", eventos.CALIFICACION_REGISTRADA, "registradas"),
            (D("2.00"), "3.00", eventos.CALIFICACION_ACTUALIZADA, "actualizadas"),
            (D("3.00"), "3.00", None, "sin_cambios"),
        ],
    )
    def test_aplica_solo_cambios_y_encola_un_evento(self, anterior, nueva, tipo, campo):
        servicio, _ = self._servicio()
        participacion = Participacion(id=uuid.uuid4(), convocatoria_id=uuid.uuid4(), nota_final=anterior)
        resumen = ResumenProceso(uuid.uuid4())
        cambio = servicio._aplicar(participacion, self._resultado(nueva), resumen.sesion_id, resumen)
        assert getattr(resumen, campo) == 1
        assert cambio == (tipo is not None)
        assert [e.tipo for e in servicio._pendientes] == ([tipo] if tipo else [])
        assert servicio._repo.registrar_nota.called == (tipo is not None)

    def test_eventos_solo_despues_del_commit(self):
        servicio, publicador = self._servicio()
        with servicio._transaction():
            servicio._pendientes.append(eventos.EventoEvaluacion(eventos.CALIFICACION_REGISTRADA, uuid.uuid4()))
            publicador.publicar.assert_not_called()
        servicio._session.commit.assert_called_once()
        publicador.publicar.assert_called_once()

    def test_error_revierte_y_descarta_eventos(self):
        servicio, publicador = self._servicio()
        with pytest.raises(EvaluacionNoPosibleError), servicio._transaction():
            servicio._pendientes.append(eventos.EventoEvaluacion(eventos.CALIFICACION_REGISTRADA, uuid.uuid4()))
            raise EvaluacionNoPosibleError("X", "fallo")
        servicio._session.rollback.assert_called_once()
        servicio._session.commit.assert_not_called()
        publicador.publicar.assert_not_called()
        assert servicio._pendientes == []

    def test_participacion_de_otro_docente_es_404(self):
        servicio, _ = self._servicio()
        servicio._repo.participacion_con_sesion.return_value = (MagicMock(), MagicMock(docente_id=uuid.uuid4()))
        with pytest.raises(NotFoundError):
            servicio.participacion_autorizada(uuid.uuid4(), usuario())

    def test_publicador_configurable_para_el_modulo_6(self):
        anterior = eventos.publicador()
        nuevo = MagicMock()
        try:
            eventos.configurar(nuevo)
            assert EvaluacionService(sesion_bd())._eventos is nuevo
        finally:
            eventos.configurar(anterior)

    def test_publicador_nulo_no_falla(self):
        eventos.PublicadorNulo().publicar(eventos.EventoEvaluacion(eventos.RESULTADOS_DISPONIBLES, uuid.uuid4()))


# --- Token y acceso de resultados ---------------------------------------------------------------------


def _claims(**extra):
    datos = {
        "estudiante_id": uuid.uuid4(),
        "convocatoria_id": uuid.uuid4(),
        "sesion_id": uuid.uuid4(),
        "version_usuario": 0,
        "huella_codigo": "abc",
        "duracion": timedelta(minutes=5),
    }
    return datos | extra


class TestTokenResultados:
    def test_ida_y_vuelta(self):
        datos = _claims()
        claims = decodificar_token_resultados(crear_token_resultados(**datos))
        assert (claims.estudiante_id, claims.convocatoria_id) == (datos["estudiante_id"], datos["convocatoria_id"])

    def test_no_sirve_como_token_de_resolucion_ni_docente(self):
        token = crear_token_resultados(**_claims())
        with pytest.raises(security.InvalidTokenError):
            decodificar_token_estudiante(token)
        with pytest.raises(security.InvalidTokenError):
            security.decode_access_token(token)

    def test_token_de_resolucion_no_sirve_para_resultados(self):
        from app.modules.sessions.security import crear_token_estudiante

        with pytest.raises(security.InvalidTokenError):
            decodificar_token_resultados(crear_token_estudiante(**_claims()))

    def test_claims_alterados(self):
        token = security.encode_token({"sub": "x", "conv": "y", "ses": "z", "ver": 0, "cod": "c"}, TIPO_TOKEN_RESULTADOS, timedelta(minutes=1))
        with pytest.raises(security.InvalidTokenError):
            decodificar_token_resultados(token)


class TestAccesoResultados:
    def _servicio(self, conv):
        servicio = AccesoResultadosService(sesion_bd())
        servicio._convocatorias = MagicMock()
        servicio._convocatorias.get_by_id.return_value = conv
        servicio._convocatorias.de_estudiante_por_correo.return_value = [conv]
        return servicio

    def _escenario(self, estado=EstadoSesionEnum.FINALIZADO, **conv_extra):
        estudiante = usuario(RolUsuario.ESTUDIANTE)
        ses = sesion(estado=estado)
        conv = convocatoria(ses, estudiante, **conv_extra)
        return estudiante, ses, conv

    def _token(self, conv, estudiante, **extra):
        datos = dict(
            estudiante_id=estudiante.id,
            convocatoria_id=conv.id,
            sesion_id=conv.sesion_id,
            version_usuario=estudiante.version_token,
            huella_codigo=huella_codigo(conv.codigo_autorizacion),
            duracion=timedelta(minutes=5),
        )
        return crear_token_resultados(**(datos | extra))

    def test_login_exige_sesion_finalizada(self):
        from tests.unit.fabricas import CODIGO

        estudiante, _, conv = self._escenario(EstadoSesionEnum.EN_CURSO)
        limitador = MagicMock()
        with pytest.raises(PermissionDeniedError):
            self._servicio(conv).ingresar_resultados(estudiante.correo, CODIGO, "1.1.1.1", limitador)
        limitador.registrar_exito.assert_called_once()

    def test_login_correcto_emite_token_de_resultados(self):
        from tests.unit.fabricas import CODIGO

        estudiante, _, conv = self._escenario()
        token = self._servicio(conv).ingresar_resultados(estudiante.correo, CODIGO, "1.1.1.1", MagicMock())
        assert decodificar_token_resultados(token.access_token).convocatoria_id == conv.id

    def test_codigo_incorrecto_cuenta_como_fallo(self):
        estudiante, _, conv = self._escenario()
        limitador = MagicMock()
        with pytest.raises(AuthenticationError):
            self._servicio(conv).ingresar_resultados(estudiante.correo, "ZZZZZZZZZZZZ", "1.1.1.1", limitador)
        limitador.registrar_fallo.assert_called_once_with(estudiante.correo, "1.1.1.1")

    def test_resolver_valido(self):
        estudiante, _, conv = self._escenario()
        acceso = self._servicio(conv).resolver_resultados(self._token(conv, estudiante))
        assert acceso.convocatoria is conv

    @pytest.mark.parametrize("alteracion", ["revocada", "otra_version", "inactivo", "en_curso", "otro_codigo", "otro_estudiante"])
    def test_resolver_rechaza_estado_actual_invalido(self, alteracion):
        from datetime import UTC, datetime

        estudiante, ses, conv = self._escenario()
        token = self._token(conv, estudiante)
        if alteracion == "revocada":
            conv.revocada_en = datetime(2026, 11, 3, tzinfo=UTC)
        elif alteracion == "otra_version":
            estudiante.version_token = 1
        elif alteracion == "inactivo":
            estudiante.activo = False
        elif alteracion == "en_curso":
            ses.estado = EstadoSesionEnum.EN_CURSO
        elif alteracion == "otro_codigo":
            token = self._token(conv, estudiante, huella_codigo="otra")
        else:
            token = self._token(conv, estudiante, estudiante_id=uuid.uuid4())
        with pytest.raises(AuthenticationError):
            self._servicio(conv).resolver_resultados(token)

    def test_resolver_token_basura(self):
        with pytest.raises(AuthenticationError):
            self._servicio(None).resolver_resultados("basura")
