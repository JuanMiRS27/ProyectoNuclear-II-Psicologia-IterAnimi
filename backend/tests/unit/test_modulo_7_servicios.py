"""Módulo 7: servicios de reportes y exportación CSV con el repositorio simulado (unitarias).

Complementa `test_modulo_7.py`, que prueba los cálculos y el formato CSV. Aquí se verifica que
cada exportación use la misma lectura coherente que la consulta, respete el límite de filas
sin leer de más, nunca incluya columnas secretas y que los reportes de caso y espacio armen sus
agregados sin inventar valores.
"""

import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.modules.cases.models import EstadoCasoEnum
from app.modules.participations.models import EstadoParticipacionEnum as EP
from app.modules.participations.models import MotivoCierreEnum as MC
from app.modules.reports import calculations as calc
from app.modules.reports import exporters
from app.modules.reports.repositories import FiltroEstudiantes, FiltroSesiones
from app.modules.reports.services import ExportacionService, ReportesAcademicosService, ReportesSesionService
from app.modules.sessions.models import EstadoSesionEnum as ES
from tests.conftest import RelojFijo
from tests.unit.fabricas import sesion_bd

T8 = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
T9 = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
T10 = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
D = Decimal
PALABRAS_SECRETAS = ("autorizaci", "contraseña", "token", "clave", "password")


def _fila_sesion(estado=ES.FINALIZADO):
    return SimpleNamespace(
        id=uuid.uuid4(), estado=estado, inicio=T8, fin=T10, tiempo_max_min=40, caso_id=uuid.uuid4(), caso_nombre="Conformidad",
        caso_estado=EstadoCasoEnum.PUBLICADO, espacio_id=uuid.uuid4(), espacio_nombre="Psicología Social", espacio_periodo="2026-2",
        docente_id=uuid.uuid4(), docente_nombre="Docente Titular", escala_max=D("5.00"),
    )


def _repo(fila=None):
    repo = MagicMock()
    repo.sesion.return_value = fila
    repo.conteos_convocatorias.return_value = {}
    repo.conteos_intentos.return_value = {}
    repo.agregado_notas.return_value = {}
    repo.rubrica.return_value = None
    repo.preguntas_del_caso.return_value = []
    return repo


def _exportador(repo, limite=exporters.MAX_FILAS_EXPORTACION):
    servicio = ExportacionService(sesion_bd(), RelojFijo(T9), limite=limite)
    servicio._repo = repo
    servicio._sesiones._repo = repo  # la exportación reutiliza los reportes REST: mismo repositorio
    return servicio


def _leer_csv(contenido: bytes) -> list[list[str]]:
    assert contenido.startswith(b"\xef\xbb\xbf")  # UTF-8 con BOM
    return list(csv.reader(io.StringIO(contenido.decode("utf-8-sig"))))


def _sin_secretos(encabezados: list[str]) -> bool:
    texto = " ".join(encabezados).lower()
    return not any(p in texto for p in PALABRAS_SECRETAS)


# --- Exportaciones por sesión -------------------------------------------------------------------


def test_resumen_csv_tiene_todos_los_indicadores_y_nombre_seguro():
    fila = _fila_sesion()
    archivo = _exportador(_repo(fila)).exportar_sesion(fila.id, fila.docente_id, "resumen", FiltroEstudiantes())

    filas = _leer_csv(archivo.contenido)

    assert filas[0] == ["Indicador", "Valor"]
    assert len(filas) == 1 + 31 + 4 * 3  # datos de la sesión + tasas con porcentaje, numerador y denominador
    valores = dict(filas[1:])
    assert valores["Sesión"] == str(fila.id)
    assert valores["Inicio (UTC)"] == "2026-11-03T08:00:00Z"
    assert valores["Tasa de participación (porcentaje)"] == ""  # sin convocatorias no se inventa un 0 %
    assert archivo.nombre == f"reporte_sesion_resumen_{fila.id.hex[:8]}_20261103.csv"


def test_estudiantes_csv_resume_cada_intento_sin_columnas_secretas():
    fila = _fila_sesion()
    repo = _repo(fila)
    conv_id = uuid.uuid4()
    repo.estudiantes_para_exportar.return_value = [
        SimpleNamespace(
            estudiante_id=uuid.uuid4(), nombre_completo="Eva Ruiz", correo="eva@universidad.edu.co", codigo_institucional="E-1",
            convocatoria_id=conv_id, revocada_en=None, intentos_autorizados=2, intentos=2, activo=False, calificados=1,
        )
    ]
    repo.intentos_breves.return_value = [
        SimpleNamespace(id=uuid.uuid4(), convocatoria_id=conv_id, numero_intento=1, estado=EP.FINALIZADA,
                        motivo_cierre=MC.VOLUNTARIO, nota_final=D("4.5"), respondidas=3),
        SimpleNamespace(id=uuid.uuid4(), convocatoria_id=conv_id, numero_intento=2, estado=EP.EXPIRADA,
                        motivo_cierre=MC.SESION_FINALIZADA, nota_final=None, respondidas=0),
    ]

    filas = _leer_csv(_exportador(repo).exportar_sesion(fila.id, fila.docente_id, "estudiantes", FiltroEstudiantes()).contenido)

    encabezados, datos = filas[0], dict(zip(filas[0], filas[1]))
    assert _sin_secretos(encabezados)
    assert datos["Convocatoria activa"] == "Sí"
    assert datos["Notas por intento"].startswith("1: 4.50 (")
    assert "2: sin nota (" in datos["Notas por intento"]  # una nota ausente nunca se exporta como 0
    repo.intentos_breves.assert_called_once_with([conv_id])  # una sola consulta para todos los intentos
    repo.terminar_lectura.assert_called_once()


def test_intentos_csv_respeta_el_limite_sin_seguir_consultando():
    fila = _fila_sesion()
    repo = _repo(fila)
    repo.intentos_detallados.return_value = [object()] * 3

    with pytest.raises(exporters.ExportacionExcedeLimiteError):
        _exportador(repo, limite=2).exportar_sesion(fila.id, fila.docente_id, "intentos", FiltroEstudiantes())

    assert repo.intentos_detallados.call_args.kwargs["limite"] == 3
    repo.total_preguntas.assert_not_called()
    repo.terminar_lectura.assert_called_once()


def test_intentos_csv_oculta_aciertos_de_un_intento_abierto():
    fila = _fila_sesion(ES.EN_CURSO)
    repo = _repo(fila)
    repo.total_preguntas.return_value = 3
    repo.intentos_detallados.return_value = [
        SimpleNamespace(
            id=uuid.uuid4(), estudiante_id=uuid.uuid4(), convocatoria_id=uuid.uuid4(), nombre_completo="Eva", correo="eva@u.edu.co",
            codigo_institucional=None, numero_intento=1, inicio=T8, fin=None, estado=EP.EN_PROGRESO, motivo_cierre=None,
            respondidas=2, aciertos=2, nota_final=None,
        )
    ]

    filas = _leer_csv(_exportador(repo).exportar_sesion(fila.id, fila.docente_id, "intentos", FiltroEstudiantes()).contenido)

    datos = dict(zip(filas[0], filas[1]))
    assert _sin_secretos(filas[0])
    assert (datos["Preguntas respondidas"], datos["Preguntas sin responder"]) == ("2", "1")
    assert (datos["Aciertos"], datos["Errores"], datos["Nota final"], datos["Fin (UTC)"]) == ("", "", "", "")


@pytest.mark.parametrize(("tipo", "consulta"), [("criterios", "correccion_por_criterio"), ("preguntas", "correccion_por_pregunta")])
def test_sin_intentos_cerrados_no_se_corrige_nada(tipo, consulta):
    fila = _fila_sesion()
    repo = _repo(fila)
    repo.preguntas_del_caso.return_value = [
        SimpleNamespace(id=uuid.uuid4(), enunciado="¿Qué ocurre?", escenario="Inicio", orden_escenario=1, orden=1,
                        criterio_id=None, criterio=None, corregible=True)
    ]

    filas = _leer_csv(_exportador(repo).exportar_sesion(fila.id, fila.docente_id, tipo, FiltroEstudiantes()).contenido)

    getattr(repo, consulta).assert_not_called()
    if tipo == "preguntas":
        datos = dict(zip(filas[0], filas[1]))
        assert (datos["Intentos considerados"], datos["Porcentaje de aciertos"]) == ("0", "")
    else:
        assert len(filas) == 1  # sin rúbrica no hay criterios: solo encabezados


def test_exportacion_de_sesion_ajena_es_404_y_cierra_la_lectura():
    repo = _repo(None)

    with pytest.raises(NotFoundError):
        _exportador(repo).exportar_sesion(uuid.uuid4(), uuid.uuid4(), "estudiantes", FiltroEstudiantes())

    repo.iniciar_lectura.assert_called_once()
    repo.terminar_lectura.assert_called_once()
    repo.estudiantes_para_exportar.assert_not_called()


# --- Exportación por espacio académico ----------------------------------------------------------


def _espacio(activo=True):
    return SimpleNamespace(id=uuid.uuid4(), nombre="Psicología Social", periodo="2026-2", activo=activo)


def test_exportar_espacio_lista_las_sesiones_con_sus_conteos():
    fila = _fila_sesion()
    repo = _repo()
    repo.espacio.return_value = _espacio()
    repo.pagina_sesiones.return_value = [fila]
    repo.conteos_convocatorias.return_value = {fila.id: calc.ConteosConvocatorias(activas=4, activas_con_intento=3)}
    repo.conteos_intentos.return_value = {fila.id: calc.ConteosIntentos(finalizados=2, expirados=1, calificados=3)}
    espacio_id = uuid.uuid4()

    archivo = _exportador(repo).exportar_espacio(espacio_id, FiltroSesiones(fila.docente_id))

    datos = dict(zip(*_leer_csv(archivo.contenido)))
    assert (datos["Convocatorias activas"], datos["Intentos"], datos["Tasa de participación (%)"]) == ("4", "3", "75.00")
    assert archivo.nombre == f"reporte_espacio_sesiones_{espacio_id.hex[:8]}_20261103.csv"


def test_exportar_espacio_respeta_el_limite():
    repo = _repo()
    repo.espacio.return_value = _espacio()
    repo.pagina_sesiones.return_value = [_fila_sesion()] * 3

    with pytest.raises(exporters.ExportacionExcedeLimiteError):
        _exportador(repo, limite=2).exportar_espacio(uuid.uuid4(), FiltroSesiones(uuid.uuid4()))

    assert repo.pagina_sesiones.call_args.kwargs == {"skip": 0, "limit": 3}
    repo.conteos_intentos.assert_not_called()


@pytest.mark.parametrize(
    ("espacio", "con_historial"), [(None, False), (_espacio(activo=False), False)], ids=["inexistente", "inactivo-sin-historial"]
)
def test_exportar_espacio_sin_acceso_es_404_sin_leer_sesiones(espacio, con_historial):
    repo = _repo()
    repo.espacio.return_value = espacio
    repo.docente_tiene_sesiones_en_espacio.return_value = con_historial

    with pytest.raises(NotFoundError):
        _exportador(repo).exportar_espacio(uuid.uuid4(), FiltroSesiones(uuid.uuid4()))

    repo.pagina_sesiones.assert_not_called()
    repo.terminar_lectura.assert_called_once()


def test_espacio_inactivo_con_historial_del_docente_sigue_visible():
    repo = _repo()
    repo.espacio.return_value = _espacio(activo=False)
    repo.docente_tiene_sesiones_en_espacio.return_value = True
    repo.pagina_sesiones.return_value = []

    archivo = _exportador(repo).exportar_espacio(uuid.uuid4(), FiltroSesiones(uuid.uuid4()))

    assert len(_leer_csv(archivo.contenido)) == 1


# --- Reportes académicos -------------------------------------------------------------------------


def _academicos(repo):
    servicio = ReportesAcademicosService(sesion_bd(), RelojFijo(T9))
    servicio._repo = repo
    return servicio


def test_mis_sesiones_completa_conteos_ausentes_con_ceros():
    fila = _fila_sesion(ES.SIN_INICIAR)
    repo = _repo()
    repo.pagina_sesiones.return_value = [fila]
    repo.contar_sesiones.return_value = 7

    pagina = _academicos(repo).mis_sesiones(FiltroSesiones(fila.docente_id), skip=5, limit=1)

    item = pagina.items[0]
    assert (pagina.total, pagina.skip, pagina.limit) == (7, 5, 1)
    assert (item.convocatorias_activas, item.intentos, item.tasa_participacion.porcentaje) == (0, 0, None)
    repo.conteos_intentos.assert_called_once_with([fila.id], T9)
    repo.terminar_lectura.assert_called_once()


def _conteos_agregados(conteos):
    def conteos_intentos(ids, ahora, agrupar=True):
        return {None: conteos} if not agrupar else {}

    return conteos_intentos


def test_reporte_de_caso_sin_notas_no_inventa_estadisticas():
    repo = _repo()
    caso = SimpleNamespace(id=uuid.uuid4(), nombre="Conformidad", estado=EstadoCasoEnum.ARCHIVADO, escala_max=D("5"))
    repo.caso_del_autor.return_value = caso
    repo.conteos_intentos.side_effect = _conteos_agregados(calc.ConteosIntentos(en_progreso=1))
    repo.pagina_sesiones.return_value = []
    repo.contar_sesiones.return_value = 0
    repo.sesiones_por_estado.return_value = {ES.EN_CURSO: 1}

    reporte = _academicos(repo).caso(caso.id, FiltroSesiones(uuid.uuid4()), skip=0, limit=20)

    assert reporte.caso.estado == EstadoCasoEnum.ARCHIVADO  # un caso archivado conserva su historial
    assert (reporte.estadisticas.evaluados, reporte.estadisticas.promedio, reporte.estadisticas.mediana) == (0, None, None)
    assert (reporte.totales.intentos, reporte.totales.en_progreso) == (1, 1)
    assert reporte.sesiones_por_estado.en_curso == 1
    assert reporte.criterios.intentos_considerados == 0
    repo.correccion_por_criterio.assert_not_called()


def test_reporte_de_caso_ajeno_es_404_y_no_calcula():
    repo = _repo()
    repo.caso_del_autor.return_value = None

    with pytest.raises(NotFoundError):
        _academicos(repo).caso(uuid.uuid4(), FiltroSesiones(uuid.uuid4()), skip=0, limit=20)

    repo.agregado_notas.assert_not_called()
    repo.terminar_lectura.assert_called_once()


def test_reporte_de_espacio_incluye_los_casos_utilizados():
    repo = _repo()
    espacio = _espacio()
    repo.espacio.return_value = espacio
    repo.conteos_intentos.side_effect = _conteos_agregados(calc.ConteosIntentos(finalizados=4, calificados=4))
    repo.casos_utilizados.return_value = [
        SimpleNamespace(id=uuid.uuid4(), nombre="Conformidad", estado=EstadoCasoEnum.PUBLICADO, escala_max=D("5"),
                        sesiones=2, evaluaciones=4, promedio=D("3.875"))
    ]
    repo.promedio_normalizado.return_value = D("77.5")
    repo.pagina_sesiones.return_value = []
    repo.contar_sesiones.return_value = 2
    repo.sesiones_por_estado.return_value = {ES.FINALIZADO: 2}

    reporte = _academicos(repo).espacio(espacio.id, FiltroSesiones(uuid.uuid4()), skip=0, limit=20)

    caso = reporte.casos_utilizados[0]
    assert (caso.promedio, caso.escala_max, caso.evaluaciones_registradas) == (D("3.88"), D("5.00"), 4)
    assert (reporte.promedio_porcentaje_escala, reporte.totales.evaluaciones_registradas) == (D("77.50"), 4)
    assert (reporte.sesiones_registradas, reporte.sesiones_por_estado.finalizadas) == (2, 2)


# --- Reportes de una sesión ---------------------------------------------------------------------


def _por_sesion(repo):
    servicio = ReportesSesionService(sesion_bd(), RelojFijo(T9))
    servicio._repo = repo
    return servicio


def test_criterios_de_sesion_identifican_la_sesion():
    fila = _fila_sesion()

    reporte = _por_sesion(_repo(fila)).criterios(fila.id, fila.docente_id)

    assert reporte.sesion_id == fila.id
    assert (reporte.escala_max, reporte.criterios) == (None, [])


def test_preguntas_de_sesion_con_intentos_cerrados_usan_la_correccion():
    fila = _fila_sesion()
    repo = _repo(fila)
    pregunta = SimpleNamespace(id=uuid.uuid4(), enunciado="¿Qué ocurre?", escenario="Inicio", orden_escenario=1, orden=1,
                               criterio_id=None, criterio=None, corregible=True)
    repo.preguntas_del_caso.return_value = [pregunta]
    repo.conteos_intentos.return_value = {fila.id: calc.ConteosIntentos(finalizados=4)}
    repo.correccion_por_pregunta.return_value = {pregunta.id: (4, 3, 1)}

    reporte = _por_sesion(repo).preguntas(fila.id, fila.docente_id)

    p = reporte.preguntas[0]
    assert (reporte.intentos_considerados, p.aciertos, p.errores, p.sin_responder, p.porcentaje_aciertos) == (4, 1, 2, 1, D("25.00"))
    repo.correccion_por_pregunta.assert_called_once_with([fila.id])
