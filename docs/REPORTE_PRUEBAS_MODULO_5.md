# Reporte de pruebas — Módulo 5: Evaluación y Retroalimentación

**Proyecto:** Proyecto Nuclear II — Inter Nos
**Ejecución registrada:** 3 de noviembre de 2026, rama `modulo-5-evaluacion-retroalimentacion`, creada desde `main` en `9122a48` (cambios aún sin confirmar)
**Rutas:** relativas a `backend/`. Complementa, sin reemplazarlo, a [`REPORTE_PRUEBAS_MODULOS_1_4.md`](REPORTE_PRUEBAS_MODULOS_1_4.md).

| Resumen | Valor |
|---|---|
| Pruebas antes del módulo 5 | 1343 (680 unitarias, 205 de integración, 458 de regresión), todas aprobadas |
| Pruebas nuevas | **137**: 98 unitarias, 35 de integración y 4 de regresión |
| Total final | **1480** |
| Aprobadas / falladas / omitidas | **1480 / 0 / 0** |
| Cobertura de `app/` (líneas y ramas) | **99,56 %** |
| Cobertura de `app/modules/evaluations/` | **98,53 %** |

## Entorno

| Herramienta | Versión |
|---|---|
| Python | 3.14.8 |
| Pytest / pytest-cov / Coverage | 9.2.0 / 7.1.0 / 7.17.0 |
| PostgreSQL | Contenedor `postgres:17-alpine` desechable (`--tmpfs`), en `127.0.0.1:55432`, base `simulador_psicologia_test` |

La base de pruebas cumple las salvaguardas de `tests/db_guard.py`: es local, tiene un nombre de prueba, es distinta de `DATABASE_URL` y lleva la marca de base desechable.

## Pruebas nuevas

| Archivo | Tipo | Pruebas | Qué cubre |
|---|---|---:|---|
| `tests/unit/test_modulo_5.py` | Unitaria (sin PostgreSQL) | 98 | Selección de estrategia y contexto intercambiable; estrategias completa, incompleta (tres causas) y ausencia; corrección con una y con varias opciones correctas; preguntas sin responder; agrupación por criterio; porcentajes; ponderación; niveles con umbral y su límite exacto; comparación sin redondear; cálculo lineal sin umbrales o con umbrales incompletos; combinación de políticas; criterios sin preguntas y renormalización; `Decimal` y contexto decimal propio; redondeo ROUND_HALF_UP; rúbricas y niveles inválidos; límites de escala; determinismo; mapeo ORM → dominio; retroalimentación; eventos solo tras el commit (con dobles); tokens y acceso de resultados |
| `tests/integration/test_modulo_5_api.py` | Integración (PostgreSQL real) | 35 | Evaluación de FINALIZADA y de EXPIRADA por tiempo, por revocación y por fin de sesión; persistencia de la nota; ausencias sin participaciones ficticias y sin contar convocatorias revocadas; varios intentos; intentos en progreso omitidos; historial intacto; idempotencia sin eventos duplicados; recalificación de una nota incoherente; rúbrica no evaluable sin escrituras parciales; criterio sin preguntas; dos procesos concurrentes; disparadores del módulo 4; eventos post-commit; retroalimentación del docente; rechazo de `nota_final` enviada por el cliente; autorización (otro docente, anónimo, estudiante, administrador, tokens estudiantiles); bloqueo antes del cierre; consulta segura; token de solo lectura; revalidación; fuerza bruta compartida |
| `tests/test_evaluations_regression.py` | Regresión | 4 | Sin migraciones nuevas (head `0010`); cerrar un intento sigue sin generar nota; el ingreso de resolución sigue cerrado tras finalizar la sesión; tipos de token y configuración por defecto |

## Prueba existente ajustada

`tests/integration/test_modulo_4_api.py::test_no_existen_rutas_de_calificacion` comprobaba que **todavía no** existían rutas de calificación. Esa premisa deja de ser cierta con el módulo 5, así que la prueba fallaba por diseño. Se ajustó conservando su intención: las operaciones del módulo 4 (etiqueta `Participaciones`) no exponen rutas de calificación, toda ruta de calificación pertenece al módulo 5 (etiquetas `Evaluación` y `Resultados del estudiante`), y los esquemas `ParticipacionRead` y `CuestionarioRead` no incluyen `nota_final` ni `retroalimentacion_general`. En la revisión previa al merge se sustituyó la primera versión, que comparaba una lista exacta de ocho rutas, por esta comprobación de pertenencia, que no se rompe al añadir rutas legítimas. No se modificó ninguna otra prueba del equipo.

## Migraciones

| Verificación | Resultado |
|---|---|
| `alembic heads` | `0010_evaluacion_tras_cierre (head)`, único |
| `alembic upgrade head` | Correcto |
| `alembic check` | `No new upgrade operations detected.` |
| Ciclo `downgrade base` / `upgrade head` de la suite | Correcto |

El módulo 5 no necesita migraciones: usa `nota_final` y `retroalimentacion_general` (0009/0010).

## Reproducción (Git Bash, desde `backend/`)

```bash
docker run -d --rm --name inter_nos_pg_test -e POSTGRES_USER=simulador_test -e POSTGRES_PASSWORD=solo_pruebas_local -e POSTGRES_DB=simulador_psicologia_test -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:17-alpine
export TEST_DATABASE_URL="postgresql+psycopg://simulador_test:solo_pruebas_local@127.0.0.1:55432/simulador_psicologia_test"
export DATABASE_URL="postgresql+psycopg://simulador_test:solo_pruebas_local@127.0.0.1:55432/no_usada_dev"
pytest tests/unit
pytest tests/integration
pytest
pytest --cov=app --cov-report=term-missing --cov-report=html
```

En Git Bash para Windows, `docker run --tmpfs` debe lanzarse desde PowerShell, porque Git Bash convierte la ruta del tmpfs.

Las unitarias también se ejecutaron apuntando a un puerto sin servidor (`127.0.0.1:1`): **778 aprobadas**, lo que confirma que no se conectan a PostgreSQL.

## Limitaciones de la medición

- Las 7 líneas sin cubrir del módulo 5 son ramas defensivas: la nota fuera de escala tras validar los niveles, una participación que desaparece entre la autorización y el bloqueo, el esquema `Bearer` ausente en el token de resultados y un intento EN_PROGRESO con la sesión ya finalizada (imposible por los disparadores).
- La concurrencia se probó con dos procesos simultáneos sobre la misma sesión, no con carga sostenida.
- La cobertura mide ejecución, no corrección. Las reglas académicas están fijadas por aserciones explícitas de valores (p. ej., 2.20, 3.80, 3.33).
