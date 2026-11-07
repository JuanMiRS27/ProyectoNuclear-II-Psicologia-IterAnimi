# Reporte de pruebas — Módulo 6: Notificaciones y Eventos

**Proyecto:** Proyecto Nuclear II — Inter Nos
**Ejecución registrada:** 7 de noviembre de 2026, rama `modulo-6-notificaciones-eventos`, creada desde `main` local en `35c2d88` (cambios aún sin confirmar)
**Rutas:** relativas a `backend/`. Complementa, sin reemplazarlos, a [`REPORTE_PRUEBAS_MODULOS_1_4.md`](REPORTE_PRUEBAS_MODULOS_1_4.md) y [`REPORTE_PRUEBAS_MODULO_5.md`](REPORTE_PRUEBAS_MODULO_5.md).

| Resumen | Valor |
|---|---|
| Pruebas antes del módulo 6 (`35c2d88`, worktree limpio) | 1480 (778 unitarias y 702 restantes), todas aprobadas; cobertura 99,56 % |
| Pruebas nuevas | **182**: 131 unitarias, 45 de integración, 2 de extremo a extremo con SMTP real (Mailpit) y 4 de regresión |
| Total final | **1662** con Mailpit (909 unitarias, 287 en `tests/integration/` y 466 de regresión) |
| Aprobadas / falladas / omitidas | **1662 / 0 / 0** con Mailpit; **1660 / 0 / 2** sin Mailpit (las 2 de SMTP real se omiten) |
| Cobertura de `app/` (líneas y ramas) | **99,09 %** |
| Cobertura del módulo 6 (`app/modules/notifications/`, `app/workers/notifications/`, `app/core/outbox.py`) | **97,27 %** |
| Revisión final previa al commit | +27 pruebas sobre las 1635 de la primera entrega; ver "Revisión final" |

## Entorno

| Herramienta | Versión |
|---|---|
| Python | 3.14.8 |
| Pytest / pytest-cov / Coverage | 9.2.0 / 7.1.0 / 7.17.0 |
| PostgreSQL | Contenedor `postgres:17-alpine` desechable (`inter_nos_pg_test`, `--tmpfs`), `127.0.0.1:55432` |
| Correo | `AdaptadorCorreoPruebas` y un SMTP simulado; para el extremo a extremo, **Mailpit `axllent/mailpit:v1.20.0`** en `127.0.0.1:1025`/`8025`. **Ningún correo salió hacia Internet.** |

## Pruebas nuevas

| Archivo | Tipo | Pruebas | Qué cubre |
|---|---|---:|---|
| `tests/unit/test_modulo_6.py` | Unitaria (sin PostgreSQL ni SMTP) | 131 | **Observer:** registro, distribución, varios observadores, tipos distintos, eventos desconocidos, desuscripción, propagación de fallos, composición con responsabilidad compartida y reglas de ambos observadores (eventos obsoletos, códigos regenerados, revocación "cuando corresponda", reprogramación, casos A y B, sin calificar, revocadas, idempotencia). **Adapter:** contrato común, `MensajeCorreo` (inyección de encabezados, destinatario único, asunto), traducción a MIME, STARTTLS verificado, TLS implícito, errores temporales y permanentes sin filtrar secretos, configuración inválida, URL de acceso. **Plantillas:** convocatoria, cambios, código nuevo, resultados sin nota, retroalimentación solo interna, escapado HTML, ningún código ni nota en los avisos guardados. **Procesadores:** outbox, datos prohibidos, reintentos con espera progresiva, intentos agotados, revalidación de entregas, caminos de error del envío y CLI del worker |
| `tests/integration/test_modulo_6_api.py` | Integración (PostgreSQL real) | 45 | Outbox en la transacción de la operación; rollback sin eventos; entrega del código vigente (y búsqueda del código en las tres tablas); regeneración antes y después del envío; revocación antes y después; reactivación; reprogramación; resultados en los casos A y B y antes del cierre; recalificación idéntica y con cambio; retroalimentación visible y diferida; cierre que cancela invitaciones; eventos obsoletos; notificaciones internas, lectura idempotente y aislamiento entre estudiantes y frente al docente; autenticación; administración de entregas; reintentos; intentos agotados; idempotencia del worker; tres workers concurrentes; reserva vencida tras una caída; fallo de observador y recuperación; envío desactivado; revocación y regeneración concurrentes detectadas al enviar |
| `tests/test_notifications_regression.py` | Regresión | 4 | Migración `0011` reversible sin perder datos académicos; el publicador posterior al commit del módulo 3 sigue funcionando y el outbox va dentro de la transacción; sin el módulo 6 configurado no se registra nada; cerrar un intento no genera avisos |

| `tests/integration/test_modulo_6_smtp_mailpit.py` | Extremo a extremo con SMTP real (Mailpit local) | 2 | Entrega real comprobada en Mailpit y en PostgreSQL; fallo de conexión SMTP con reintento y recuperación |

## Revisión final previa al commit

### 1. Prueba SMTP real con Mailpit

| Paso | Resultado |
|---|---|
| Servidor SMTP local y aislado | Contenedor `inter_nos_mailpit`, puertos ligados solo a `127.0.0.1` |
| `NOTIFICATIONS_EMAIL_ENABLED=true` temporal | Configurado en la prueba (con `monkeypatch`), solo hacia `127.0.0.1`, sin credenciales; la fábrica real construye `AdaptadorCorreoSMTP` |
| Base desechable y estudiantes ficticios | `inter_nos_pg_test`; estudiantes creados por la prueba; códigos generados en esa base |
| Convocatoria y outbox | 3 `CONVOCATORIA_CREADA` pendientes en `evento_outbox` |
| Observer, entrega y worker | Una pasada de `ejecutar_una_vez`: 3 eventos procesados y 3 correos enviados |
| Recepción en Mailpit | 3 mensajes, cada uno con **un único destinatario** y sin direcciones de los demás convocados |
| Contenido | Remitente, asunto `Inter Nos: Convocatoria a una sesión académica — Conformidad en el aula`, programación, tiempo máximo, lugar, correo institucional, **URL de acceso** y **código vigente**; `Message-ID` = `entrega-<id>@dominio` |
| Persistencia | Las 3 entregas en **ENVIADA**, con `intentos = 1`, `enviada_en` y sin error; el código no aparece en ninguna tabla |
| Fallo de conexión | Puerto local cerrado: entregas **PENDIENTE**, `intentos = 1`, error seguro `Fallo de red o de protocolo SMTP (ConnectionRefusedError).`, nada en Mailpit. Al volver el servidor y pasar la espera: **ENVIADA** con `intentos = 2` |

No fue necesario modificar el adaptador. Evidencias, con el código redactado, en [`docs/evidencias/modulo_6/`](evidencias/modulo_6/):

- `mailpit_mensaje.json`: mensaje tal como lo recibió Mailpit (cabeceras y texto).
- `entregas_enviadas.json`: filas de `entrega_correo` tras el envío.
- `entregas_tras_fallo_smtp.json`: filas tras el fallo de conexión.

La hora del mensaje (`03:00 (UTC-05:00)`) corresponde al reloj fijo de las pruebas (08:00 UTC).

### 2. Caducidad de entregas pendientes

**Defecto real encontrado y corregido.** Las invitaciones solo comprobaban que la sesión no hubiera finalizado. Se habría enviado un código después del límite de ingreso del módulo 3, cuando ya no permite iniciar una participación.

La corrección es una regla única, `services/vigencia.py`, que aplican el observador y el envío:
- Un ingreso nuevo cabe hasta `limite_ingreso` y antes de `fin`.
- Después del límite, el código solo es útil para quien puede reingresar porque tiene un intento EN_PROGRESO con tiempo. Esta parte reutiliza `ReingresoConParticipacionActiva` del módulo 4.

**Mejora en las reprogramaciones:**
- El aviso indica qué cambió.
- El correo muestra los datos vigentes al enviarse y sale solo si el estudiante ya recibió la invitación.
- Un cambio posterior cancela el aviso anterior que aún no se había enviado.

| Caso (entregas creadas con el envío desactivado) | Resultado | Prueba |
|---|---|---|
| Convocatoria válida antes del inicio | Se envía al activar el correo | `test_pendiente_valida_antes_del_inicio_se_envia_al_activar` |
| Plazo de ingreso vencido | CANCELADA: "El plazo de ingreso terminó: la invitación ya no permite participar." | `test_invitacion_con_plazo_de_ingreso_vencido_se_cancela` |
| Código regenerado tras el plazo | Solo lo recibe quien tiene un intento en curso (reingreso) | `test_codigo_regenerado_tras_el_plazo_solo_llega_a_quien_puede_reingresar` |
| Sesión finalizada | CANCELADA: "La sesión finalizó antes del envío." | `test_sesion_finalizada_mientras_estaba_pendiente` |
| Convocatoria revocada | CANCELADA, sin el código en la base | `test_convocatoria_revocada_mientras_estaba_pendiente` |
| Código regenerado después de crear la entrega | La invitación queda CANCELADA y solo se envía el código nuevo | `test_codigo_regenerado_despues_de_crear_la_entrega` |
| Reprogramada antes de procesar la invitación | Una sola invitación con los datos vigentes; aviso interno "Cambió: ..." sin correo redundante | `test_reprogramada_antes_de_procesar_la_invitacion` |
| Varios cambios pendientes | Un único correo, con los datos vigentes; el anterior queda "superado" | `test_varios_cambios_pendientes_envian_un_solo_aviso_vigente` |

Unitarias añadidas: el límite exacto (el instante del límite está permitido), un segundo después, la invitación futura, el reingreso, la revocación y los mensajes que identifican el cambio.

`test_intentos_agotados_quedan_fallidos` (propia del módulo 6) avanzaba el reloj 5 horas, más allá del límite de ingreso. Con la regla nueva la entrega se cancelaba en lugar de fallar. Ahora avanza exactamente la espera progresiva, dentro del plazo.

### 3. Privacidad de la administración de entregas

**Sin defectos.** El código ya cumplía y se añadieron pruebas que lo demuestran:

- `test_administracion_de_entregas_no_expone_secretos` busca en las respuestas de listado, reintento, 409 y 404, en los logs capturados (nivel DEBUG) y en las tres tablas: los códigos de autorización, la contraseña SMTP, `CONVOCATION_CODE_ENCRYPTION_KEY`, `JWT_SECRET_KEY` y los JWT de administrador y docente. No aparece ninguno. Además comprueba el conjunto exacto de campos (sin dirección de correo, asunto ni cuerpo) y que los errores son genéricos.
- `test_administracion_de_entregas_rechaza_a_no_administradores`, para cinco actores: anónimo (401), docente (403), estudiante con token `access` (403), token estudiantil (401) y token de resultados (401).

## Pruebas existentes ajustadas

`tests/test_evaluations_regression.py::test_el_modulo_5_no_agrega_migraciones` (del módulo 5) exigía que el head fuera `0010`. Con la migración `0011` del módulo 6 fallaba por diseño. Se ajustó conservando su intención: que el módulo 5 no añadió migraciones, es decir, que la `0011` sigue directamente a la `0010`. No se modificó ninguna otra prueba.

## Fallos encontrados y corregidos durante el desarrollo

| Fallo | Causa | Corrección |
|---|---|---|
| Primera línea base: 2 fallos y 90,70 % | Se lanzó mientras ya se añadían archivos nuevos, así que no era una línea base válida | Se repitió en un worktree limpio de `35c2d88`: 1480 aprobadas, 99,56 % |
| 3 pruebas de integración propias | Expectativas erróneas: un evento procesado tras el cierre no crea invitaciones, el orden de entregas con igual `creada_en` no es determinista y la reserva simulada ya estaba vencida | Se corrigieron las pruebas (el código se comportaba como se esperaba) y se añadió la prueba del evento obsoleto |
| Cancelación en el momento del envío sin cubrir | Todas las cancelaciones de prueba ocurrían en los observadores | Prueba de un cambio de estado concurrente detectado al enviar |

## Migraciones

| Verificación | Resultado |
|---|---|
| `alembic heads` | `0011_notificaciones_eventos (head)`, único |
| `alembic upgrade head` | Correcto |
| `alembic check` | `No new upgrade operations detected.` |
| `downgrade 0010_evaluacion_tras_cierre` y `upgrade head` | Correcto; la regresión comprueba que se conservan las convocatorias |

## Reproducción (Git Bash, desde `backend/`)

```bash
export TEST_DATABASE_URL="postgresql+psycopg://simulador_test:solo_pruebas_local@127.0.0.1:55432/simulador_psicologia_test"
export DATABASE_URL="postgresql+psycopg://simulador_test:solo_pruebas_local@127.0.0.1:55432/no_usada_dev"
pytest tests/unit
pytest tests/integration
pytest
pytest --cov=app --cov-report=term-missing --cov-report=html
```

El contenedor se crea como indica el reporte del módulo 5 (lanzando `docker run --tmpfs` desde PowerShell).

## Limitaciones de la medición

- **La cobertura global es 99,09 %** (antes del módulo 6: 99,56 %). Las 20 líneas sin cubrir del módulo 6 son de tres tipos:
  - El bucle infinito `ejecutar_periodicamente` del worker.
  - Ramas defensivas: excepciones inesperadas de la base de datos al finalizar, una entrega que desaparece entre la reclamación y el cierre, o datos de un evento sin `convocatoria_id`.
  - Algunas ramas del adaptador SMTP (encabezados adicionales y cierre de la conexión).
- **SMTP real solo con Mailpit local:** el adaptador se probó de extremo a extremo con Mailpit, sin TLS porque es localhost. STARTTLS y TLS implícito se verificaron con un SMTP simulado (contexto con verificación de certificado y nombre de host), no contra un servidor institucional real.
- **Las 2 pruebas de Mailpit se omiten** si no se definen `MAILPIT_SMTP_PORT` y `MAILPIT_API_URL`; la suite normal no depende de un servidor de correo.
- **Concurrencia:** se probó con tres workers simultáneos sobre una misma sesión, no con carga sostenida.
- **"Exactamente una vez" no se mide:** SMTP no lo garantiza. Las pruebas verifican la idempotencia de lo que el sistema controla: eventos, avisos y entregas.
