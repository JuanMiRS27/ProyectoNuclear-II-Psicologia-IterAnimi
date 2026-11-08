"""Regresión de los comportamientos de módulos anteriores que el módulo 5 amplía o del que depende."""

from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.modules.evaluations.security import TIPO_TOKEN_RESULTADOS
from app.modules.sessions.security import TIPO_TOKEN_ESTUDIANTIL
from tests.conftest import alembic_config
from tests.participations_helpers import PART_URL, entorno, fila, guardar  # noqa: F401
from tests.sessions_helpers import ingresar


def test_el_modulo_5_no_agrega_migraciones():
    """El módulo 5 usa `nota_final` y `retroalimentacion_general` de la migración 0010.

    Módulo 6: la siguiente revisión (0011) es la de notificaciones y sigue directamente a la 0010.
    """
    script = ScriptDirectory.from_config(alembic_config())
    assert len(script.get_heads()) == 1
    assert script.get_revision("0011_notificaciones_eventos").down_revision == "0010_evaluacion_tras_cierre"


def test_cerrar_un_intento_sigue_sin_registrar_nota(entorno):
    """Módulo 4: el cierre no inventa una nota; solo el proceso de evaluación la registra."""
    headers = entorno.headers()
    intento = entorno.iniciar(headers)
    pregunta = entorno.preguntas[0]
    guardar(entorno.client, headers, intento["id"], pregunta["id"], pregunta["opciones"][0]["id"])
    entorno.client.post(f"{PART_URL}/{intento['id']}/finish", headers=headers)

    datos = fila("SELECT nota_final, retroalimentacion_general FROM participacion WHERE id = :id", id=intento["id"])
    assert (datos.nota_final, datos.retroalimentacion_general) == (None, None)


def test_el_ingreso_de_resolucion_sigue_cerrado_tras_finalizar(entorno):
    """Módulo 3: el acceso a resultados es otro endpoint; el ingreso de resolución no se reabre."""
    entorno.client.post(f"/api/v1/sessions/{entorno.sesion_id}/finish", headers=entorno.docente_headers)
    estudiante = entorno.estudiantes[0]
    assert ingresar(entorno.client, estudiante.correo, entorno.codigos[estudiante.correo]).status_code == 403


def test_tipos_de_token_distintos_y_configuracion_por_defecto():
    assert TIPO_TOKEN_RESULTADOS != TIPO_TOKEN_ESTUDIANTIL != "access"
    assert get_settings().STUDENT_RESULTS_TOKEN_EXPIRE_MINUTES == 60
