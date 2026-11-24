# Auditoría funcional · Onboarding estudiante (ITAN-ONB-EST-01)

> Archivo para el equipo de desarrollo. **No forma parte de la guía del estudiante.**
> Fecha: 22 de noviembre de 2026 · Rama `frontend-iter-animi` · Árbol de trabajo local, con cambios sin confirmar en `frontend/`.

## 1. Método y entorno

1. **Referencia editorial.** Se renderizaron las 57 páginas de `Onboarding Docente.pdf` y se revisó su comienzo (portada, índice y primeros capítulos); el resto se conocía por su generador, del que se reutilizaron paleta, tipografías, portada, encabezados, procedimientos, avisos y numeración de figuras. El contenido es nuevo.
2. **Código.** Frontend: `modules/auth`, `modules/student`, `modules/simulator`, `modules/evaluation/ResultBreakdown`, `providers/SessionProvider`, `lib/student-session-adapters`, `lib/visual`. Backend: `sessions`, `participations`, `evaluations` y `notifications`.
3. **Ejecución aislada.** El recorrido del estudiante escribe datos (intentos y respuestas), así que no se hizo sobre la base de desarrollo:
   - `inter_nos_pg_dev` se arrancó solo para leerla con `pg_dump` y se detuvo de nuevo.
   - La copia se cargó en un contenedor desechable (en memoria, puerto 55439), ya eliminado.
   - Se usó el mismo código del backend con claves temporales y el frontend compilado fuera del proyecto.
   - Las sesiones, los intentos, las evaluaciones, los comentarios y un segundo caso de ejemplo («El efecto espectador») solo existieron en esa copia. **El comentario docente de las capturas se redactó para esta guía.**
4. **Credenciales.** Se usaron las cuentas ficticias de demostración. Las capturas no muestran códigos válidos: los reales aparecen como puntos (ocultos con un estilo del navegador de captura) y los visibles (`CODI-GOEJ-EMPL`) son inventados.

## 2. Reglas verificadas

«Ejecutado» significa observado en la copia aislada; «Código», leído en el fuente sin ejecutar.

| Regla | Comportamiento | Verificación | Fuente |
|---|---|---|---|
| Ingreso | Correo + código de 12 caracteres. Tolera guiones, espacios y minúsculas | Ejecutado | `sessions/schemas`, `acceso_service.py` |
| Código incorrecto o regenerado | 401 con el mismo mensaje | Ejecutado | `acceso_service.py` |
| Sesión sin abrir | 403 «La sesión aún no ha sido iniciada por el docente.» | Ejecutado | `sessions/states` |
| Plazo de ingreso | Mitad de la ventana programada (instante incluido) | Ejecutado (instante exacto: código) | `Sesion.limite_ingreso` |
| Horario terminado | 403 «La ventana programada de la sesión terminó…» | Ejecutado | `sessions/states` |
| Bloqueo | 5 fallos por correo o 30 por IP en 15 min (configurable). Se mantiene con el código correcto | Ejecutado (mensaje); el resto, código | `security/limitador.py` |
| Convocatoria retirada | Expulsa, cierra el intento y responde 403 al ingresar | Ejecutado (cierre del intento: código) | `acceso_service.py`, `integracion_sesiones.py` |
| Código regenerado | Expulsa. El intento abierto continúa con el código nuevo | Ejecutado | `acceso_service.py` |
| Intentos | 1 por defecto, ampliable por el docente | Ejecutado | `Convocatoria.intentos_autorizados` |
| Tiempo del intento | `inicio + tiempo_max_min`, reloj del servidor. Puede sobrepasar el fin programado | Ejecutado | `policies/temporizador.py` |
| Reingreso | Con intento abierto y con tiempo se puede volver, incluso tras el plazo y el fin programado | Ejecutado | `ReingresoConParticipacionActiva` |
| Guardado | Solo al confirmar. Seleccionar no envía nada | Ejecutado | `SimulatorPlayView.tsx` |
| Cambio de respuesta | Permitido hasta entregar o agotar el tiempo | Ejecutado | `respuesta_service.py` |
| Saltar decisiones | La interfaz no lo permite hacia adelante | Código | `DecisionActions` |
| Tiempo agotado | Cierre automático y pantalla «Tu intento se cerró» | Ejecutado | `use-countdown`, `AttemptClosedView` |
| Sin conexión del navegador | El envío queda en «Guardando…» y continúa solo al reconectar | Ejecutado | TanStack Query (modo en línea) |
| Fallo del envío | Conserva la selección y permite reintentar | Ejecutado (petición cortada en el navegador) | `SimulatorPlayView.tsx` |
| Sesión finalizada | Expulsa. El mismo código abre los resultados | Ejecutado | `SessionProvider.loginStudent` |
| Resultados | Sesión finalizada **y** evaluación registrada; si no, «En revisión» | Ejecutado | `consulta_resultados_service.py` |
| Nota | Suma de puntaje × peso. Verificado 3,40 = 5 × 0,6 + 1 × 0,4 | Ejecutado | `calculadora_rubrica.py` |
| Sin calificar | Cierre administrativo sin respuestas guardadas | Ejecutado | `strategies/incompleta.py` |
| Reacciones | Solo tras la confirmación del servidor; no se reconstruyen al reanudar | Ejecutado | `use-stage-expression.ts` |
| Sin paquete visual | Silueta sin rostro | Ejecutado | `CharacterSprite.tsx` |

## 3. Funcionalidades del estudiante

| Funcionalidad | Estado | Ruta o componente |
|---|---|---|
| Ingreso con código y paso automático a resultados | IMPLEMENTADA | `/ingresar` · `LoginView` |
| Inicio, Mi aula, Mi sesión | IMPLEMENTADA | `/estudiante`, `/estudiante/aula`, `/estudiante/sesion` |
| Iniciar, continuar, responder, revisar y entregar | IMPLEMENTADA | `/estudiante/caso/:id` · `SimulatorPlayView` |
| Cierre del intento | IMPLEMENTADA | `/estudiante/caso/:id/cierre` · `AttemptClosedView` |
| Resultados, detalle y retroalimentación | IMPLEMENTADA | `/estudiante/resultados`, `/estudiante/retroalimentacion` |
| Tema claro, oscuro o sistema; uso en móvil | IMPLEMENTADA | `ThemeSwitcher`, `PlatformLayout` |
| Personaje ilustrado y reacciones | PARCIALMENTE IMPLEMENTADA: exige un paquete instalado en el frontend; hoy solo lo tiene «Conformidad grupal», con arte provisional | `lib/visual/static-packages.ts` |
| Avisos | PARCIALMENTE IMPLEMENTADA: requieren ejecutar el proceso de notificaciones (en la copia se ejecutó una vez, sin correo) | `/estudiante/avisos` · `app.workers.notifications` |
| Código por correo | PARCIALMENTE IMPLEMENTADA: desactivado por defecto (`NOTIFICATIONS_EMAIL_ENABLED=false`) | `notifications` |
| Contraseña, registro o recuperación de código | NO IMPLEMENTADA | — |
| Ver varias convocatorias juntas | NO IMPLEMENTADA | — |
| Pausar el tiempo | NO IMPLEMENTADA | — |
| Conversar con el personaje, IA, voz, música, diálogos línea a línea | NO IMPLEMENTADA | — |
| Responder o reclamar un comentario | NO IMPLEMENTADA | — |

## 4. Procedimientos no comprobados

| Elemento | Motivo |
|---|---|
| Recepción real del correo con el código | No se configuró ningún servidor de correo |
| «La cuenta del estudiante está desactivada.» | Solo código: exige la cuenta de administración |
| Vencimiento natural del acceso (300 min; 60 min en resultados, por defecto) | Solo código: no se esperó |
| Botón «Ver el estado de mi intento» tras un 409 | No se presentó: el reloj detectó antes el cierre |
| Cierre automático de sesiones a las 24 h | Solo código |
| Transición de la reacción al cambiar de escena | Solo código: el caso de dos escenas no tiene paquete visual |
| Sprites propios del docente | Solo hay un paquete instalado y usa un personaje del sistema |
| Navegadores distintos de Chrome y teléfonos físicos | No se probaron; el móvil se emuló a 390 px. La guía no nombra navegadores |

## 5. Hallazgos para el equipo (no se modificó nada)

1. **Aviso de error que persiste.** Tras un fallo de envío, pulsar «Anterior» mantiene el mensaje rojo en la otra decisión (`21-respuesta-guardada.png`).
2. **Motivo genérico al expulsar.** Retiro, código regenerado y sesión finalizada muestran «Tu sesión expiró.», sin la causa real, y la pantalla vuelve a «Con contraseña».
3. **Título adelantado.** Con la sesión finalizada, Inicio usa siempre «Tus resultados ya están aquí», aunque el intento siga «En revisión» (código: `StudentDashboardView`).
4. **Título fijo.** «Tu próxima decisión te espera» aparece también en «Completado» y en «Plazo de ingreso cerrado» (`28`, `44`).
5. **Textos del servidor.** «Respuesta incorrecta.» convive con «Respuesta no acertada», y el resumen usa punto decimal («3.40», «0.00 %») mientras la interfaz usa coma.
6. **Códigos tras finalizar.** El servidor todavía permite consultar el código, pero la interfaz docente oculta esa acción y regenerarlo responde 409. Un estudiante que lo pierde no puede ver sus resultados por esa vía.
7. **Marca.** Las plantillas de correo usan «Inter Nos», no «Iter Animi».

## 6. Capturas

Las capturas originales están en `evidencias/` y los recortes y composiciones usados, en `evidencias/recortes/`. Los recortes (`r-*.png`) solo cambian el encuadre y el margen. Las composiciones (`c-*.png`) reúnen varias capturas reales con rótulos; la guía lo indica en su leyenda, salvo la de móvil, cuya leyenda enumera las tres pantallas. `recursos/portada.png` es un recurso gráfico, no una evidencia.

| Figura | Archivo |
|---|---|
| 1 | `recortes/r-formulario-lleno.png` |
| 2 | `recortes/r-sesion-no-iniciada.png` |
| 3 | `recortes/r-expirada.png` |
| 4 | `recortes/r-inicio.png` |
| 5 | `recortes/r-mi-sesion.png` |
| 6 | `17-decision-1.png` |
| 7 | `recortes/c-movil.png` |
| 8 | `recortes/r-confirmar-inicio-dialogo.png` |
| 9 | `16-prologo.png` |
| 10 | `recortes/r-seleccion.png` |
| 11 | `19-reaccion-decision-2.png` |
| 12 | `recortes/c-barra.png` |
| 13 | `42-escena-1-silueta.png` |
| 14 | `43-escena-2-silueta.png` |
| 15 | `recortes/r-guardada.png` |
| 16 | `25-revision-final.png` |
| 17 | `recortes/r-confirmar-entrega.png` |
| 18 | `recortes/r-cierre.png` |
| 19 | `recortes/c-antes-despues.png` |
| 20 | `recortes/c-expresiones.png` |
| 21 | `recortes/r-hero-plazo.png` |
| 22 | `recortes/r-cierre-tiempo.png` |
| 23 | `recortes/r-hero-otro.png` |
| 24 | `recortes/r-hero-en-curso.png` |
| 25 | `recortes/r-error.png` |
| 26 | `recortes/r-resultados-en-curso.png` |
| 27 | `recortes/r-inicio-resultados.png` |
| 28 | `recortes/r-evaluados.png` |
| 29 | `recortes/r-en-revision.png` |
| 30 | `recortes/r-avisos.png` |
| 31 | `recortes/r-nota.png` |
| 32 | `recortes/r-criterios.png` |
| 33 | `recortes/r-decisiones.png` |
| 34 | `recortes/r-retro.png` |

**Referencia:** las demás imágenes de `evidencias/` documentan estados adicionales y no aparecen en la guía o son el origen de un recorte.

**Capturas pendientes:** ninguna para los procedimientos documentados; no hay marcadores `[CAPTURA PENDIENTE]`. No se obtuvieron el correo de convocatoria ni el mensaje de cuenta desactivada; la guía los describe en texto.

## 7. Diferencias con el onboarding docente

- Las pantallas docentes se capturaron el 20/11. Después cambiaron `ThemeSwitcher.tsx` y `theme.css`: el selector de tema muestra ahora **iconos** y la pantalla de ingreso llega hasta los bordes. Las capturas docentes de ingreso y menú difieren ligeramente de la versión actual.
- La guía docente habla de un «plazo de ingreso»; aquí se precisa que es **la mitad de la ventana programada**.
- `ANALISIS_ONBOARDING.md` indica que un 401 durante el caso muestra «Ver el estado de mi intento». En la práctica, un 401 cierra la sesión y lleva a **Ingresar**.
- El aviso «Buena práctica docente» pasa a «Para tu aprendizaje». «Cómo leer esta guía» va junto al índice.
- El onboarding docente no se modificó.

## 8. Limitaciones

- «Conformidad grupal» tiene una sola escena; el paso entre escenas se documentó con un caso creado en la copia y mostrado sin personaje.
- El PDF se exportó desde Word. El documento usa Segoe UI y Georgia, como el docente, en lugar de las fuentes del producto.
- Las fechas visibles en las capturas corresponden al día de elaboración.
