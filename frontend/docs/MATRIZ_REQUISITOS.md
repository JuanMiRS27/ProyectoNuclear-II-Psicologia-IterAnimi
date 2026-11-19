# Matriz de requisitos del frontend

Fuente de los requisitos: **PT-DCP-01 Plan y Casos de Prueba** (`docs/PT-DCP-01_Plan_y_Casos_de_Prueba_Iter_Amini.docx`), que
define 36 casos de uso (CU1–CU36). El repositorio no tiene otro documento de requisitos con identificadores; los que pide el
encargo de rediseño y no están en ese plan se marcan como **(encargo)**.

Evidencia:

- **N** = verificado en navegador contra la API real (backend FastAPI + PostgreSQL local), 18–19/11/2026.
- **A** = verificado con llamadas directas a la API real.
- **T** = cubierto por pruebas automáticas del frontend (`src/test`).
- **—** = no verificado de punta a punta en este trabajo.

| Requisito | Rol | Pantalla | Soporte de API | Brecha / decisión | Evidencia |
|---|---|---|---|---|---|
| CU1 Inicio de sesión del personal | Docente, admin | `/ingresar` (con contraseña) | `POST /auth/login`, `GET /auth/me` | El rol lo decide el servidor; un token vencido lleva al acceso con aviso | N, T |
| CU2 Gestión de docentes | Admin | `/admin/usuarios` (crear, editar) | `POST /users/teachers`, `PATCH /users/{id}` | — | N (crear) |
| CU3 Cambio de contraseña | Docente, admin | `/docente/cuenta`, `/admin/cuenta` | `PATCH /auth/password` | El servidor invalida todos los tokens: se cierra la sesión y se explica | — |
| CU4 Estado y permisos de usuarios | Admin | `/admin/usuarios` | `PATCH /users/{id}/status`, `/case-permission` | No se ofrece desactivar a administradores (el backend lo protege) | N (permiso de casos) |
| CU5 Gestión de espacios académicos | Admin (crear), docente (ver activos) | `/admin/aulas`, `/docente/aulas` | `/academic-spaces` | «Aula» = espacio académico | N |
| CU6 Creación de casos | Docente con permiso | `/docente/casos/nuevo` (en blanco) | `POST /cases` | — | N |
| CU7 Contenido del caso | Docente con permiso | `/docente/casos/:id` (editor) | escenarios, preguntas, opciones y reorden | Editor por piezas; cada cambio vuelve a leer el caso del servidor | N (añadir escena, decisión, opciones; eliminar opción) |
| CU8 Rúbrica | Docente con permiso | `/docente/casos/:id` (editor) | `/rubric`, `/rubric/criteria` | La suma de pesos mostrada es orientativa; la valida el servidor | N |
| CU9 Validación y publicación | Docente | `/docente/casos/:id` | `/validate`, `/publish` | Se muestran los errores del servidor tal cual | N |
| CU10 Archivado | Docente | `/docente/casos/:id` | `/archive` | Confirmación con la consecuencia | — |
| CU11 Importación y exportación CaseDSL | Docente | `/docente/casos/nuevo?modo=importar`, botón Exportar | `/cases/full`, `/dsl` | — | N (importar) |
| CU12 Programación de sesiones | Docente | `/docente/aulas/:id/programar` | `POST /sessions` | — | N (3 sesiones) |
| CU13 Inicio y finalización | Docente | `/docente/sesiones/:id`, agenda | `/start`, `/finish` | Solo se muestran las acciones válidas para el estado | N |
| CU14 Convocatoria | Docente | Convocados | `/convocations` | — | N |
| CU15 Códigos e intentos | Docente | Convocados (ver, regenerar, intentos, retirar) | `/code`, `/regenerate-code`, `/attempts`, `DELETE` | — | N (ver código) |
| CU16 Ingreso del estudiante | Estudiante | `/ingresar` (con código) | `/auth/student/login` y `/results-login` | Con 403 se prueba el acceso de resultados con el mismo código | N, T |
| CU17 Cierre automático | Sistema | — | worker `session_expiration` | Sin pantalla (proceso del servidor) | — |
| CU18 Inicio de un intento | Estudiante | Inicio y Mi sesión | `POST /student/sessions/{id}/participations` | Confirmación porque consume un intento | N |
| CU19 Resolución del cuestionario | Estudiante | `/estudiante/caso/:id` | `questionnaire`, `PUT answers` | Seleccionar ≠ confirmar; sin doble envío; reanudación | N, T |
| CU20 Finalización de un intento | Estudiante | Revisión final del simulador | `/finish` | — | N |
| CU21 Expiración de intentos | Sistema / estudiante | Cuenta atrás y cierre | estado del intento | El cierre lo decide el servidor; la cuenta atrás solo informa | N (intento cerrado por tiempo) |
| CU22 Procesamiento de evaluaciones | Docente | Resultados | `/evaluations/process` | — | N |
| CU23 Recalificación | Docente | Evaluación del intento | `/evaluation/recalculate` | Se ofrece solo si la nota registrada no coincide con la calculada | — |
| CU24 Retroalimentación del docente | Docente | Evaluación del intento | `PATCH /feedback` | — | N |
| CU25 Resultados del estudiante | Estudiante | Resultados, Retroalimentación | `/student/results[/:id]` | Evaluados frente a en revisión; comentario del docente separado del resumen automático | N, T |
| CU26 Notificación de convocatorias | Sistema | — | worker de notificaciones | Sin pantalla propia | — |
| CU27 Avisos de cambios | Sistema → estudiante | Avisos | `/notifications` | Requiere el worker; en las pruebas no corría y la lista quedó vacía | — |
| CU28 Avisos de resultados | Sistema → estudiante | Avisos | `/notifications` | Igual que CU27 | — |
| CU29 Consulta de notificaciones | Estudiante | `/estudiante/avisos`, inicio | `/notifications`, `/read` | Docentes y administración no tienen avisos en el modelo actual | N (vacío) |
| CU30 Entregas de correo | Admin | `/admin/entregas` | `/notification-deliveries`, `/retry` | — | N (vacío) |
| CU31 Resumen de sesión | Docente | Seguimiento, cabecera de sesión | `/reports/summary` | — | N |
| CU32 Reporte de estudiantes | Docente | Convocados (condición e intentos) | `/reports/students` | — | N |
| CU33 Estadísticas de notas | Docente | Seguimiento | `/reports/grades` | — | N |
| CU34 Desempeño por criterio y pregunta | Docente | Seguimiento | `/reports/criteria`, `/questions` | — | N |
| CU35 Exportación CSV | Docente | Seguimiento, detalle del aula | `/reports/export` | No se probó el clic de descarga en el navegador | — |
| CU36 Reportes académicos | Docente | Panel, Sesiones, detalle del aula | `/reports/my-sessions`, `/academic-spaces/{id}/reports` | — | N |
| Portal estudiantil transversal (encargo) | Estudiante | Inicio, Mi aula, Mi sesión, Resultados, Retroalimentación | Token por convocatoria | **Decisión del responsable: sin cambios de identidad.** El portal muestra una convocatoria; «Mi aula» es el aula de esa sesión, no una matrícula | N |
| Privacidad entre estudiantes (encargo) | Estudiante | — | 404 y 403 del servidor | Comprobado con dos estudiantes | A |
| Denegación entre roles (encargo) | Todos | Pantalla «No tienes acceso» | 401 y 403 del servidor | — | N, A, T |
| Refresco de rutas internas (encargo) | Todos | — | SPA con `index.html` | Sin peticiones antes del token ni cargas infinitas | N |
| Móvil (encargo) | Todos | Todas | — | 375 px sin desbordamiento; en el simulador se reduce el escenario y no el texto | N |

## Cambio de backend asociado

`GET /student/sessions/{id}` y `GET /student/results` incluyen ahora `espacio_academico {nombre, periodo}`. Es un cambio
aditivo y de solo lectura, dentro del mismo alcance del token. Lo cubren `tests/test_sessions_student_access.py` y
`tests/unit/test_modulo_5_servicios.py`.
