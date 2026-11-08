"""Regresión: el módulo 6 se integra sin alterar el comportamiento de los módulos 1 a 5."""

import uuid
from unittest.mock import MagicMock

from alembic import command
from sqlalchemy import inspect, text

from app.core import outbox
from app.core.database import engine
from app.modules.sessions.eventos import EventoSesion
from tests.conftest import alembic_config
from tests.participations_helpers import PART_URL, contar, entorno, fila, guardar  # noqa: F401

TABLAS_MODULO_6 = ("evento_outbox", "notificacion", "entrega_correo")


def test_migracion_0011_reversible_sin_tocar_datos_academicos(entorno):
    """Bajar a 0010 elimina solo lo del módulo 6; las convocatorias y sesiones se conservan."""
    convocatorias = contar("SELECT count(*) FROM convocatoria")
    config = alembic_config()
    engine.dispose()
    command.downgrade(config, "0010_evaluacion_tras_cierre")
    try:
        inspector = inspect(engine)
        assert not any(inspector.has_table(t) for t in TABLAS_MODULO_6)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT to_regtype('estado_entrega_correo')")).scalar() is None
        assert contar("SELECT count(*) FROM convocatoria") == convocatorias
    finally:
        command.upgrade(config, "head")
    assert all(inspect(engine).has_table(t) for t in TABLAS_MODULO_6)
    assert contar("SELECT count(*) FROM convocatoria") == convocatorias


def test_el_publicador_posterior_al_commit_del_modulo_3_sigue_funcionando():
    """El outbox se suma al puerto existente; no lo reemplaza."""
    from app.modules.sessions.services.base import ServicioSesionesBase

    sesion_bd, publicador = MagicMock(), MagicMock()
    servicio = ServicioSesionesBase(sesion_bd, eventos=publicador)
    evento = EventoSesion("SESION_INICIADA", uuid.uuid4())
    with servicio._transaction():
        servicio._emitir(evento)
        publicador.publicar.assert_not_called()
    publicador.publicar.assert_called_once_with(evento)
    llamadas = [c[0] for c in sesion_bd.method_calls]
    assert llamadas.index("execute") < llamadas.index("commit")  # el INSERT del outbox va DENTRO de la transacción


def test_sin_modulo_6_configurado_no_se_registra_nada():
    """El puerto por defecto (`_SinRegistro`) no hace nada: los módulos funcionan sin el módulo 6."""
    configurado = outbox.registro()
    try:
        outbox.configurar(outbox._SinRegistro())
        db = MagicMock()
        outbox.registro().registrar(db, "X", uuid.uuid4(), {})
        db.execute.assert_not_called()
    finally:
        outbox.configurar(configurado)


def test_cerrar_un_intento_sigue_sin_registrar_nota_ni_avisos(entorno):
    headers = entorno.headers()
    intento = entorno.iniciar(headers)
    pregunta = entorno.preguntas[0]
    guardar(entorno.client, headers, intento["id"], pregunta["id"], pregunta["opciones"][0]["id"])
    entorno.client.post(f"{PART_URL}/{intento['id']}/finish", headers=headers)

    assert fila("SELECT nota_final FROM participacion WHERE id = :id", id=intento["id"]).nota_final is None
    assert contar("SELECT count(*) FROM evento_outbox WHERE tipo LIKE 'CALIFICACION%'") == 0
