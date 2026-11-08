"""Pruebas unitarias del módulo 7 (Seguimiento y Reportes).

No usan PostgreSQL: prueban los cálculos puros, los esquemas de filtros, el exportador CSV y
los servicios con un repositorio simulado. El conftest de `tests/unit/` hace fallar
cualquier intento de conexión.
"""

import csv
import io
import itertools
import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import NotFoundError
from app.modules.cases.models import EstadoCasoEnum
from app.modules.evaluations.dominio import (
    CondicionAcademica,
    CriterioEvaluable,
    Nivel,
    OpcionEvaluable,
    PreguntaEvaluable,
    RubricaEvaluable,
    SituacionAcademica,
)
from app.modules.evaluations.services.calculadora_rubrica import CalculadoraRubrica
from app.modules.evaluations.strategies import ContextoEvaluacion
from app.modules.evaluations.strategies.incompleta import CIERRES_ADMINISTRATIVOS
from app.modules.participations.models import EstadoParticipacionEnum as EP
from app.modules.participations.models import MotivoCierreEnum as MC
from app.modules.reports import calculations as calc
from app.modules.reports import exporters
from app.modules.reports import schemas as s
from app.modules.reports.calculations import CondicionConvocado, SituacionIntento
from app.modules.reports.repositories import FiltroEstudiantes, FiltroSesiones, ReportesRepository, _patron
from app.modules.reports.services import ExportacionService, ReportesAcademicosService, ReportesSesionService
from app.modules.reports.services.base import ServicioReportesBase, estadisticas, por_estado
from app.modules.reports.services.reportes_sesion import condicion_academica, intento_detalle
from app.modules.sessions.models import EstadoSesionEnum as ES
from tests.unit.fabricas import T8, T9, T10, sesion_bd

D = Decimal


# --- Porcentajes e indicadores -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("numerador", "denominador", "esperado"),
    [(1, 3, D("33.33")), (2, 3, D("66.67")), (1, 8, D("12.50")), (1, 800, D("0.13")), (0, 5, D("0.00")), (5, 5, D("100.00"))],
)
def test_porcentaje_redondea_a_dos_decimales_medio_hacia_arriba(numerador, denominador, esperado):
    assert calc.porcentaje(numerador, denominador) == esperado


def test_porcentaje_con_denominador_cero_es_ausencia_de_datos():
    assert calc.porcentaje(0, 0) is None
    assert calc.Indicador(0, 0).porcentaje is None


def test_porcentaje_rechaza_conteos_negativos():
    with pytest.raises(ValueError):
        calc.porcentaje(-1, 3)


def test_porcentaje_acepta_decimales_y_devuelve_decimal():
    assert calc.porcentaje(D("1.5"), D("3")) == D("50.00")
    assert isinstance(calc.porcentaje(1, 3), Decimal)


def test_indicadores_usan_denominadores_explicitos():
    conv = calc.ConteosConvocatorias(activas=4, revocadas=2, activas_con_intento=3, revocadas_con_intento=1)
    intentos = calc.ConteosIntentos(en_progreso=1, finalizados=5, expirados=2, calificados=6)
    ind = calc.indicadores(conv, intentos)

    assert (ind.tasa_participacion.numerador, ind.tasa_participacion.denominador) == (3, 4)  # las revocadas no cuentan
    assert ind.tasa_participacion.porcentaje == D("75.00")
    assert (ind.tasa_finalizacion.numerador, ind.tasa_finalizacion.denominador) == (5, 8)
    assert (ind.tasa_expiracion.numerador, ind.tasa_expiracion.denominador) == (2, 8)
    assert (ind.tasa_calificacion.numerador, ind.tasa_calificacion.denominador) == (6, 7)  # sobre intentos cerrados
    assert ind.tasa_finalizacion.porcentaje + ind.tasa_expiracion.porcentaje < D("100")  # hay uno en progreso


def test_sin_convocatorias_ni_intentos_todas_las_tasas_son_nulas():
    ind = calc.indicadores(calc.ConteosConvocatorias(), calc.ConteosIntentos())
    assert [i.porcentaje for i in (ind.tasa_participacion, ind.tasa_finalizacion, ind.tasa_expiracion, ind.tasa_calificacion)] == [None] * 4


def test_un_estudiante_con_tres_intentos_es_un_participante_y_tres_intentos():
    conv = calc.ConteosConvocatorias(activas=1, activas_con_intento=1)
    intentos = calc.ConteosIntentos(finalizados=2, expirados=1)
    ind = calc.indicadores(conv, intentos)
    assert ind.tasa_participacion.numerador == 1 and intentos.total == 3
    assert ind.tasa_participacion.porcentaje == D("100.00")


def test_totales_por_estado():
    c = calc.ConteosIntentos(en_progreso=2, finalizados=3, expirados=4)
    assert (c.total, c.cerrados) == (9, 7)
    assert calc.ConteosConvocatorias(activas=5, activas_con_intento=2).activas_sin_intento == 3


# --- Condición del convocado y situación del intento -------------------------------------------------------


@pytest.mark.parametrize(
    ("revocada", "intentos", "estado", "esperada"),
    [
        (False, 0, ES.SIN_INICIAR, CondicionConvocado.PENDIENTE),
        (False, 0, ES.EN_CURSO, CondicionConvocado.PENDIENTE),  # aún puede participar: no es ausencia
        (False, 0, ES.FINALIZADO, CondicionConvocado.AUSENTE),
        (False, 2, ES.EN_CURSO, CondicionConvocado.PARTICIPO),
        (False, 1, ES.FINALIZADO, CondicionConvocado.PARTICIPO),
        (True, 0, ES.FINALIZADO, CondicionConvocado.REVOCADA),  # revocada no es ausencia
        (True, 1, ES.EN_CURSO, CondicionConvocado.REVOCADA),
    ],
)
def test_condicion_del_convocado(revocada, intentos, estado, esperada):
    assert calc.condicion_convocado(revocada=revocada, intentos=intentos, estado_sesion=estado) == esperada


@pytest.mark.parametrize(
    ("estado", "motivo", "nota", "respondidas", "esperada"),
    [
        (EP.EN_PROGRESO, None, None, 3, SituacionIntento.EN_PROGRESO),
        (EP.FINALIZADA, MC.VOLUNTARIO, D("2.20"), 1, SituacionIntento.CALIFICADO),
        (EP.FINALIZADA, MC.VOLUNTARIO, None, 0, SituacionIntento.PENDIENTE_CALIFICACION),
        (EP.EXPIRADA, MC.TIEMPO_AGOTADO, None, 0, SituacionIntento.PENDIENTE_CALIFICACION),
        (EP.EXPIRADA, MC.SESION_FINALIZADA, None, 0, SituacionIntento.SIN_CALIFICAR),
        (EP.EXPIRADA, MC.CONVOCATORIA_REVOCADA, None, 0, SituacionIntento.SIN_CALIFICAR),
        (EP.EXPIRADA, MC.SESION_FINALIZADA, None, 2, SituacionIntento.PENDIENTE_CALIFICACION),
        (EP.EXPIRADA, MC.SESION_FINALIZADA, D("0.00"), 2, SituacionIntento.CALIFICADO),  # 0.00 registrado sí es una nota
    ],
)
def test_situacion_del_intento(estado, motivo, nota, respondidas, esperada):
    assert calc.situacion_intento(estado, motivo, nota, respondidas) == esperada


def _rubrica_simple() -> tuple[RubricaEvaluable, tuple[PreguntaEvaluable, ...]]:
    criterio = CriterioEvaluable(uuid.uuid4(), "Análisis", D("100"), (Nivel("Bajo", D("1"), D("0")), Nivel("Alto", D("5"), D("50"))))
    opciones = (OpcionEvaluable(uuid.uuid4(), "Sí", True, None), OpcionEvaluable(uuid.uuid4(), "No", False, None))
    pregunta = PreguntaEvaluable(uuid.uuid4(), "¿?", criterio.id, opciones)
    return RubricaEvaluable(D("5"), (criterio,)), (pregunta,)


@pytest.mark.parametrize(
    ("estado", "motivo"),
    [(EP.FINALIZADA, MC.VOLUNTARIO)] + [(EP.EXPIRADA, m) for m in (MC.TIEMPO_AGOTADO, MC.CONVOCATORIA_REVOCADA, MC.SESION_FINALIZADA)],
)
@pytest.mark.parametrize("con_respuesta", [False, True])
def test_calificable_coincide_con_las_estrategias_del_modulo_5(estado, motivo, con_respuesta):
    rubrica, preguntas = _rubrica_simple()
    respuestas = {preguntas[0].id: preguntas[0].opciones[0].id} if con_respuesta else {}
    situacion = SituacionAcademica(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), rubrica, preguntas, uuid.uuid4(), 1, estado, motivo, respuestas
    )
    resultado = ContextoEvaluacion.para(situacion).evaluar(situacion)
    assert calc.calificable(estado, motivo, len(respuestas)) == resultado.calificada


def test_calificable_reutiliza_los_cierres_administrativos_del_modulo_5():
    assert CIERRES_ADMINISTRATIVOS == {MC.CONVOCATORIA_REVOCADA, MC.SESION_FINALIZADA}
    assert calc.calificable(EP.EN_PROGRESO, None, 5) is False


def test_duracion_registrada():
    assert calc.duracion_segundos(T8, T9) == 3600
    assert calc.duracion_segundos(T8, None) is None


# --- Estadísticas de notas ------------------------------------------------------------------------------


def test_mediana_impar_par_y_vacia():
    assert calc.mediana([D("3"), D("1"), D("2")]) == D("2")
    assert calc.mediana([D("1.00"), D("2.25")]) == D("1.625")  # exacta; se redondea al presentarla
    assert calc.mediana([]) is None


def test_estadisticas_excluyen_notas_nulas_sin_tratarlas_como_cero():
    e = calc.estadisticas_notas([D("4.00"), None, D("2.00"), None], D("5.00"))
    assert e.evaluados == 2
    assert (e.minimo, e.maximo, e.promedio, e.mediana) == (D("2.00"), D("4.00"), D("3.00"), D("3.00"))
    assert e.promedio_porcentaje_escala == D("60.00")


def test_estadisticas_sin_notas_no_inventan_valores():
    e = calc.estadisticas_notas([None, None], D("5.00"))
    assert (e.evaluados, e.minimo, e.maximo, e.promedio, e.mediana, e.promedio_porcentaje_escala) == (0, None, None, None, None, None)
    assert all(t.cantidad == 0 and t.porcentaje_de(e.evaluados) is None for t in e.distribucion)


def test_promedio_con_decimal_y_redondeo_medio_hacia_arriba():
    # (1.00 + 1.00 + 1.01) / 3 = 1.00333… -> 1.00 ; (2.22 + 2.23) / 2 = 2.225 -> 2.23
    assert calc.estadisticas_notas([D("1.00"), D("1.00"), D("1.01")], D("5")).promedio == D("1.00")
    e = calc.estadisticas_notas([D("2.22"), D("2.23")], D("5"))
    assert (e.promedio, e.mediana) == (D("2.23"), D("2.23"))
    assert isinstance(e.promedio, Decimal)


def test_distribucion_en_cinco_tramos_con_limites_al_tramo_superior():
    notas = [D("0.00"), D("0.99"), D("1.00"), D("2.50"), D("4.99"), D("5.00")]
    tramos = calc.distribucion(notas, D("5.00"))
    assert [(t.desde, t.hasta) for t in tramos] == [
        (D("0.00"), D("1.00")), (D("1.00"), D("2.00")), (D("2.00"), D("3.00")), (D("3.00"), D("4.00")), (D("4.00"), D("5.00"))
    ]
    assert [t.cantidad for t in tramos] == [2, 1, 1, 0, 2]  # 1.00 va al segundo tramo; 5.00 al último
    assert [t.incluye_hasta for t in tramos] == [False, False, False, False, True]
    assert tramos[0].porcentaje_de(6) == D("33.33")


def test_distribucion_respeta_la_escala_de_la_rubrica():
    tramos = calc.distribucion([D("10.00"), D("7.00")], D("10.00"))
    assert [t.hasta for t in tramos] == [D("2.00"), D("4.00"), D("6.00"), D("8.00"), D("10.00")]
    assert [t.cantidad for t in tramos] == [0, 0, 0, 1, 1]


def test_distribucion_sin_escala_no_supone_cinco():
    assert calc.distribucion([D("3")], None) == ()
    assert calc.estadisticas_notas([D("3")], None).promedio_porcentaje_escala is None


def test_distribucion_rechaza_notas_fuera_de_escala():
    with pytest.raises(ValueError):
        calc.distribucion([D("6.00")], D("5.00"))


def test_agregado_equivalente_al_de_postgresql():
    a = calc.agregar_notas([D("3.00"), None, D("1.00"), D("5.00"), D("2.00")], D("5.00"))
    assert (a.evaluados, a.minimo, a.maximo, a.suma) == (4, D("1.00"), D("5.00"), D("11.00"))
    assert (a.mediana_inferior, a.mediana_superior) == (D("2.00"), D("3.00"))  # percentile_disc asc / desc
    assert dict(a.tramos) == {1: 1, 2: 1, 3: 1, 4: 1}
    e = calc.estadisticas_agregadas(a, D("5.00"))
    assert (e.promedio, e.mediana) == (D("2.75"), D("2.50"))
    assert e == calc.estadisticas_notas([D("3.00"), D("1.00"), D("5.00"), D("2.00")], D("5.00"))
    assert calc.agregar_notas([], D("5")) == calc.AgregadoNotas()
    assert calc.agregar_notas([D("2")], None).tramos == {}


def test_indice_de_tramo_y_tramos_invalidos():
    assert [calc.indice_tramo(D(n), D("5")) for n in ("0", "0.99", "1", "4.99", "5")] == [0, 0, 1, 4, 4]
    with pytest.raises(ValueError):
        calc.indice_tramo(D("-0.01"), D("5"))
    with pytest.raises(ValueError):
        calc.tramos({5: 1}, D("5"))
    with pytest.raises(ValueError):
        calc.estadisticas_agregadas(calc.AgregadoNotas(1, D("1"), D("6"), D("6"), D("6"), D("6")), D("5"))


def test_escalas_distintas_requieren_normalizacion():
    assert calc.normalizar(D("4.00"), D("5.00")) == D("80")
    assert calc.normalizar(D("8.00"), D("10.00")) == D("80")
    with pytest.raises(ValueError):
        calc.asegurar_escala_unica([D("5.00"), D("10.00")])
    assert calc.asegurar_escala_unica([D("5.00"), None, D("5.00")]) == D("5.00")
    assert calc.asegurar_escala_unica([]) is None
    with pytest.raises(ValueError):
        calc.normalizar(D("1"), D("0"))


# --- Criterios -----------------------------------------------------------------------------------------------

NIVELES = (Nivel("Insuficiente", D("1.00"), D("0")), Nivel("Aceptable", D("3.00"), D("50")), Nivel("Sobresaliente", D("5.00"), D("85")))


def _criterios():
    analisis = CriterioEvaluable(uuid.uuid4(), "Análisis", D("60"), NIVELES)
    decision = CriterioEvaluable(uuid.uuid4(), "Decisión", D("40"), ())  # sin niveles: lineal
    vacio = CriterioEvaluable(uuid.uuid4(), "Sin preguntas", D("0.01"), NIVELES)
    return analisis, decision, vacio


def test_criterio_sin_preguntas_es_no_evaluable():
    analisis, decision, vacio = _criterios()
    r = calc.estadisticas_criterios([vacio], D("5"), {}, [], 3)[0]
    assert (r.evaluable, r.total_preguntas, r.porcentaje_aciertos, r.puntaje_promedio) == (False, 0, None, None)
    assert r.advertencia == calc.SIN_PREGUNTAS and r.intentos_considerados == 3


def test_estadisticas_por_criterio_y_puntaje_del_modulo_5():
    analisis, decision, vacio = _criterios()
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    filas = [
        calc.FilaCriterioIntento(p1, analisis.id, 2, 2, 1, True),  # 50 % -> Aceptable 3.00
        calc.FilaCriterioIntento(p2, analisis.id, 2, 1, 1, True),  # 50 % -> 3.00
        calc.FilaCriterioIntento(p1, decision.id, 1, 1, 1, True),  # 100 % lineal -> 5.00
        calc.FilaCriterioIntento(p2, decision.id, 1, 0, 0, False),  # no calificado: no entra al puntaje
        calc.FilaCriterioIntento(p2, uuid.uuid4(), 1, 1, 1, True),  # criterio ajeno: se ignora
    ]
    a, d, v = calc.estadisticas_criterios([analisis, decision, vacio], D("5"), {analisis.id: 2, decision.id: 1}, filas, 2)

    assert (a.aciertos, a.errores, a.sin_responder, a.porcentaje_aciertos) == (2, 1, 1, D("50.00"))
    assert (a.intentos_calificados, a.puntaje_promedio) == (2, D("3.00"))
    assert (d.aciertos, d.errores, d.sin_responder, d.porcentaje_aciertos) == (1, 0, 1, D("50.00"))
    assert (d.intentos_calificados, d.puntaje_promedio) == (1, D("5.00"))
    assert not v.evaluable
    # El puntaje es exactamente el de la calculadora del módulo 5.
    assert CalculadoraRubrica.puntuar(analisis, D("50"), D("5"))[1] == a.puntaje_promedio


def test_criterio_sin_intentos_considerados_no_tiene_porcentaje():
    analisis, *_ = _criterios()
    r = calc.estadisticas_criterios([analisis], D("5"), {analisis.id: 2}, [], 0)[0]
    assert (r.evaluable, r.porcentaje_aciertos, r.puntaje_promedio, r.sin_responder) == (True, None, None, 0)


def test_criterio_con_niveles_invalidos_no_inventa_puntaje():
    malo = CriterioEvaluable(uuid.uuid4(), "Mal configurado", D("100"), (Nivel("A", D("9"), D("0")),))
    fila = calc.FilaCriterioIntento(uuid.uuid4(), malo.id, 1, 1, 1, True)
    r = calc.estadisticas_criterios([malo], D("5"), {malo.id: 1}, [fila], 1)[0]
    assert r.puntaje_promedio is None and r.porcentaje_aciertos == D("100.00")
    assert r.advertencia.startswith("Puntaje no disponible")


def test_sin_escala_no_hay_puntaje():
    analisis, *_ = _criterios()
    fila = calc.FilaCriterioIntento(uuid.uuid4(), analisis.id, 2, 2, 2, True)
    assert calc.estadisticas_criterios([analisis], None, {analisis.id: 2}, [fila], 1)[0].puntaje_promedio is None


# --- Preguntas ---------------------------------------------------------------------------------------------------


def test_estadistica_de_pregunta():
    e = calc.estadistica_pregunta(intentos=4, respondidas=3, aciertos=2, corregible=True)
    assert (e.aciertos, e.errores, e.sin_responder, e.porcentaje_aciertos) == (2, 1, 1, D("50.00"))


def test_pregunta_sin_intentos_no_tiene_porcentaje():
    e = calc.estadistica_pregunta(intentos=0, respondidas=0, aciertos=0, corregible=True)
    assert (e.porcentaje_aciertos, e.sin_responder) == (None, 0)


def test_pregunta_sin_opcion_correcta_no_se_corrige():
    e = calc.estadistica_pregunta(intentos=2, respondidas=2, aciertos=0, corregible=False)
    assert (e.aciertos, e.errores, e.porcentaje_aciertos, e.corregible, e.sin_responder) == (None, None, None, False, 0)


def test_pregunta_con_conteos_incoherentes_falla():
    with pytest.raises(ValueError):
        calc.estadistica_pregunta(intentos=1, respondidas=2, aciertos=0, corregible=True)
    with pytest.raises(ValueError):
        calc.estadistica_pregunta(intentos=2, respondidas=1, aciertos=2, corregible=True)


# --- Filtros de fecha y parámetros ------------------------------------------------------------------------------


def test_validar_rango_de_fechas():
    calc.validar_rango(T8, T9)
    calc.validar_rango(None, T9)
    with pytest.raises(calc.RangoFechasInvalido):
        calc.validar_rango(T9, T8)
    with pytest.raises(calc.RangoFechasInvalido):
        calc.validar_rango(T9, T9)  # intervalo semiabierto vacío
    with pytest.raises(calc.RangoFechasInvalido):
        calc.validar_rango(datetime(2026, 11, 3, 8), None)


def test_filtros_normalizan_a_utc_y_validan_el_rango():
    f = s.FiltrosSesiones(desde="2026-11-03T03:00:00-05:00", hasta="2026-11-04T00:00:00Z")
    assert f.desde == T8 and f.desde.tzinfo == UTC
    with pytest.raises(ValidationError):
        s.FiltrosSesiones(desde="2026-11-04T00:00:00Z", hasta="2026-11-03T00:00:00Z")
    with pytest.raises(ValidationError):
        s.FiltrosSesiones(desde="2026-11-03T08:00:00")  # sin zona horaria


def test_filtros_rechazan_parametros_desconocidos_y_limites():
    with pytest.raises(ValidationError):
        s.FiltrosSesiones(docente_id=str(uuid.uuid4()))
    with pytest.raises(ValidationError):
        s.FiltrosEstudiantes(limit=101)
    with pytest.raises(ValidationError):
        s.FiltrosEstudiantes(skip=-1)
    with pytest.raises(ValidationError):
        s.ExportacionSesion(formato="xlsx")
    with pytest.raises(ValidationError):
        s.ExportacionSesion(tipo="codigos")
    assert s.FiltrosEstudiantes(buscar="  ana  ").buscar == "ana"


def test_filtro_de_sesiones_siempre_incluye_al_docente():
    docente = uuid.uuid4()
    sql = str(FiltroSesiones(docente).ids().compile())
    assert "sesion.docente_id" in sql
    completo = FiltroSesiones(docente, ES.EN_CURSO, uuid.uuid4(), uuid.uuid4(), T8, T10)
    assert len(completo.condiciones()) == 6
    sql = str(completo.ids().compile())
    assert "sesion.inicio >=" in sql and "sesion.inicio <" in sql


def test_busqueda_escapa_comodines():
    assert _patron("50%_a\\b") == "%50\\%\\_a\\\\b%"


# --- Exportación CSV ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("peligroso", ["=SUM(A1:A2)", "+1", "-1+2", "@cmd", "\t=1", "\r=1", "  =1", "＝1"])
def test_texto_seguro_neutraliza_formulas(peligroso):
    assert exporters.texto_seguro(peligroso) == "'" + peligroso


@pytest.mark.parametrize(
    "peligroso",
    [
        "\x00=1",  # NUL
        "\x0b=1",  # tabulador vertical
        "\x0c+1",  # avance de página
        "\x1f@x",  # separador de unidad
        " =1",  # espacio de no separación
        " -1",  # espacio eme
        "​=1",  # espacio de ancho cero (formato)
        "﻿=1",  # BOM dentro del valor
        "‮=1",  # marca de dirección (RLO)
        " \t  ​=HYPERLINK(\"x\")",  # secuencia mixta
        " =1",  # separador de línea
        "\x00\x00＠x",  # ancho completo tras controles
    ],
)
def test_texto_seguro_ignora_espacios_y_caracteres_invisibles_antes_de_la_formula(peligroso):
    assert exporters.texto_seguro(peligroso) == "'" + peligroso
    assert exporters.celda(peligroso) == "'" + peligroso


def test_texto_seguro_conserva_texto_normal():
    assert exporters.texto_seguro("Ana Pérez") == "Ana Pérez"
    assert exporters.texto_seguro("") == ""
    for normal in ("  Ana", " Ana", "\x00Ana", "Ana=1", "Ana - Pérez", "2026-2", "​"):
        assert exporters.texto_seguro(normal) == normal  # solo se marca si tras el prefijo invisible hay un indicador


def test_celdas_con_representacion_consistente():
    assert exporters.celda(None) == ""  # una nota nula no es 0
    assert exporters.celda(D("2.2")) == "2.20"
    assert exporters.celda(D("0")) == "0.00"
    assert exporters.celda(True) == "Sí" and exporters.celda(False) == "No"
    assert exporters.celda(7) == "7"
    assert exporters.celda(datetime(2026, 11, 3, 3, 0, tzinfo=timezone(timedelta(hours=-5)))) == "2026-11-03T08:00:00Z"
    assert exporters.celda(EP.EXPIRADA) == "EXPIRADA"
    u = uuid.uuid4()
    assert exporters.celda(u) == str(u)
    assert exporters.celda("=1") == "'=1"
    with pytest.raises(ValueError):
        exporters.celda(datetime(2026, 11, 3, 8))


def test_construir_csv_utf8_con_bom_comillas_y_crlf():
    contenido = exporters.construir_csv(["Nombre", "Nota"], [["José \"Pepe\", Ñ", D("3.5")], ["=HYPERLINK(\"x\")", None]])
    assert contenido.startswith(b"\xef\xbb\xbf")
    texto = contenido.decode("utf-8-sig")
    assert "\r\n" in texto
    filas = list(csv.reader(io.StringIO(texto, newline="")))
    assert filas == [["Nombre", "Nota"], ['José "Pepe", Ñ', "3.50"], ["'=HYPERLINK(\"x\")", ""]]


def test_construir_csv_vacio_solo_encabezados():
    filas = list(csv.reader(io.StringIO(exporters.construir_csv(["A"], []).decode("utf-8-sig"))))
    assert filas == [["A"]]


def test_construir_csv_limita_las_filas():
    with pytest.raises(exporters.ExportacionExcedeLimiteError) as exc:
        exporters.construir_csv(["A"], ([i] for i in itertools.count()), limite=3)
    assert exc.value.status_code == 422 and exc.value.extra["codigo"] == "EXPORTACION_EXCEDE_LIMITE"
    assert len(exporters.construir_csv(["A"], [[1], [2], [3]], limite=3).splitlines()) == 4


def test_construir_csv_rechaza_filas_incompletas():
    with pytest.raises(ValueError):
        exporters.construir_csv(["A", "B"], [[1]])


def test_nombre_de_archivo_seguro():
    nombre = exporters.nombre_archivo("sesión/../x", uuid.UUID("12345678-1234-5678-1234-567812345678"), "Resumen\";rm", T8)
    assert nombre == "reporte_sesinx_resumenrm_12345678_20261103.csv"
    assert all(c.isalnum() or c in "_.-" for c in nombre)
    cabeceras = exporters.cabeceras_descarga(nombre)
    assert cabeceras["Content-Disposition"] == f'attachment; filename="{nombre}"'
    assert cabeceras["Cache-Control"] == "no-store" and cabeceras["X-Content-Type-Options"] == "nosniff"


# --- Servicios con repositorio simulado ------------------------------------------------------------------------------


class RelojFijo:
    def ahora(self):
        return T9


def _fila_sesion(estado=ES.EN_CURSO, escala=D("5.00")):
    return SimpleNamespace(
        id=uuid.uuid4(), estado=estado, inicio=T8, fin=T10, tiempo_max_min=40, caso_id=uuid.uuid4(), caso_nombre="Caso",
        caso_estado=EstadoCasoEnum.PUBLICADO, espacio_id=uuid.uuid4(), espacio_nombre="Espacio", espacio_periodo="2026-2",
        docente_id=uuid.uuid4(), docente_nombre="Docente", escala_max=escala,
    )


def _servicio(clase, **repo):
    servicio = clase(sesion_bd(), RelojFijo())
    servicio._repo = MagicMock(**repo)
    return servicio


@pytest.mark.parametrize(("estado", "ausentes", "pendientes"), [(ES.EN_CURSO, 0, 2), (ES.SIN_INICIAR, 0, 2), (ES.FINALIZADO, 2, 0)])
def test_resumen_solo_declara_ausencias_con_la_sesion_finalizada(estado, ausentes, pendientes):
    fila = _fila_sesion(estado)
    servicio = _servicio(ReportesSesionService)
    servicio._repo.sesion.return_value = fila
    servicio._repo.conteos_convocatorias.return_value = {fila.id: calc.ConteosConvocatorias(activas=3, revocadas=1, activas_con_intento=1)}
    servicio._repo.conteos_intentos.return_value = {}

    r = servicio.resumen(fila.id, fila.docente_id)

    assert (r.convocatorias.ausentes, r.convocatorias.pendientes, r.convocatorias.revocadas) == (ausentes, pendientes, 1)
    assert r.intentos.total == 0 and r.indicadores.tasa_finalizacion.porcentaje is None
    assert r.sesion.limite_ingreso == T9 and r.generado_en == T9
    servicio._repo.iniciar_lectura.assert_called_once()
    servicio._repo.terminar_lectura.assert_called_once()


def test_sesion_ajena_o_inexistente_responde_404_y_cierra_la_lectura():
    servicio = _servicio(ReportesSesionService)
    servicio._repo.sesion.return_value = None
    with pytest.raises(NotFoundError):
        servicio.resumen(uuid.uuid4(), uuid.uuid4())
    servicio._repo.terminar_lectura.assert_called_once()


def test_estudiantes_arma_la_pagina_con_una_sola_consulta_de_intentos():
    fila = _fila_sesion(ES.FINALIZADO)
    conv_a, conv_b = uuid.uuid4(), uuid.uuid4()
    estudiantes = [
        SimpleNamespace(convocatoria_id=conv_a, revocada_en=None, intentos_autorizados=2, estudiante_id=uuid.uuid4(), nombre_completo="A",
                        correo="a@u.edu.co", codigo_institucional=None, intentos=2, calificados=1, activo=False),
        SimpleNamespace(convocatoria_id=conv_b, revocada_en=None, intentos_autorizados=1, estudiante_id=uuid.uuid4(), nombre_completo="B",
                        correo="b@u.edu.co", codigo_institucional="2026", intentos=0, calificados=0, activo=None),
    ]
    intentos = [
        SimpleNamespace(id=uuid.uuid4(), convocatoria_id=conv_a, numero_intento=n, estado=EP.FINALIZADA, motivo_cierre=MC.VOLUNTARIO,
                        nota_final=nota, respondidas=1)
        for n, nota in ((1, D("2.2")), (2, None))
    ]
    servicio = _servicio(ReportesSesionService)
    servicio._repo.sesion.return_value = fila
    servicio._repo.pagina_estudiantes.return_value = estudiantes
    servicio._repo.contar_estudiantes.return_value = 2
    servicio._repo.intentos_breves.return_value = intentos

    r = servicio.estudiantes(fila.id, fila.docente_id, FiltroEstudiantes(), skip=0, limit=20)

    servicio._repo.intentos_breves.assert_called_once_with([conv_a, conv_b])
    a, b = r.items
    assert [i.nota_final for i in a.intentos] == [D("2.20"), None]
    assert [i.situacion for i in a.intentos] == [SituacionIntento.CALIFICADO, SituacionIntento.PENDIENTE_CALIFICACION]
    assert (a.condicion, b.condicion, b.intento_activo, b.intentos) == (CondicionConvocado.PARTICIPO, CondicionConvocado.AUSENTE, False, [])
    assert "codigo_autorizacion" not in r.model_dump_json()


def test_desempeno_de_estudiante_no_convocado_responde_404():
    servicio = _servicio(ReportesSesionService)
    servicio._repo.sesion.return_value = _fila_sesion()
    servicio._repo.convocatoria_de_estudiante.return_value = None
    with pytest.raises(NotFoundError):
        servicio.desempeno_estudiante(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())


def _intento(estado, motivo=None, fin=None, respondidas=2, aciertos=1, nota=None):
    return SimpleNamespace(
        id=uuid.uuid4(), numero_intento=1, inicio=T8, fin=fin, estado=estado, motivo_cierre=motivo, nota_final=nota,
        convocatoria_id=uuid.uuid4(), estudiante_id=uuid.uuid4(), respondidas=respondidas, aciertos=aciertos,
    )


def test_intento_en_progreso_no_expone_aciertos():
    d = intento_detalle(_intento(EP.EN_PROGRESO), uuid.uuid4(), 3, D("5"))
    assert (d.aciertos, d.errores, d.preguntas_respondidas, d.preguntas_sin_responder, d.condicion) == (None, None, 2, 1, None)
    assert d.situacion == SituacionIntento.EN_PROGRESO and d.duracion_segundos is None


def test_intento_cerrado_con_condicion_del_modulo_5():
    d = intento_detalle(_intento(EP.EXPIRADA, MC.TIEMPO_AGOTADO, T8 + timedelta(minutes=40), nota=D("1")), uuid.uuid4(), 3, D("5"))
    assert (d.aciertos, d.errores, d.duracion_segundos, d.nota_final) == (1, 1, 2400, D("1.00"))
    assert d.condicion == CondicionAcademica.INCOMPLETA
    assert condicion_academica(_intento(EP.FINALIZADA, MC.VOLUNTARIO, T9), uuid.uuid4()) == CondicionAcademica.COMPLETA


def test_notas_separan_finalizados_y_expirados():
    fila = _fila_sesion()
    servicio = _servicio(ReportesSesionService)
    servicio._repo.sesion.return_value = fila
    finalizados = calc.agregar_notas([D("4.00"), D("3.00")], D("5.00"))
    expirados = calc.agregar_notas([D("2.00")], D("5.00"))
    total = calc.agregar_notas([D("4.00"), D("2.00"), D("3.00")], D("5.00"))
    servicio._repo.agregado_notas.side_effect = lambda _s, _e, por_estado=False: (
        {EP.FINALIZADA: finalizados, EP.EXPIRADA: expirados} if por_estado else {None: total}
    )
    servicio._repo.conteos_intentos.return_value = {fila.id: calc.ConteosIntentos(finalizados=2, expirados=2, calificados=3)}
    servicio._repo.estudiantes_con_nota.return_value = 2

    r = servicio.notas(fila.id, fila.docente_id)

    assert (r.intentos_cerrados, r.intentos_sin_nota, r.estudiantes_con_nota) == (4, 1, 2)
    assert (r.estadisticas.evaluados, r.estadisticas.promedio) == (3, D("3.00"))
    assert (r.por_estado.finalizados.promedio, r.por_estado.expirados.promedio) == (D("3.50"), D("2.00"))
    assert r.estadisticas.unidad == "intento"


def test_espacio_inactivo_sin_sesiones_del_docente_responde_404():
    servicio = _servicio(ReportesAcademicosService)
    servicio._repo.espacio.return_value = SimpleNamespace(id=uuid.uuid4(), nombre="E", periodo="2026-1", activo=False)
    servicio._repo.docente_tiene_sesiones_en_espacio.return_value = False
    with pytest.raises(NotFoundError):
        servicio.espacio(uuid.uuid4(), FiltroSesiones(uuid.uuid4()), skip=0, limit=20)
    servicio._repo.espacio.return_value = None
    with pytest.raises(NotFoundError):
        servicio.espacio(uuid.uuid4(), FiltroSesiones(uuid.uuid4()), skip=0, limit=20)


def test_caso_de_otro_autor_responde_404():
    servicio = _servicio(ReportesAcademicosService)
    servicio._repo.caso_del_autor.return_value = None
    with pytest.raises(NotFoundError):
        servicio.caso(uuid.uuid4(), FiltroSesiones(uuid.uuid4()), skip=0, limit=20)


def test_exportacion_detecta_el_limite_sin_leer_el_resto():
    fila = _fila_sesion()
    servicio = ExportacionService(sesion_bd(), RelojFijo(), limite=2)
    servicio._repo = MagicMock()
    servicio._repo.sesion.return_value = fila
    servicio._repo.estudiantes_para_exportar.return_value = [object()] * 3
    with pytest.raises(exporters.ExportacionExcedeLimiteError):
        servicio.exportar_sesion(fila.id, fila.docente_id, "estudiantes", FiltroEstudiantes())
    assert servicio._repo.estudiantes_para_exportar.call_args.args[-1] == 3  # pide limite + 1
    servicio._repo.terminar_lectura.assert_called()


def test_repositorio_abre_una_transaccion_de_solo_lectura_repeatable_read():
    session = sesion_bd()
    repo = ReportesRepository(session)
    repo.iniciar_lectura()
    session.commit.assert_called_once()
    sentencia = str(session.execute.call_args.args[0])
    assert "REPEATABLE READ" in sentencia and "READ ONLY" in sentencia
    repo.terminar_lectura()
    session.rollback.assert_called_once()


def test_conteos_con_lista_vacia_no_consultan():
    session = sesion_bd()
    repo = ReportesRepository(session)
    assert repo.conteos_convocatorias([]) == {} and repo.conteos_intentos([], T8) == {} and repo.intentos_breves([]) == []
    session.execute.assert_not_called()


def test_conversiones_de_presentacion():
    e = estadisticas(calc.estadisticas_notas([D("4.444")], D("5")))
    assert e.minimo == D("4.44") and e.escala_max == D("5.00")
    assert por_estado({ES.EN_CURSO: 2}).model_dump() == {"sin_iniciar": 0, "en_curso": 2, "finalizadas": 0}
    assert issubclass(ReportesSesionService, ServicioReportesBase)


def test_esquemas_no_declaran_datos_secretos():
    prohibidos = {"codigo_autorizacion", "codigo", "clave", "clave_hash", "version_token", "access_token", "token"}
    for nombre in dir(s):
        modelo = getattr(s, nombre)
        if isinstance(modelo, type) and issubclass(modelo, s.BaseModel):
            assert not prohibidos & set(modelo.model_fields), nombre
