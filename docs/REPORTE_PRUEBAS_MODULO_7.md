# Reporte de pruebas — Módulo 7: Seguimiento y Reportes

**Proyecto:** Proyecto Nuclear II — Inter Nos
**Ejecución registrada:** 7 de noviembre de 2026; revisión final el 8 de noviembre de 2026, rama `modulo-7-seguimiento-reportes`, creada desde `main` local en `01b1504` (cambios aún sin confirmar)
**Rutas:** relativas a `backend/`. Complementa, sin reemplazarlos, a [`REPORTE_PRUEBAS_MODULOS_1_4.md`](REPORTE_PRUEBAS_MODULOS_1_4.md), [`REPORTE_PRUEBAS_MODULO_5.md`](REPORTE_PRUEBAS_MODULO_5.md) y [`REPORTE_PRUEBAS_MODULO_6.md`](REPORTE_PRUEBAS_MODULO_6.md).

| Resumen | Valor |
|---|---|
| Pruebas antes del módulo 7 (`01b1504`, árbol limpio, con Mailpit) | 1662 aprobadas (909 unitarias, 287 en `tests/integration/` y 466 de regresión); cobertura 99,09 %, módulo 6 97,27 % |
| Pruebas nuevas | **153**: 106 unitarias, 39 de integración, 3 de rendimiento y 5 de regresión (17 de ellas añadidas en la revisión final) |
| Total final | **1815** (1015 unitarias, 329 en `tests/integration/` y 471 de regresión) |
| Aprobadas / falladas / omitidas | **1815 / 0 / 0** con Mailpit |
| Cobertura de `app/` (líneas y ramas) | **99,19 %** |
| Cobertura del módulo 7 (`app/modules/reports/`) | **99,74 %** |
| Prueba existente ajustada | 1 (ver "Prueba existente ajustada") |

## 1. Objetivo del módulo

Permitir a los docentes consultar el desarrollo y los resultados de sus actividades académicas: seguimiento operativo de sesiones y convocatorias, participaciones, ausencias, intentos, calificaciones, desempeño por criterio y por pregunta, historial por caso y por espacio académico, y exportación CSV. El módulo es **solo de lectura**.

## 2. Requisitos funcionales relacionados

El repositorio no incluye un documento de requisitos con obligaciones de reportes. Los únicos RF citados son RF-20, RF-21 y RF-27, del módulo 6. Por lo tanto:

- Las métricas, los endpoints y el formato CSV son **propuestas de implementación** tomadas del enunciado del módulo 7.
- No se encontró ninguna exigencia de **Excel ni de PDF**, así que no se implementaron ni se añadieron dependencias para ellos.

## 3. Arquitectura

`app/modules/reports/` contiene `calculations/` (puro), `repositories/` (SQL), `services/` (coordinación, instantánea y propiedad), `exporters/` (CSV), `schemas/`, `dependencies/` y `routers/`. El detalle está en el README, sección "Módulo 7".

- **Sin tablas, migraciones, índices ni dependencias nuevas.**
- **Sin patrones de diseño nuevos.** Se reutilizan los contratos del módulo 5: `CalculadoraRubrica.puntuar`, `SelectorEstrategia`, `CIERRES_ADMINISTRATIVOS`, `mapeo.criterio` y `redondear`.

## 4. Consultas y servicios

| Servicio | Reportes |
|---|---|
| `ReportesSesionService` | Resumen, estudiantes (paginado), desempeño individual, notas, criterios, preguntas |
| `ReportesAcademicosService` | Mis sesiones, espacio académico, historial del caso |
| `ExportacionService` | CSV de sesión (5 tipos) y de espacio |

Cada reporte es **una transacción READ ONLY con REPEATABLE READ**, de modo que todas sus consultas ven la misma instantánea. Las agregaciones se hacen en PostgreSQL con `COUNT(*) FILTER`, `GROUP BY` y `percentile_disc`.

## 5-10. Fórmulas, ausencias, intentos, notas nulas, criterios y preguntas

Están documentados en el README ("Fórmulas de los indicadores", "Ausencias y condición del convocado", "Intentos y notas", "Desempeño por criterio y por pregunta"). En resumen:

- Tasas con numerador y denominador explícitos; `null` si el denominador es 0.
- Una ausencia solo se declara con la sesión FINALIZADA. Una convocatoria revocada no es una ausencia.
- Cada intento conserva su nota y no hay nota consolidada.
- Una nota nula no es cero; `SIN_CALIFICAR` y `PENDIENTE_CALIFICACION` se distinguen.
- El puntaje por criterio se obtiene con `CalculadoraRubrica.puntuar`. Un criterio sin preguntas es no evaluable.
- La corrección por pregunta sigue la regla del módulo 5: con varias opciones correctas, sirve cualquiera.

## 11. Seguridad y autorización

| Actor | Resultado verificado (`test_autorizacion_de_todos_los_endpoints`, 11 rutas) |
|---|---|
| Docente responsable | 200 |
| Otro docente | 404 en sesión, estudiante, exportación y caso. En espacio y "mis sesiones": 200, sin datos ajenos |
| Administrador | 403 |
| Estudiante con token `access` | 403 |
| Token `student` / token `student_results` | 401 / 401 |
| Anónimo | 401 |

Además:

- `test_conocer_un_uuid_no_autoriza_el_acceso`: sesión, estudiante y caso de otro docente responden 404 sin filtrar el correo.
- `test_parametros_desconocidos_no_amplian_el_alcance`: `docente_id` y otros parámetros desconocidos responden 422.
- `test_las_rutas_de_reportes_solo_admiten_lectura`: 405 para escrituras.
- `test_esquemas_no_declaran_datos_secretos`.
- Los CSV no contienen códigos cifrados ni en claro, claves ni tokens.

## 12. Endpoints REST

Hay 11 rutas GET; la tabla completa está en el README. Antes de registrarlas se revisó la tabla de rutas: no hay colisiones con `/sessions/{id}`, `/cases/{id}/…` ni `/academic-spaces/{id}`, y no se duplicó ninguna ruta del módulo 5.

### Ejemplos verificables (valores asertados por las pruebas)

Todos los ejemplos usan el caso de `dsl_valido()` y la sesión del `entorno` de pruebas (08:00-10:00 UTC, 40 min, 3 convocados).

**Resumen con un intento finalizado y otro en curso** (`test_varios_intentos…` y la ejecución de humo):

```http
GET /api/v1/sessions/{id}/reports/summary
Authorization: Bearer <docente responsable>

200 OK
{"convocatorias": {"activas": 3, "activas_con_intento": 1, "pendientes": 2, "ausentes": 0, ...},
 "intentos": {"total": 2, "en_progreso": 1, "finalizados": 1, ...},
 "indicadores": {"tasa_participacion": {"numerador": 1, "denominador": 3, "porcentaje": "33.33"},
                 "tasa_finalizacion":  {"numerador": 1, "denominador": 2, "porcentaje": "50.00"}, ...}}
```

**Sesión sin convocatorias** (`test_resumen_de_sesion_sin_convocatorias`): todas las tasas valen `{"numerador": 0, "denominador": 0, "porcentaje": null}`.

**Estadísticas de notas** (`test_estadisticas_de_notas_registradas_coinciden_con_el_modulo_5`), con notas 5.00, 2.20 y 1.00 registradas por el módulo 5:

```http
GET /api/v1/sessions/{id}/reports/grades

200 OK
{"intentos_cerrados": 3, "intentos_sin_nota": 0, "estudiantes_con_nota": 3,
 "estadisticas": {"unidad": "intento", "evaluados": 3, "escala_max": "5.00", "minimo": "1.00", "maximo": "5.00",
                  "promedio": "2.73", "mediana": "2.20", "promedio_porcentaje_escala": "54.67",
                  "distribucion": [{"desde": "0.00", "hasta": "1.00", "cantidad": 0, ...}, {"desde": "1.00", "hasta": "2.00", "cantidad": 1, ...},
                                   {"desde": "2.00", "hasta": "3.00", "cantidad": 1, ...}, {"desde": "3.00", "hasta": "4.00", "cantidad": 0, ...},
                                   {"desde": "4.00", "hasta": "5.00", "incluye_hasta": true, "cantidad": 1, ...}]},
 "por_estado": {...}}
```

**Notas nulas** (`test_notas_nulas_no_se_promedian_como_cero`): con notas 2.20 y 2.60 más un intento `SIN_CALIFICAR`, el promedio es `"2.40"` y no 1.60.

**Historial individual con dos intentos** (`test_varios_intentos…`):

```http
GET /api/v1/sessions/{id}/reports/students/{student_id}

200 OK
{"condicion": "PARTICIPO", "intentos_autorizados": 2,
 "intentos": [{"numero_intento": 1, "estado": "FINALIZADA", "condicion": "COMPLETA", "preguntas_totales": 3,
               "aciertos": 0, "nota_final": "1.00", "situacion": "CALIFICADO", ...},
              {"numero_intento": 2, ..., "nota_final": "5.00", "situacion": "CALIFICADO"}]}
```

No aparece ningún campo de nota consolidada.

**Criterio sin preguntas** (`TestCriterioSinPreguntas`): `{"descripcion": "Criterio sin preguntas", "evaluable": false, "total_preguntas": 0, "porcentaje_aciertos": null, "puntaje_promedio": null, "advertencia": "Sin preguntas asociadas: no evaluable (SIN_EVIDENCIA en el módulo 5)."}`

**Parámetro desconocido:** `GET /api/v1/reports/my-sessions?docente_id=<uuid>` → `422`.

**Exportación** (`test_exportaciones_csv_correctas_y_sin_datos_secretos`):

```http
GET /api/v1/sessions/{id}/reports/export?tipo=intentos

200 OK
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="reporte_sesion_intentos_<id8>_20261103.csv"
Cache-Control: no-store

"ID del estudiante","Nombre",…,"Inicio (UTC)",…,"Nota final","Escala máxima","Situación"
"…","Usuario Estudiante 2",…,"2026-11-03T08:00:00Z",…,"2.20","5.00","CALIFICADO"
"…","Usuario Estudiante 3",…,"2026-11-03T08:00:00Z",…,"","5.00","SIN_CALIFICAR"
```

**Exportación sobre el límite** (`test_exportacion_que_supera_el_limite_responde_422`): `422 {"detail": "El reporte supera el máximo de 1 filas exportables; aplique filtros para reducirlo.", "codigo": "EXPORTACION_EXCEDE_LIMITE", "limite": 1}`. El ejemplo usa un límite de prueba de 1; el valor real es 5000.

## 13. Exportaciones

Hay seis exportaciones: resumen, estudiantes, intentos, criterios y preguntas de una sesión, y las sesiones de un espacio. Características comunes:

- UTF-8 con BOM, `QUOTE_ALL` y CRLF.
- ISO 8601 en UTC; una nota nula es una celda vacía.
- Protección contra fórmulas.
- Nombre de archivo seguro.
- Máximo de 5000 filas, con 422 si se supera.
- Mismos permisos y filtros que la consulta JSON.
- Se genera en memoria y nunca se guarda en disco.

## 14-15. Pruebas nuevas

| Archivo | Tipo | Pruebas | Qué cubre |
|---|---|---:|---|
| `tests/unit/test_modulo_7.py` | Unitaria (sin PostgreSQL) | 106 | Tasas y denominador cero; redondeo ROUND_HALF_UP; estudiantes frente a intentos; totales por estado; condición del convocado en cada estado de sesión; situación del intento; `calificable` comparado con las **estrategias reales** del módulo 5 (8 combinaciones); mediana; promedio con `Decimal`; notas nulas; distribución y límites de tramo; escala distinta de 5; escalas incompatibles; agregado equivalente al SQL; criterios (sin preguntas, lineal, niveles inválidos, sin escala, puntaje idéntico a `CalculadoraRubrica`); preguntas (sin intentos, sin opción correcta, conteos incoherentes); rango de fechas; filtros (UTC, rango, parámetros desconocidos, límites); escape de comodines; CSV (BOM, CRLF, comillas, nulos, fórmulas, límite, filas incompletas, nombre seguro, cabeceras); servicios con repositorio simulado (ausencias según el estado, 404 y cierre de la lectura, página sin N+1, intento en progreso sin aciertos, espacio y caso sin acceso, límite de exportación con `límite + 1`); transacción READ ONLY/REPEATABLE READ; esquemas sin secretos |
| `tests/integration/test_modulo_7_api.py` | Integración (PostgreSQL real) | 39 | **Sesiones:** sin convocatorias, con convocatorias, participaciones activas (sin ausencias antes del cierre; el reporte no cierra intentos vencidos), cerradas con sus tres motivos, ausencias iguales a `/absences` del módulo 5, revocadas con historial. **Calificaciones:** estadísticas iguales a las notas del módulo 5, notas nulas, FINALIZADA frente a EXPIRADA, varios intentos, criterios y preguntas iguales al desglose del módulo 5, varias opciones correctas, criterio sin preguntas. **Académico:** espacio compartido sin datos ajenos (también en CSV), filtros combinados de estudiantes, promedio normalizado, espacio inactivo, caso ARCHIVADO, filtros y rango semiabierto. **Autorización:** seis actores × 11 rutas, UUID ajenos, parámetros desconocidos, solo GET. **Exportación:** contenido y cabeceras de los 5 tipos, sin secretos, filtros, fórmulas, sin permisos, vacía, límite (sesión y espacio). **Concurrencia:** instantánea ante una finalización, una calificación y una revocación concurrentes; transacción de solo lectura; agregados íntegros con escrituras en paralelo |
| `tests/integration/test_modulo_7_rendimiento.py` | Rendimiento (PostgreSQL real) | 3 | Consultas constantes con 5 y 200 estudiantes; filas acotadas; paginación; exportación de 240 intentos y límite |
| `tests/test_reports_regression.py` | Regresión | 5 | Head único `0011` (sin migraciones); huella de las tablas académicas idéntica tras consultar todos los reportes y exportaciones (antes y después de finalizar); el módulo 4 sigue guardando respuestas; el módulo 5 sigue calculando 2.20 y es idempotente; el módulo 6 sigue registrando `SESION_FINALIZADA` y los reportes no añaden eventos |

### Prueba existente ajustada

`tests/integration/test_modulo_4_api.py::test_no_existen_rutas_de_calificacion` decidía por palabras contenidas en la ruta (`grade`, `result`…). La ruta de consulta `/sessions/{id}/reports/grades` la hacía fallar por diseño.

Primero se ajustó admitiendo la etiqueta del módulo 7 en operaciones GET. En la revisión final se **reescribió de forma estructural**, sin depender de palabras: ver "Revisión final", punto 2. Conserva su intención:
- El módulo 4 no expone calificación.
- Solo el módulo 5 la registra.
- El módulo 7 solo consulta.

No se modificó ni eliminó ninguna otra prueba del equipo.

### Fallos encontrados y corregidos durante el desarrollo

| Fallo | Causa | Corrección |
|---|---|---|
| Consulta del promedio normalizado | Faltaba `select_from(Participacion)` | Corregido en el repositorio |
| Prueba de motivos de cierre | El intento del tercer estudiante también agotó su tiempo al avanzar el reloj (en el módulo 4 prevalece `TIEMPO_AGOTADO`) | Se reordenó la prueba; el código era correcto |
| Notas cargadas una a una (204 filas con 400 intentos) | Detectado por la prueba de rendimiento | Agregación completa en SQL: mediana exacta con `percentile_disc` y tramos con `GROUP BY` (8 filas) |
| Prueba de rendimiento con un parámetro llamado `estudiantes` | Chocaba con la fixture del mismo nombre | Se renombró |

## 16. Cobertura

| Ámbito | Cobertura |
|---|---|
| `app/` | 99,19 % |
| `app/` sin el módulo 7 | 99,09 % (sin cambios respecto a la línea base) |
| `app/modules/reports/` | 99,74 % |

Sin cubrir en el módulo 7: el `OverflowError` de fechas extremas en `schemas/` (2 líneas, rama defensiva) y una rama parcial de los tramos en `repositories/` (escala nula con notas registradas, imposible porque una nota exige rúbrica).

Salida completa de la ejecución: [`docs/evidencias/modulo_7/suite_completa_con_cobertura.txt`](evidencias/modulo_7/suite_completa_con_cobertura.txt).

## 17. Rendimiento

Ejecución local en Windows con Docker. Los tiempos dependen del equipo y **no son objetivos**. Datos completos en [`docs/evidencias/modulo_7/`](evidencias/modulo_7/).

| Endpoint | Consultas (5 → 200 estudiantes) | Filas devueltas (5 → 200) | ms (5 → 200) |
|---|---|---|---|
| summary | 5 → 5 | 4 → 4 | 28 → 27 |
| students (página de 20) | 6 → 6 | 21 → 63 | 31 → 45 |
| students/{id} | 6 → 6 | 6 → 6 | 26 → 26 |
| grades | 9 → 9 | 8 → 8 | 34 → 42 |
| criteria | 8 → 8 | 29 → 809 | 34 → 69 |
| questions | 6 → 6 | 9 → 9 | 29 → 62 |
| export estudiantes | 5 → 5 | 20 → 605 | 23 → 53 |
| export intentos | 5 → 5 | 13 → 403 | 27 → 55 |
| my-sessions | 6 → 6 | 5 → 5 | 26 → 28 |
| academic-spaces/{id}/reports | 12 → 12 | 11 → 11 | 43 → 51 |
| cases/{id}/reports | 17 → 17 | 38 → 818 | 58 → 98 |

- **Sin N+1:** el número de consultas es idéntico. Incluye la autenticación y la apertura de la transacción.
- **Sin cargar respuestas:** con 1200 respuestas almacenadas, resumen, notas, preguntas, espacio y "mis sesiones" devuelven menos de 50 filas.
- **Criterios:** devuelve intento × criterio (800 filas), porque debe aplicar `CalculadoraRubrica.puntuar` a cada intento. Son menos filas que respuestas.
- **Memoria:** exportar 240 intentos (60 KB) tuvo un pico de unos 665 KiB, medido con `tracemalloc`. Las exportaciones están acotadas a 5000 filas.

**Limitaciones de la medición:**
- Un solo equipo y una sola sesión con 400 intentos.
- Sin carga concurrente sostenida.
- `tracemalloc` mide solo la memoria de Python.

## 18. Limitaciones

Ver README, "Limitaciones y decisiones pendientes":
- Sin nota consolidada.
- Se usa `nota_final` tal como está registrada, sin recalcular.
- Administradores sin acceso a los reportes.
- Solo CSV.
- El criterio trae una fila por intento × criterio.
- Sin caché ni reportes históricos.

## Revisión final (8 de noviembre de 2026)

### 1. Autoría del caso frente a responsabilidad de la sesión

**Sin defecto en el código.** El informe anterior decía "docente responsable de la sesión **o** autor del caso", y esa redacción era imprecisa. Lo que el código hace es esto:

- Todas las consultas de sesión filtran por `Sesion.docente_id`.
- El historial del caso exige además la autoría (regla del módulo 2, sin cambios) y solo agrega las sesiones del propio docente.

Se corrigió la redacción en `services/base.py` y en el README.

La API del módulo 3 solo deja programar casos propios, pero el disparador de PostgreSQL no exige la autoría. Por eso la prueba reproduce el peor caso insertando directamente la sesión del docente B con el caso del docente A.

| Comprobación (`test_el_autor_del_caso_no_accede_a_la_sesion_de_otro_docente`) | Resultado |
|---|---|
| A en los 6 reportes de la sesión de B y en las 5 exportaciones CSV | 404 `{"detail": "Sesión no encontrada."}`, igual que una sesión inexistente |
| B en esas mismas 11 rutas | 200 |
| `/cases/{id}/reports`, `/academic-spaces/{id}/reports`, su exportación y `/reports/my-sessions` de A | Solo la sesión de A. Promedio 2.20 (sin la nota 4.75 de B), 44.00 % normalizado y 1 intento considerado en criterios |
| Filtración hacia A | Ninguna respuesta de A contiene el id de la sesión de B, el nombre o el correo de su estudiante ni la nota 4.75 |
| B en `/cases/{id}/reports` del caso de A | 404 (B no es el autor; regla del módulo 2) |
| B en su espacio y en sus sesiones | Solo su sesión (95.00 %) y ningún estudiante de A |

### 2. Prueba de regresión del módulo 4

**Problema real.** El ajuste anterior seguía decidiendo por palabras contenidas en la ruta (`grade`, `result`…) y por etiquetas. `test_no_existen_rutas_de_calificacion` se reescribió de forma **estructural**, recorriendo las rutas reales de FastAPI:

- **Módulo 4:** ningún modelo de entrada o salida alcanzable (resueltos de forma recursiva) contiene `nota_final` ni `retroalimentacion_general`, y ninguna ruta inyecta `EvaluacionService`.
- **Módulo 5:** es el único que inyecta `EvaluacionService` (la única escritura de nota y retroalimentación) y lo hace en operaciones POST y PATCH. Un recorrido del AST de `app/` confirma que solo `app/modules/evaluations/` asigna esos campos.
- **Módulo 7:** solo GET, sin cuerpo de petición y sin servicios de escritura entre sus dependencias.
- Se conserva la comprobación original de `ParticipacionRead` y `CuestionarioRead`.

Para verificar que la prueba detecta lo que debe, se aplicaron **mutaciones controladas** y la prueba falló en las cuatro:
- Una ruta POST en el módulo 7.
- Una ruta del módulo 7 que inyecta `EvaluacionService`.
- Una ruta del módulo 4 con `nota_final` anidado en su respuesta.
- Un archivo del módulo 7 que asigna `nota_final`.

Además, `test_las_rutas_de_reportes_solo_admiten_lectura` ahora recorre las **11** rutas del módulo 7, no solo una. Las cuatro escrituras responden 405 y la huella de las tablas académicas no cambia.

### 3. Verificaciones adicionales

| Verificación | Resultado | Prueba |
|---|---|---|
| El historial de un estudiante no incluye a otros | Cumple. Solo sus dos intentos y ningún correo ni nombre ajeno, tampoco en el CSV | `test_el_historial_individual_solo_contiene_al_estudiante_consultado` |
| Estadísticas por caso en el alcance del docente | Cumple | `test_el_autor_del_caso_no_accede_a_la_sesion_de_otro_docente` |
| CSV y JSON con los mismos permisos y filtros | Cumple en 13 combinaciones de filtros (estudiantes e intentos), con 404 para otro docente en ambos | `test_csv_y_json_aplican_los_mismos_filtros_y_permisos` |
| Nulas ≠ cero | Cumple (ya cubierto) | `test_notas_nulas_no_se_promedian_como_cero`, `test_exportaciones_csv_correctas_y_sin_datos_secretos` |
| Escalas distintas normalizadas | Cumple. Casos de escala 5 y 10: cada uno en su escala y espacio normalizado al 75.00 % | `test_escalas_distintas_se_normalizan_en_el_espacio` |
| Los reportes no modifican datos | Cumple (ya cubierto, ahora también para las escrituras rechazadas) | `test_ningun_reporte_modifica_informacion_academica`, `test_las_rutas_de_reportes_solo_admiten_lectura` |
| Fórmulas tras espacios o caracteres de control | **Defecto real, corregido** | Ver abajo |

**Defecto CSV.** `texto_seguro` solo ignoraba los espacios ASCII iniciales. Antes de la corrección, 7 de 8 valores se exportaban sin neutralizar: `"\x00=1"`, `"\x0b=1"`, `"\x0c=1"`, `" =1"`, `"​=1"`, `"﻿=1"` y `"\x1f@x"`.

**Corrección:** ahora se ignora toda secuencia inicial de caracteres Unicode de las categorías `Zs`, `Zl` y `Zp` (espacios), `Cc` (control) y `Cf` (formato invisible) antes de buscar el indicador. El valor original se conserva y solo se antepone `'`; el texto normal (`" Ana"`, `"2026-2"`) no cambia.

Pruebas:
- 12 casos unitarios nuevos.
- `test_exportacion_neutraliza_formulas_tras_caracteres_invisibles`, con nombres y títulos de escenario guardados en PostgreSQL y exportados en `estudiantes`, `intentos` y `preguntas`.

### Resultado de la revisión

| | Antes | Después |
|---|---:|---:|
| Pruebas aprobadas | 1798 | **1815** (17 nuevas: 12 unitarias y 5 de integración) |
| Cobertura de `app/` | 99,19 % | **99,19 %** |
| Cobertura del módulo 7 | 99,73 % | **99,74 %** |

## Migraciones

| Verificación | Resultado |
|---|---|
| `alembic heads` | `0011_notificaciones_eventos (head)`, único |
| `alembic upgrade head` | Correcto |
| `alembic check` | `No new upgrade operations detected.` |
| Ciclo `downgrade base` / `upgrade head` de la suite | Correcto |

## Entorno y reproducción

| Herramienta | Versión |
|---|---|
| Python | 3.14.8 |
| Pytest / pytest-cov | 9.2.0 / 7.1.0 |
| PostgreSQL | Contenedor desechable `inter_nos_pg_test` (`postgres:17-alpine`, `--tmpfs`) en `127.0.0.1:55432` |
| Correo | Mailpit `inter_nos_mailpit` (`axllent/mailpit:v1.20.0`) en `127.0.0.1:1025`/`8025`. Ningún mensaje salió a Internet. |

Los datos son ficticios: los crean las pruebas, con correos `@universidad.edu.co` generados.

```bash
export TEST_DATABASE_URL="postgresql+psycopg://simulador_test:solo_pruebas_local@127.0.0.1:55432/simulador_psicologia_test"
export MAILPIT_SMTP_PORT=1025 MAILPIT_API_URL=http://127.0.0.1:8025   # opcional
export REPORTES_EVIDENCIA_DIR=../docs/evidencias/modulo_7              # opcional: guarda la medición de rendimiento
pytest tests/unit
pytest tests/integration
pytest
pytest --cov=app --cov-report=term-missing --cov-report=html
```

Las unitarias también se ejecutaron apuntando a un puerto sin servidor (`127.0.0.1:1`): **1015 aprobadas**, lo que confirma que no se conectan a PostgreSQL.
