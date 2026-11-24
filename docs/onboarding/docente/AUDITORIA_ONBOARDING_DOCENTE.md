# Auditoría funcional · Onboarding docente (ITAN-ONB-DOC-01)

> Archivo auxiliar. **No forma parte de la guía dirigida al docente.**
> Fecha: 20 de noviembre de 2026 · Rama: `frontend-iter-animi` · Fuente principal: código de `frontend/src`.
> Verificación en ejecución: frontend local (`http://127.0.0.1:5173`), backend FastAPI local (`:8000`) y PostgreSQL de desarrollo, con la cuenta de demostración **Docente Demo** que facilitó el responsable del proyecto. Las credenciales no aparecen en ningún entregable.

## 1. Método

1. Se leyeron todas las vistas, hooks y servicios del rol docente (`app/routes/teacher.tsx`, `modules/teacher`, `modules/academic`, `modules/cases`, `modules/evaluation`, `modules/auth`, `lib/navigation.ts`, `lib/session-rules.ts`, `services/*`).
2. Se contrastaron con `frontend/docs/MATRIZ_REQUISITOS.md` y `frontend/docs/PAQUETES_VISUALES.md`.
3. Se recorrió el portal con Chrome automatizado (`puppeteer-core`, instalado solo en un directorio temporal fuera del proyecto) y se capturaron 34 pantallas.
4. **Política de solo lectura:** se abrieron pantallas y diálogos y se cerraron sin confirmar. Las únicas acciones ejecutadas fueron:
   - **Validar** el borrador «Caso X» (consulta las reglas; no cambia el caso).
   - Enviar vacío el formulario **Programar sesión** (el cliente lo rechaza antes de llamar al servidor).
   - En el editor visual, **Usar a** un personaje del sistema, asignar una reacción y **Probar reacción** (todo es estado local del navegador de captura; no se pulsó «Guardar borrador»).

   En esta primera pasada no se crearon, modificaron ni eliminaron datos. No se pulsaron «Abrir sesión», «Finalizar sesión», «Evaluar intentos cerrados», «Publicar», «Archivar», «Retirar» ni «Regenerar».
5. **Segunda pasada (20/11/2026, con aprobación expresa del responsable):** para las dos capturas que faltaban se crearon datos de prueba desde la propia interfaz:
   - Un borrador temporal «Caso de prueba (onboarding)» con rúbrica de dos criterios (60 % y 40 %, niveles Alto, Medio y Bajo). Tras capturarlo **se eliminó** con «Eliminar borrador». «Caso X» no se tocó.
   - Una sesión de «Conformidad grupal» en «Psicología Social, grupo 1», **sin iniciar**, programada para el 21/11/2026 de 10:00 a 12:00, 30 min por intento, lugar «Salón 204», **sin convocados** (no genera correos). La API no permite borrar sesiones, así que **sigue en la base** como sesión próxima de la cuenta demo; si no se abre, el cierre automático la finalizará 24 h después de su fin.
6. En la captura del diálogo «Ver código» se **difuminó el código** (credencial del estudiante) mediante un estilo inyectado solo en el navegador de captura.

## 2. Funcionalidades verificadas (IMPLEMENTADAS)

| # | Funcionalidad (nombre en la interfaz) | Ubicación | Verificación (código + ejecución) | Evidencia |
|---|---|---|---|---|
| 1 | Ingreso «Con contraseña» | `/ingresar` | `LoginView.tsx`, `SessionProvider.tsx`; ingreso real con la cuenta demo | `01-acceso.png`, `02-acceso-validacion.png` |
| 2 | Cierre de sesión y cierre por vencimiento | Barra lateral «Cerrar sesión» | `Sidebar.tsx`, temporizador en `SessionProvider.tsx` | `03-panel-docente.png` |
| 3 | Tema Claro / Oscuro / Sistema | Barra lateral y Mi cuenta | `ThemeSwitcher.tsx` | `03`, `32` |
| 4 | Panel docente: cifras, «Para hacer ahora», accesos, agenda | `/docente` | `TeacherDashboardView.tsx` | `03`, `04` |
| 5 | Aulas activas y buscador (>6 aulas) | `/docente/aulas` | `ClassroomsView.tsx` | `05-aulas.png` |
| 6 | Detalle del aula, casos usados, CSV | `/docente/aulas/:id` | `ClassroomDetailView.tsx` | `06-detalle-aula.png` |
| 7 | Lista de casos con filtros y búsqueda | `/docente/casos` | `CasesListView.tsx` | `07-casos.png` |
| 8 | Nuevo caso «Empezar en blanco» | `/docente/casos/nuevo` | `CaseCreateView.tsx` | `08-nuevo-caso-blanco.png` |
| 9 | Nuevo caso «Importar CaseDSL» | `/docente/casos/nuevo?modo=importar` | `CaseCreateView.tsx` | `09-nuevo-caso-importar.png` |
| 10 | Editor de escenas, decisiones y opciones | Caso en borrador › Contenido académico | `ScenarioEditor.tsx` | `10-borrador-editor.png` |
| 11 | Rúbrica (escala, criterios, niveles) | Caso en borrador › Rúbrica | `RubricEditor.tsx`; rúbrica creada en un borrador temporal | `10`, `12`, `35`, `36` |
| 12 | Validar / Publicar con lista de errores | Cabecera del caso | `CaseDetailView.tsx`; «Validar» ejecutado | `11-borrador-validacion.png` |
| 13 | Exportar CaseDSL, Archivar, Eliminar borrador | Cabecera / pie del caso | `CaseDetailView.tsx` (no ejecutados) | `10`, `12` |
| 14 | Personaje: personajes del sistema y «Mis personajes» | Caso › Personaje y reacciones | `CharacterPanel.tsx`, `CharacterLibrary.tsx` | `13`, `14`, `15` |
| 15 | Reacciones por decisión (expresión inicial, reacción, movimiento) | Ídem | `ReactionsPanel.tsx` | `16-visual-reacciones.png` |
| 16 | Vista previa jugable | Ídem | `ScenePreview.tsx`; reacción probada | `17-visual-vista-previa.png` |
| 17 | Guardar / Exportar / Importar / Descartar borrador visual | Barra del editor visual | `VisualEditor.tsx`, `use-visual.ts` | `18-visual-barra.png` |
| 18 | Programar sesión y sus validaciones | `/docente/aulas/:id/programar` | `ScheduleSessionView.tsx`; validación ejecutada | `19`, `20` |
| 19 | Lista de sesiones con filtros y búsqueda | `/docente/sesiones` | `SessionsListView.tsx` | `21-sesiones.png` |
| 20 | Abrir / Finalizar sesión, Editar programación / lugar y mensaje | Detalle de sesión | `SessionDetailView.tsx`; sesión de prueba sin iniciar | `22`, `26`, `27`, `37`, `38` |
| 21 | Convocar, Ver código, Más intentos, Regenerar código, Retirar | Pestaña Convocados | `ConvocationsPanel.tsx` | `22`–`25` |
| 22 | Resultados: Evaluar intentos cerrados, tabla, ausencias | Pestaña Resultados | `ResultsPanel.tsx` | `28-sesion-finalizada-resultados.png` |
| 23 | Evaluación de un intento, comentario, registrar nota calculada | `/docente/sesiones/:id/intentos/:pid` | `TeacherEvaluationView.tsx`, `FeedbackEditor.tsx` | `29-evaluacion-intento.png` |
| 24 | Seguimiento: participación, notas, criterios, decisiones, CSV | Pestaña Seguimiento | `TrackingPanel.tsx` | `30-seguimiento.png` |
| 25 | Cola «Evaluación» | `/docente/evaluacion` | `EvaluationQueueView.tsx` | `31-cola-evaluacion.png` |
| 26 | Mi cuenta: datos, apariencia, cambiar contraseña | `/docente/cuenta` | `AccountView.tsx` | `32-mi-cuenta.png` |
| 27 | Navegación móvil (cajón lateral) | Cualquier ruta en móvil | `PlatformLayout.tsx` | `33`, `34` |

## 3. Funcionalidades PARCIALES

| Funcionalidad | Limitación | Tratamiento en la guía |
|---|---|---|
| Envío del código por correo al convocar | Depende de la configuración de correo del servidor; la propia interfaz sugiere «Ver código» si no está activo. | Se documenta «Ver código» como alternativa. |
| Borrador visual | Se guarda solo en el navegador (IndexedDB) de esa cuenta y ese equipo. | Advertencia explícita. |
| Distribución del paquete visual a estudiantes | Requiere exportar el `.zip`, instalarlo con `npm run visual:install` y desplegar: paso técnico fuera de la interfaz. «Publicar el caso no publica su paquete visual.» | Se explica como coordinación con el equipo técnico; sin pasos técnicos. |
| Personajes del sistema | Arte marcado como provisional en la interfaz. | Nota breve. |
| Seguimiento en vivo | Sin actualización automática (`refetchOnWindowFocus: false`, sin `refetchInterval`); hay que recargar o cambiar de pestaña. | Consejo en la sección de sesiones. |
| Cierre automático de sesiones | Proceso del servidor (CU17) sin pantalla. | Se menciona en el texto de la advertencia del plazo. |
| Descarga CSV | Implementada; la matriz indica que el clic de descarga no se verificó en navegador. Tampoco se pulsó en esta auditoría. | Se documenta como disponible. |
| Cambio de contraseña (CU3), Archivar (CU10), Registrar nota calculada (CU23) | Implementados en código; no verificados de punta a punta (ni en la matriz ni aquí, para no alterar datos). | Se documentan según el código. |

## 4. Funcionalidades NO IMPLEMENTADAS para el docente

| Funcionalidad | Evidencia | Tratamiento |
|---|---|---|
| Crear, editar o desactivar aulas | `ClassroomsView` solo lista; la creación está en `/admin/aulas`. | Se indica que lo hace la administración. |
| Crear cuentas de estudiante / gestionar estudiantes | Solo en `/admin/usuarios`; el docente convoca por correo cuentas existentes. | Se indica que lo hace la administración. |
| Matrícula o listas permanentes de estudiantes por aula | No existe en el modelo («no es una matrícula»). | No se menciona como función. |
| Recuperación de contraseña | No existe en `LoginView`. | FAQ: contactar a la administración. |
| Avisos / notificaciones para el docente | «Docentes y administración no tienen avisos en el modelo actual» (matriz). | No se menciona. |
| Actualización en tiempo real | Ver §3. | Consejo de recargar. |
| Diálogos línea a línea, globos de texto, voz, música, fondos por escena, varios personajes simultáneos | `SimulatorStage`, `NarrativePanel`, `use-stage-expression.ts`. El «diálogo» es la narración (contexto) de la escena más el enunciado de la decisión. | Se aclara en la sección del entrevistado virtual. |
| Comportamiento emocional automático o IA | Las expresiones cambian solo por la reacción asignada a cada opción, tras confirmar el servidor. | Se aclara. |
| Calificación manual de la nota | La nota la calcula el servidor con la rúbrica; el docente procesa, registra la calculada y comenta. | Se aclara. |
| Duplicar casos | No existe. Alternativa real: exportar CaseDSL e importarlo. | Se menciona como alternativa. |

## 5. Capturas obtenidas (`evidencias/`)

| Archivo | Pantalla | Uso en la guía |
|---|---|---|
| `01-acceso.png` | Ingresar | Fig. 1 |
| `02-acceso-validacion.png` | Ingresar con validaciones | Fig. 2 |
| `03-panel-docente.png` | Panel docente | Fig. 3 |
| `04-panel-docente-completo.png` | Panel docente completo | Referencia |
| `05-aulas.png` | Aulas | Fig. 19 (recorte f-aulas) |
| `06-detalle-aula.png` | Detalle del aula | Fig. 20 (recorte f-detalle-aula) |
| `07-casos.png` | Casos | Fig. 6 (recorte f-casos) |
| `08-nuevo-caso-blanco.png` | Nuevo caso en blanco | Fig. 7 (recorte f-nuevo-caso) |
| `09-nuevo-caso-importar.png` | Importar CaseDSL | Referencia |
| `10-borrador-editor.png` | Editor de contenido (borrador) | Figs. 8, 9 (recortes f-editor, f-rubrica-vacia) |
| `11-borrador-validacion.png` | Errores de validación | Fig. 12 (recorte f-validacion) |
| `12-caso-publicado.png` | Caso publicado (lectura, rúbrica) | Fig. 13 (recorte f-caso-publicado) |
| `13-visual-mis-personajes.png` | Editor visual: Mis personajes | Referencia |
| `13b-visual-mis-personajes-panel.png` | Editor visual: panel Mis personajes | Fig. 15 |
| `14-visual-biblioteca.png` | Personajes del sistema | Fig. 14 (recorte f-biblioteca) |
| `15-visual-personaje-en-uso.png` | Editor visual completo | Referencia |
| `16-visual-reacciones.png` | Reacciones por decisión | Fig. 16 |
| `17-visual-vista-previa.png` | Vista previa jugable | Fig. 17 |
| `18-visual-barra.png` | Barra de guardado del editor visual | Fig. 18 |
| `19-programar-sesion.png` | Programar sesión | Fig. 21 (recorte f-programar) |
| `20-programar-validacion.png` | Programar sesión con validaciones | Referencia |
| `21-sesiones.png` | Sesiones | Fig. 28 (recorte f-sesiones) |
| `22-sesion-en-curso-convocados.png` | Sesión en curso, Convocados | Fig. 24 (recorte f-convocados) |
| `23-dialogo-ver-codigo.png` | Ver código (difuminado) | Fig. 22 |
| `24-dialogo-mas-intentos.png` | Más intentos | Fig. 25 |
| `25-dialogo-regenerar.png` | Regenerar código | Referencia |
| `26-dialogo-finalizar.png` | Finalizar sesión | Fig. 27 |
| `27-dialogo-editar-lugar.png` | Editar lugar y mensaje | Referencia |
| `28-sesion-finalizada-resultados.png` | Resultados | Fig. 29 (recorte f-resultados) |
| `29-evaluacion-intento.png` | Evaluación de un intento | Figs. 32, 33, 34 (recortes f-evaluacion-resumen, f-evaluacion-decisiones, f-evaluacion-comentario) |
| `30-seguimiento.png` | Seguimiento | Figs. 30, 31 (recortes f-seguimiento-1, f-seguimiento-2) |
| `31-cola-evaluacion.png` | Evaluación (cola) | Fig. 35 (recorte f-cola) |
| `32-mi-cuenta.png` | Mi cuenta | Fig. 5 (recorte f-mi-cuenta) |
| `33-movil-panel.png` | Panel en móvil | Referencia |
| `34-movil-menu.png` | Menú móvil | Fig. 4 |
| `35-rubrica-criterio-en-edicion.png` | Nuevo criterio con niveles (borrador temporal) | Fig. 10 |
| `36-rubrica-con-criterios.png` | Rúbrica con dos criterios y suma de pesos | Fig. 11 |
| `37-sesion-sin-iniciar.png` | Sesión Sin iniciar (Abrir sesión desactivado) | Fig. 23 (recorte f-sesion-sin-iniciar) |
| `38-dialogo-editar-programacion.png` | Editar programación | Fig. 26 |

Los recortes de `evidencias/recortes/` son encuadres de estas mismas capturas (sin la barra lateral), usados para maquetar. La portada (`recursos/portada.png`) es un recurso gráfico, no una evidencia.

## 6. Capturas que faltan

| Pantalla | Motivo |
|---|---|
| Opción en edición (texto, «Es una respuesta correcta», justificación) | Abrir el formulario es seguro, pero el borrador de prueba solo tiene una opción sin contenido didáctico; se priorizó la captura del editor completo. |
| Aviso «Evaluación procesada.» tras evaluar | Requiere ejecutar el procesamiento (escribe en la base). |
| Aviso «La nota registrada no coincide con la calculada» | No hay intentos con discrepancia en los datos demo. |

Ninguna de estas pantallas es imprescindible: la guía las describe en texto. Ya no quedan marcadores `[CAPTURA PENDIENTE]` en el documento.

## 7. Limitaciones de esta auditoría

- Los datos de demostración son reducidos (un aula, dos casos, una escena por caso), por lo que algunas pantallas muestran listas cortas.
- Salvo los datos de prueba de §1.5, no se verificaron funciones que escriben en la base de datos (procesar evaluación, publicar, archivar, cambiar contraseña, registrar nota calculada, descargas CSV).
- El tema oscuro no se capturó; la guía usa capturas en tema claro.
- Las fuentes del producto (Manrope, Source Serif 4) no suelen estar instaladas en los equipos; el documento Word usa Segoe UI y Georgia como equivalentes disponibles en Windows.
