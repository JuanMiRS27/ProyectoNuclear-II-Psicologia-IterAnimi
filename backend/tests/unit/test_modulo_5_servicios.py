"""Módulo 5: orquestación de los servicios de evaluación y consulta de resultados (unitarias).

Complementa `test_modulo_5.py`, que prueba la Strategy y la calculadora de rúbrica. Aquí se
verifica cómo los servicios las coordinan: autorización, transacción única, eventos al outbox
antes del commit, publicación después, y qué ve cada actor. Repositorios y consultas del
módulo 4 son dobles; las estrategias y la calculadora son las reales.
"""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.core import outbox
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.modules.evaluations import eventos
from app.modules.evaluations.dependencies import acceso_resultados_actual
from app.modules.evaluations.dominio import (
    CondicionAcademica,
    CriterioEvaluable,
    EstadoCalificacion,
    EvaluacionNoPosibleError,
    OpcionEvaluable,
    PreguntaEvaluable,
    RubricaEvaluable,
    SituacionAcademica,
)
from app.modules.evaluations.schemas import ResultadoEstudianteDetalle
from app.modules.evaluations.services import consulta_resultados_service as consulta_mod
from app.modules.evaluations.services import evaluacion_service as servicio_mod
from app.modules.evaluations.services.consulta_resultados_service import ConsultaResultadosService
from app.modules.evaluations.services.evaluacion_service import EvaluacionCalculada, EvaluacionService
from app.modules.evaluations.strategies import ContextoEvaluacion
from app.modules.participations.models import EstadoParticipacionEnum, MotivoCierreEnum, Participacion
from app.modules.sessions.models import EstadoSesionEnum
from tests.unit.fabricas import convocatoria, sesion, sesion_bd, usuario

FIN = EstadoParticipacionEnum.FINALIZADA
EXP = EstadoParticipacionEnum.EXPIRADA
PROG = EstadoParticipacionEnum.EN_PROGRESO
CRITERIO = uuid.uuid4()
CORRECTA, INCORRECTA = uuid.uuid4(), uuid.uuid4()
PREGUNTA = PreguntaEvaluable(
    uuid.uuid4(),
    "¿Qué fenómeno se observa?",
    CRITERIO,
    (OpcionEvaluable(CORRECTA, "Conformidad", True, "Presión del grupo."), OpcionEvaluable(INCORRECTA, "Azar", False, "No explica.")),
    escenario="Primera votación",
)
RUBRICA = RubricaEvaluable(Decimal("5.00"), (CriterioEvaluable(CRITERIO, "Análisis", Decimal("100"), ()),))


def situacion(participacion_id=None, *, estado=FIN, motivo=MotivoCierreEnum.VOLUNTARIO, acierta=True, ausente=False):
    """Una pregunta, rúbrica lineal: acertar da 5.00 y fallar 0.00."""
    if ausente:
        return SituacionAcademica(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), RUBRICA, (PREGUNTA,))
    return SituacionAcademica(
        estudiante_id=uuid.uuid4(),
        convocatoria_id=uuid.uuid4(),
        sesion_id=uuid.uuid4(),
        rubrica=RUBRICA,
        preguntas=(PREGUNTA,),
        participacion_id=participacion_id or uuid.uuid4(),
        numero_intento=1,
        estado=estado,
        motivo_cierre=motivo,
        respuestas={PREGUNTA.id: CORRECTA if acierta else INCORRECTA},
    )


def participacion(estado=FIN, nota=None, retro=None, motivo=MotivoCierreEnum.VOLUNTARIO, conv=None):
    conv = conv or convocatoria()
    p = Participacion(
        id=uuid.uuid4(),
        convocatoria_id=conv.id,
        numero_intento=1,
        estado=estado,
        motivo_cierre=None if estado == PROG else motivo,
        nota_final=nota,
        retroalimentacion_general=retro,
    )
    p.convocatoria = conv
    return p


@pytest.fixture
def registro(monkeypatch):
    """Outbox simulado: registra lo que la transacción guardaría junto con la nota."""
    doble = MagicMock()
    monkeypatch.setattr(outbox, "registro", lambda: doble)
    return doble


@pytest.fixture
def evaluador(monkeypatch, registro):
    """EvaluacionService con repositorio y consulta del módulo 4 simulados.

    `situaciones[participacion_id]` define lo que el módulo 4 entregaría para cada intento.
    """
    servicio = EvaluacionService(sesion_bd(), eventos_publicador=MagicMock())
    servicio._repo = MagicMock()
    servicio._consulta = MagicMock()
    servicio._consulta.ausencias.return_value = []
    servicio._repo.participaciones_de_sesion.return_value = []
    servicio.situaciones = {}
    servicio._consulta.obtener.side_effect = lambda pid: servicio.situaciones[pid]
    monkeypatch.setattr(servicio_mod.mapeo, "situacion_de_participacion", lambda datos: datos)
    return servicio


def _sesion_finalizada(estado=EstadoSesionEnum.FINALIZADO):
    return SimpleNamespace(id=uuid.uuid4(), estado=estado, docente_id=uuid.uuid4())


# --- Evaluación sin escritura ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "motivo", "acierta", "condicion", "nota"),
    [
        (FIN, MotivoCierreEnum.VOLUNTARIO, True, CondicionAcademica.COMPLETA, Decimal("5.00")),
        (FIN, MotivoCierreEnum.VOLUNTARIO, False, CondicionAcademica.COMPLETA, Decimal("0.00")),
        (EXP, MotivoCierreEnum.TIEMPO_AGOTADO, True, CondicionAcademica.INCOMPLETA, Decimal("5.00")),
    ],
)
def test_evaluar_elige_la_estrategia_y_no_escribe(evaluador, estado, motivo, acierta, condicion, nota):
    pid = uuid.uuid4()
    evaluador.situaciones[pid] = situacion(pid, estado=estado, motivo=motivo, acierta=acierta)

    calculada = evaluador.evaluar(pid)

    assert (calculada.resultado.condicion, calculada.resultado.nota) == (condicion, nota)
    assert calculada.situacion is evaluador.situaciones[pid]
    evaluador._repo.registrar_nota.assert_not_called()
    evaluador._session.commit.assert_not_called()


def test_evaluar_ausencias_reutiliza_la_consulta_del_modulo_4(evaluador, monkeypatch):
    conv = convocatoria()
    evaluador._consulta.ausencias.return_value = [conv]
    monkeypatch.setattr(servicio_mod.mapeo, "situacion_de_ausencia", lambda c, sid: situacion(ausente=True))
    actual = sesion()

    resultados = evaluador.evaluar_ausencias(actual)

    evaluador._consulta.ausencias.assert_called_once_with(actual.id)
    assert [(r.condicion, r.calificacion, r.nota) for r in resultados] == [
        (CondicionAcademica.AUSENCIA, EstadoCalificacion.SIN_CALIFICAR, None)
    ]


# --- Procesamiento de una sesión -----------------------------------------------------------------


def _preparar_sesion(evaluador, estado_sesion=EstadoSesionEnum.FINALIZADO, notas=(None, None)):
    ses = _sesion_finalizada(estado_sesion)
    evaluador._repo.sesion_del_docente.return_value = ses
    cerradas = [participacion(nota=n) for n in notas]
    for p in cerradas:
        evaluador.situaciones[p.id] = situacion(p.id)
    evaluador._repo.bloquear_cerradas_de_sesion.return_value = cerradas
    return ses, cerradas


def test_procesar_sesion_registra_notas_en_una_sola_transaccion(evaluador, registro):
    ses, cerradas = _preparar_sesion(evaluador)
    evaluador._repo.participaciones_de_sesion.return_value = [*cerradas, participacion(PROG)]
    evaluador._consulta.ausencias.return_value = [convocatoria()]
    docente = usuario(id=ses.docente_id)

    resumen = evaluador.procesar_sesion(ses.id, docente)

    assert (resumen.registradas, resumen.actualizadas, resumen.sin_cambios) == (2, 0, 0)
    assert (resumen.en_progreso, resumen.ausencias, resumen.procesadas) == (1, 1, 2)
    evaluador._repo.sesion_del_docente.assert_called_once_with(ses.id, docente.id, bloquear=True)
    assert [c.args[1] for c in evaluador._repo.registrar_nota.call_args_list] == [Decimal("5.00")] * 2
    evaluador._session.commit.assert_called_once()


def test_eventos_van_al_outbox_antes_del_commit_y_se_publican_despues(evaluador, registro):
    ses, _ = _preparar_sesion(evaluador)
    orden = MagicMock()
    orden.attach_mock(registro.registrar, "outbox")
    orden.attach_mock(evaluador._session.commit, "commit")
    orden.attach_mock(evaluador._eventos.publicar, "publicar")

    evaluador.procesar_sesion(ses.id, usuario(id=ses.docente_id))

    nombres = [c[0] for c in orden.mock_calls]
    assert nombres == ["outbox"] * 3 + ["commit"] + ["publicar"] * 3
    tipos = [c.args[1] for c in registro.registrar.call_args_list]
    assert tipos == [eventos.CALIFICACION_REGISTRADA, eventos.CALIFICACION_REGISTRADA, eventos.RESULTADOS_DISPONIBLES]
    assert all("nota" not in c.args[3] for c in registro.registrar.call_args_list)  # los eventos no llevan la nota


@pytest.mark.parametrize("estado_sesion", [EstadoSesionEnum.EN_CURSO, EstadoSesionEnum.SIN_INICIAR])
def test_resultados_disponibles_solo_con_la_sesion_finalizada(evaluador, registro, estado_sesion):
    ses, _ = _preparar_sesion(evaluador, estado_sesion)

    evaluador.procesar_sesion(ses.id, usuario(id=ses.docente_id))

    tipos = [c.args[1] for c in registro.registrar.call_args_list]
    assert eventos.RESULTADOS_DISPONIBLES not in tipos
    assert tipos.count(eventos.CALIFICACION_REGISTRADA) == 2


def test_reprocesar_sin_cambios_no_escribe_ni_publica(evaluador, registro):
    ses, _ = _preparar_sesion(evaluador, notas=(Decimal("5.00"), Decimal("5.00")))

    resumen = evaluador.procesar_sesion(ses.id, usuario(id=ses.docente_id))

    assert resumen.sin_cambios == 2
    evaluador._repo.registrar_nota.assert_not_called()
    registro.registrar.assert_not_called()
    evaluador._eventos.publicar.assert_not_called()


def test_un_intento_no_evaluable_revierte_toda_la_sesion(evaluador, registro):
    ses, cerradas = _preparar_sesion(evaluador)
    fallida = cerradas[1].id

    def obtener(pid):
        if pid == fallida:
            raise EvaluacionNoPosibleError("RUBRICA_NO_EVALUABLE", "Sin criterios.")
        return evaluador.situaciones[pid]

    evaluador._consulta.obtener.side_effect = obtener

    with pytest.raises(EvaluacionNoPosibleError) as error:
        evaluador.procesar_sesion(ses.id, usuario(id=ses.docente_id))

    assert error.value.extra["participacion_id"] == str(fallida)
    evaluador._session.rollback.assert_called_once()
    evaluador._session.commit.assert_not_called()
    registro.registrar.assert_not_called()
    evaluador._eventos.publicar.assert_not_called()
    assert evaluador._pendientes == []


def test_sesion_ajena_responde_404_y_revierte(evaluador):
    evaluador._repo.sesion_del_docente.return_value = None

    with pytest.raises(NotFoundError):
        evaluador.procesar_sesion(uuid.uuid4(), usuario())

    evaluador._session.rollback.assert_called_once()
    evaluador._repo.bloquear_cerradas_de_sesion.assert_not_called()


# --- Recálculo y retroalimentación ---------------------------------------------------------------


def _preparar_intento(evaluador, p):
    ses = _sesion_finalizada()
    evaluador._repo.participacion_con_sesion.return_value = (p, ses)
    evaluador._repo.sesion_del_docente.return_value = ses
    evaluador._repo.bloquear_participacion.return_value = p
    evaluador.situaciones[p.id] = situacion(p.id)
    return ses


def test_recalcular_bloquea_sesion_antes_que_participacion_y_actualiza(evaluador, registro):
    p = participacion(nota=Decimal("2.00"))
    ses = _preparar_intento(evaluador, p)
    orden = MagicMock()
    orden.attach_mock(evaluador._repo.sesion_del_docente, "sesion")
    orden.attach_mock(evaluador._repo.bloquear_participacion, "participacion")

    calculada = evaluador.recalcular(p.id, usuario(id=ses.docente_id))

    assert calculada.resultado.nota == Decimal("5.00")
    assert [c[0] for c in orden.mock_calls] == ["sesion", "participacion"]
    assert registro.registrar.call_args.args[1] == eventos.CALIFICACION_ACTUALIZADA


def test_recalcular_intento_en_progreso_es_conflicto(evaluador):
    p = participacion(PROG)
    ses = _preparar_intento(evaluador, p)

    with pytest.raises(ConflictError):
        evaluador.recalcular(p.id, usuario(id=ses.docente_id))

    evaluador._repo.registrar_nota.assert_not_called()


def test_recalcular_intento_que_desaparecio_tras_el_bloqueo(evaluador):
    p = participacion()
    ses = _preparar_intento(evaluador, p)
    evaluador._repo.bloquear_participacion.return_value = None

    with pytest.raises(NotFoundError):
        evaluador.recalcular(p.id, usuario(id=ses.docente_id))


@pytest.mark.parametrize(("anterior", "nueva", "evento"), [(None, "Buen análisis.", True), ("Igual.", "Igual.", False), ("Texto.", None, True)])
def test_retroalimentacion_solo_registra_y_avisa_si_cambia(evaluador, registro, anterior, nueva, evento):
    p = participacion(retro=anterior)
    ses = _preparar_intento(evaluador, p)

    evaluador.actualizar_retroalimentacion(p.id, usuario(id=ses.docente_id), nueva)

    assert evaluador._repo.registrar_retroalimentacion.called is evento
    tipos = [c.args[1] for c in registro.registrar.call_args_list]
    assert tipos == ([eventos.RETROALIMENTACION_REGISTRADA] if evento else [])
    if evento:
        assert registro.registrar.call_args.args[3] == {"participacion_id": str(p.id), "convocatoria_id": str(p.convocatoria_id)}


def test_retroalimentacion_de_otro_docente_es_404(evaluador):
    p = participacion()
    _preparar_intento(evaluador, p)

    with pytest.raises(NotFoundError):
        evaluador.actualizar_retroalimentacion(p.id, usuario(), "Texto")

    evaluador._repo.registrar_retroalimentacion.assert_not_called()


# --- Consulta de resultados ----------------------------------------------------------------------


def _calculada(p, *, acierta=True, estado=FIN, motivo=MotivoCierreEnum.VOLUNTARIO):
    sit = situacion(p.id, estado=estado, motivo=motivo, acierta=acierta)
    return EvaluacionCalculada(sit, ContextoEvaluacion.para(sit).evaluar(sit))


@pytest.fixture
def consulta():
    evaluacion = MagicMock()
    servicio = ConsultaResultadosService(sesion_bd(), evaluacion=evaluacion)
    servicio._repo = MagicMock()
    servicio._consulta = MagicMock()
    servicio._consulta.ausencias.return_value = []
    evaluacion.evaluar_ausencias.return_value = []
    return servicio


def _sesion_con_caso(estado=EstadoSesionEnum.FINALIZADO):
    return SimpleNamespace(
        id=uuid.uuid4(),
        estado=estado,
        caso=SimpleNamespace(nombre="Conformidad", rubrica=SimpleNamespace(escala_max=Decimal("5"))),
        espacio_academico=SimpleNamespace(nombre="Psicología Social", periodo="2026-2"),
    )


def test_resultados_de_sesion_distinguen_evaluadas_pendientes_y_en_progreso(consulta):
    al_dia = participacion(nota=Decimal("5.00"))
    pendiente = participacion(EXP, motivo=MotivoCierreEnum.TIEMPO_AGOTADO)
    abierta = participacion(PROG)
    consulta._evaluacion.sesion_autorizada.return_value = _sesion_con_caso()
    consulta._repo.participaciones_de_sesion.return_value = [al_dia, pendiente, abierta]
    calculadas = {
        al_dia.id: _calculada(al_dia),
        pendiente.id: _calculada(pendiente, estado=EXP, motivo=MotivoCierreEnum.TIEMPO_AGOTADO),
    }
    consulta._evaluacion.evaluar.side_effect = lambda pid: calculadas[pid]

    resultado = consulta.resultados_sesion(uuid.uuid4(), usuario())

    r = resultado.resumen
    assert (r.finalizadas, r.expiradas, r.en_progreso, r.evaluadas, r.pendientes) == (1, 1, 1, 1, 1)
    filas = {f.participacion_id: f for f in resultado.participaciones}
    assert (filas[al_dia.id].evaluacion_registrada, filas[al_dia.id].requiere_procesamiento) == (True, False)
    assert (filas[pendiente.id].evaluacion_registrada, filas[pendiente.id].requiere_procesamiento) == (False, True)
    assert (filas[abierta.id].condicion, filas[abierta.id].requiere_procesamiento) == (None, False)
    assert resultado.escala_max == Decimal("5.00")
    assert abierta.id not in [c.args[0] for c in consulta._evaluacion.evaluar.call_args_list]


def test_rubrica_no_evaluable_se_muestra_como_pendiente_sin_fallar(consulta):
    p = participacion(nota=None)
    consulta._evaluacion.sesion_autorizada.return_value = _sesion_con_caso()
    consulta._repo.participaciones_de_sesion.return_value = [p]
    consulta._evaluacion.evaluar.side_effect = EvaluacionNoPosibleError("RUBRICA_NO_EVALUABLE", "Sin criterios.")

    fila = consulta.resultados_sesion(uuid.uuid4(), usuario()).participaciones[0]

    assert (fila.condicion, fila.calificacion, fila.requiere_procesamiento) == (CondicionAcademica.COMPLETA, None, True)


def test_ausencias_se_ordenan_y_muestran_datos_del_estudiante(consulta):
    convs = [convocatoria(), convocatoria()]
    consulta._consulta.ausencias.return_value = convs
    resultados = []
    for c in convs:
        sit = SituacionAcademica(c.estudiante_id, c.id, uuid.uuid4(), RUBRICA, (PREGUNTA,))
        resultados.append(ContextoEvaluacion.para(sit).evaluar(sit))
    consulta._evaluacion.evaluar_ausencias.return_value = resultados[::-1]

    ausencias = consulta.ausencias(uuid.uuid4(), usuario())

    assert [str(a.estudiante_id) for a in ausencias] == sorted(str(c.estudiante_id) for c in convs)
    assert {a.estudiante_correo for a in ausencias} == {c.estudiante.correo for c in convs}


def test_detalle_docente_de_intento_en_progreso_es_conflicto(consulta):
    consulta._evaluacion.participacion_autorizada.return_value = (participacion(PROG), MagicMock())

    with pytest.raises(ConflictError):
        consulta.detalle_docente(uuid.uuid4(), usuario())

    consulta._evaluacion.evaluar.assert_not_called()


def test_detalle_docente_marca_la_incoherencia_entre_nota_registrada_y_calculada(consulta):
    p = participacion(nota=Decimal("3.00"))
    consulta._evaluacion.participacion_autorizada.return_value = (p, MagicMock())
    consulta._evaluacion.evaluar.return_value = _calculada(p)

    detalle = consulta.detalle_docente(p.id, usuario())

    assert (detalle.nota_final, detalle.nota_calculada, detalle.evaluacion_registrada) == (
        Decimal("3.00"),
        Decimal("5.00"),
        False,
    )
    assert detalle.estrategia == "EstrategiaEvaluacionCompleta"


def _acceso(conv):
    return SimpleNamespace(convocatoria=conv, sesion=_sesion_con_caso())


def test_estudiante_solo_ve_la_nota_si_la_evaluacion_esta_resuelta(consulta):
    conv = convocatoria()
    resuelta = participacion(nota=Decimal("5.00"), conv=conv)
    incoherente = participacion(nota=Decimal("1.00"), conv=conv)
    consulta._repo.de_convocatoria.return_value = [resuelta, incoherente]
    consulta._evaluacion.evaluar.side_effect = lambda pid: _calculada(resuelta if pid == resuelta.id else incoherente)

    vista = consulta.resultados_estudiante(_acceso(conv))
    # El estudiante ve el aula de su sesión solo por nombre y periodo.
    assert vista.espacio_academico.model_dump() == {"nombre": "Psicología Social", "periodo": "2026-2"}
    filas = {f.participacion_id: f for f in vista.resultados}

    assert (filas[resuelta.id].disponible, filas[resuelta.id].nota_final) == (True, Decimal("5.00"))
    assert (filas[incoherente.id].disponible, filas[incoherente.id].nota_final, filas[incoherente.id].calificacion) == (
        False,
        None,
        None,
    )


def test_detalle_estudiante_de_intento_ajeno_es_404(consulta):
    conv = convocatoria()
    consulta._repo.de_convocatoria.return_value = [participacion(conv=conv)]

    with pytest.raises(NotFoundError):
        consulta.detalle_estudiante(_acceso(conv), uuid.uuid4())


def test_detalle_estudiante_pendiente_de_evaluacion_es_conflicto(consulta):
    conv = convocatoria()
    p = participacion(nota=None, conv=conv)
    consulta._repo.de_convocatoria.return_value = [p]
    consulta._evaluacion.evaluar.return_value = _calculada(p)

    with pytest.raises(ConflictError, match="aún no está registrada"):
        consulta.detalle_estudiante(_acceso(conv), p.id)


def test_detalle_estudiante_omite_datos_internos_del_docente(consulta):
    conv = convocatoria()
    p = participacion(nota=Decimal("5.00"), conv=conv, retro="Buen trabajo.")
    consulta._repo.de_convocatoria.return_value = [p]
    consulta._evaluacion.evaluar.return_value = _calculada(p)

    detalle = consulta.detalle_estudiante(_acceso(conv), p.id)

    assert isinstance(detalle, ResultadoEstudianteDetalle)
    campos = set(detalle.model_dump())
    assert not campos & {"estrategia", "nota_calculada", "evaluacion_registrada", "estudiante_id", "convocatoria_id"}
    assert detalle.retroalimentacion_general == "Buen trabajo."
    assert detalle.preguntas[0].opciones_correctas[0].id == CORRECTA  # visible solo con la sesión cerrada y la nota resuelta


@pytest.mark.parametrize(
    "credenciales", [None, HTTPAuthorizationCredentials(scheme="Basic", credentials="x")], ids=["sin-cabecera", "basic"]
)
def test_rutas_de_resultados_exigen_bearer(credenciales):
    servicio = MagicMock()

    with pytest.raises(AuthenticationError):
        acceso_resultados_actual(credenciales, servicio)

    servicio.resolver_resultados.assert_not_called()


def test_redondeo_de_presentacion():
    assert consulta_mod.dos_decimales(Decimal("2.345")) == Decimal("2.35")
    assert consulta_mod.dos_decimales(None) is None


def test_consulta_usa_por_defecto_el_servicio_de_evaluacion():
    servicio = ConsultaResultadosService(sesion_bd())

    assert isinstance(servicio._evaluacion, EvaluacionService)
