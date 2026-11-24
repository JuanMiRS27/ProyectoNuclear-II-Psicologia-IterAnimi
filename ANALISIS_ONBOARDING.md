# Análisis funcional para el onboarding de Iter Animi

> **Propósito.** Este documento sirve de base para dos guías de usuario independientes: una para **docentes** y otra para **estudiantes**.
> **Fuente.** El código real del frontend (`frontend/src`, rama `frontend-iter-animi`, noviembre de 2026). Como apoyo se consultaron `frontend/docs/MATRIZ_REQUISITOS.md`, `frontend/docs/PAQUETES_VISUALES.md` y los recursos de `frontend/public/`.
> **Alcance.** Es un análisis de solo lectura: no se cambió ningún archivo del proyecto. Todo texto entre «comillas latinas» se copió literalmente de la interfaz.

**Leyenda de estado**

| Marca | Significado |
|---|---|
| ✅ Implementado | Existe en la interfaz y funciona contra la API. |
| 🟡 Parcial | Existe, pero con una limitación que el usuario debe conocer (depende de un proceso externo, de un paso técnico o de una decisión de diseño). |
| ⛔ No disponible | No existe en la interfaz. Se menciona para que las guías no lo prometan. |

---

## 1. Arquitectura y organización del frontend

### 1.1 Tecnología

| Aspecto | Implementación |
|---|---|
| Base | React 19, TypeScript, Vite 8 y SPA con `react-router` 8 (`createBrowserRouter`). |
| Estado remoto | TanStack Query 5. `staleTime` de 15 s, **sin recarga al volver a la pestaña** (`refetchOnWindowFocus: false`) y **sin consultas periódicas** (no hay `refetchInterval`). Los errores 4xx no se reintentan; los demás, hasta 2 veces. |
| API | Un único cliente HTTP (`services/http-client.ts`). La base es `VITE_API_BASE_URL` o `/api/v1`. El **tiempo límite es de 20 s** y los mensajes de error están en español según el código HTTP. |
| Sesión | El token se guarda en `localStorage` (`iter-animi.session`), con una copia en memoria por si el almacenamiento está bloqueado. La sesión **se cierra sola al vencer** el token y también ante cualquier 401. |
| Tema | Claro, Oscuro o Sistema. Se guarda solo en el navegador y se cambia desde la barra lateral, desde la pantalla de acceso o desde «Mi cuenta» (personal). |
| Tipografía | Manrope (interfaz) y Source Serif 4 (narración del simulador), las dos locales. |
| Paquetes visuales | Viven solo en el frontend: el borrador en IndexedDB y el paquete instalado en `public/visual-packages/`. Los personajes del sistema están en `public/sprite-library/`. |

### 1.2 Estructura de carpetas

```
frontend/src/
├─ app/            router.tsx y routes/ (auth, student, teacher, admin), con carga diferida por portal
├─ layouts/        AuthLayout, PlatformLayout (barra lateral + cajón móvil), SimulatorLayout (inmersivo) y guards
├─ modules/
│  ├─ auth/        LoginView y AccountView
│  ├─ teacher/     Panel, Sesiones, Detalle de sesión (Convocados, Resultados, Seguimiento) y cola de Evaluación
│  ├─ academic/    Aulas, Detalle de aula, Programar sesión y SessionAgenda
│  ├─ cases/       Lista, Crear/Importar, Detalle, editor/ (escenas, rúbrica) y visual/ (personaje y reacciones)
│  ├─ evaluation/  Evaluación de un intento, ResultBreakdown y FeedbackEditor
│  ├─ simulator/   Simulador tipo novela visual (escenario, sprite, narración, decisiones, revisión y cierre)
│  ├─ student/     Inicio, Mi aula, Mi sesión, Resultados, Retroalimentación y Avisos
│  └─ admin/       Usuarios, Aulas y Entregas de correo (fuera del alcance de las guías)
├─ hooks/          use-academic, use-cases, use-student, use-visual, use-countdown…
├─ lib/            navigation, labels, session-rules, student-session-adapters y visual/ (paquete, runtime, biblioteca)
├─ services/       una capa por recurso de la API
└─ components/     design-system (estados, tablas, layout) y ui (Button, Dialog, Field, Tabs, ThemeSwitcher)
```

### 1.3 Roles y tipos de sesión

El **servidor** decide el rol. El frontend solo organiza la navegación (`lib/navigation.ts`) y los permisos reales los aplica siempre la API.

| Tipo de token | Cómo se obtiene | Zona | Alcance |
|---|---|---|---|
| `staff`, rol DOCENTE | Correo + contraseña | `/docente` | Sus sesiones, los casos y las aulas activas. |
| `staff`, rol ADMINISTRADOR | Correo + contraseña | `/admin` | Fuera del alcance de las guías. |
| `student` | Correo + **código de convocatoria**, con la sesión EN CURSO | `/estudiante` y el simulador | **Una sola convocatoria** y su sesión. |
| `results` | Correo + **el mismo código**, con la sesión FINALIZADA | `/estudiante` (solo lectura) | Resultados y retroalimentación de esa convocatoria. |

Un docente que tenga `puede_crear_casos = false` solo puede **consultar y exportar** los casos. El permiso lo concede la administración.

### 1.4 Guardas y navegación transversal

- Si se entra a una ruta privada sin sesión, la aplicación redirige a `/ingresar` y, después de ingresar, **vuelve a la ruta pedida** solo si pertenece a la zona del rol.
- Si se entra a la zona de otro rol, aparece la pantalla «No tienes acceso a esta sección», con el botón «Ir a mi inicio».
- Una ruta inexistente muestra «Esta página no existe», con el botón «Ir al inicio».
- La barra lateral agrupa las opciones por secciones y muestra el tema, las iniciales y el nombre (o el correo del estudiante), además de «Cerrar sesión». En móvil se abre como cajón con el botón «Abrir menú».
- El enlace «Saltar al contenido» está disponible en todas las páginas del portal.

---

## 2. Mapa de rutas y pantallas

### 2.1 Acceso (público)

| Ruta | Pantalla | Estado |
|---|---|---|
| `/ingresar` | Acceso único: «Con contraseña» y «Con código de acceso» | ✅ |
| `/` | Redirige al inicio del rol o al acceso | ✅ |

### 2.2 Docente (`/docente`)

| Ruta | Pantalla | Menú | Estado |
|---|---|---|---|
| `/docente` | Panel docente | Principal › Panel docente | ✅ |
| `/docente/aulas` | Aulas | Académico › Aulas | ✅ |
| `/docente/aulas/:spaceId` | Detalle del aula | — | ✅ |
| `/docente/aulas/:spaceId/programar` | Programar sesión | — | ✅ |
| `/docente/sesiones` | Sesiones (filtros: Todas, En curso, Próximas, Finalizadas) | Académico › Sesiones | ✅ |
| `/docente/sesiones/:sessionId?tab=convocados\|resultados\|seguimiento` | Detalle de sesión con 3 pestañas | — | ✅ |
| `/docente/sesiones/:sessionId/intentos/:participationId` | Evaluación de un intento | — | ✅ |
| `/docente/casos` | Casos (filtros: Todos, Publicados, Borradores, Archivados) | Académico › Casos | ✅ |
| `/docente/casos/nuevo?modo=borrador\|importar` | Nuevo caso | — | ✅ |
| `/docente/casos/:caseId?vista=contenido\|personaje` | Detalle o editor del caso | — | ✅ |
| `/docente/evaluacion` | Cola de evaluación | Evaluación y seguimiento › Evaluación | ✅ |
| `/docente/cuenta` | Mi cuenta | Cuenta › Mi cuenta | ✅ |

### 2.3 Estudiante (`/estudiante`)

| Ruta | Pantalla | Menú | Estado |
|---|---|---|---|
| `/estudiante` | Inicio | Mi actividad › Inicio | ✅ |
| `/estudiante/aula` | Mi aula | Mi actividad › Mi aula | ✅ |
| `/estudiante/sesion` | Mi sesión | Mi actividad › Mi sesión | ✅ |
| `/estudiante/caso/:participationId` | **Simulador** (vista inmersiva, sin barra lateral) | — | ✅ |
| `/estudiante/caso/:participationId/cierre` | Estado del intento al salir | — | ✅ |
| `/estudiante/resultados` | Resultados | Seguimiento › Resultados | ✅ (solo con la sesión finalizada) |
| `/estudiante/resultados/:participationId` | Detalle de un resultado | — | ✅ (solo con la sesión finalizada) |
| `/estudiante/retroalimentacion` | Retroalimentación | Seguimiento › Retroalimentación | ✅ (solo con la sesión finalizada) |
| `/estudiante/avisos` | Avisos | Seguimiento › Avisos | 🟡 (depende del proceso de notificaciones del servidor) |

---

## 3. Acceso y cuenta (común a los dos roles)

### 3.1 Pantalla «Ingresar» (`LoginView`)

En la parte izquierda hay una presentación («Decidir con criterio. Aprender con sentido.») y en la derecha, el formulario. El selector de tema está arriba a la derecha.

| Elemento | Detalle |
|---|---|
| Selector | «Con contraseña» (personal) / «Con código de acceso» (estudiante). Al cambiar de opción se borra el segundo campo. |
| Correo institucional | Es obligatorio y se valida su formato. |
| Contraseña / Código de acceso | Pista del código: «Son 12 caracteres. Puedes escribirlos con o sin guiones. Si la sesión ya terminó, este mismo código abre tus resultados.» |
| Botón | «Ingresar», que cambia a «Ingresando…» mientras se procesa. |

**Lógica del código del estudiante.** Primero se intenta el ingreso a la sesión en curso. Si el servidor responde 403 (por ejemplo, porque la sesión ya finalizó), se intenta **automáticamente** el ingreso a resultados con el mismo código. Si eso también falla, se muestra el motivo original del servidor.

**Mensajes de validación y error** (los que la guía debe explicar):

| Situación | Mensaje |
|---|---|
| Correo vacío | «Escribe tu correo institucional.» |
| Correo con formato inválido | «El correo no tiene un formato válido.» |
| Secreto vacío | «Escribe tu contraseña.» / «Escribe el código de acceso de tu convocatoria.» |
| 401 | «El correo o la contraseña no son correctos.» / «El correo o el código de acceso no son correctos.» |
| 429 | «Demasiados intentos fallidos. Vuelve a intentarlo en N minutos.» |
| 422 | «Revisa el formato del correo.» |
| 403 | El servidor explica el motivo (cuenta desactivada, sesión no iniciada, plazo vencido…). |
| Sin red | «No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.» |
| Más de 20 s sin respuesta | «El servidor tardó demasiado en responder. Inténtalo de nuevo en unos momentos.» |
| Aviso: sesión vencida | «Tu sesión expiró. Vuelve a ingresar para continuar.» |
| Aviso: contraseña cambiada | «Contraseña actualizada. Por seguridad se cerraron tus sesiones: ingresa con la nueva contraseña.» |

⛔ **No disponible:** recuperar la contraseña («olvidé mi contraseña»), registrarse por cuenta propia o elegir el rol al ingresar.

### 3.2 «Mi cuenta» (solo personal) (`AccountView`)

- Datos de solo lectura: Nombre, Correo, Rol, «Casos» (solo docentes: «Puede crear y editar casos» o «Solo lectura de sus casos») y Código institucional.
- **Apariencia:** Claro, Oscuro o Sistema («Se guarda solo en este navegador»).
- **Cambiar contraseña:** pide la contraseña actual, la nueva y su repetición. Validaciones:
  - «Escribe tu contraseña actual.»
  - «La nueva contraseña debe tener entre 8 y 128 caracteres.»
  - «La nueva contraseña debe ser distinta de la actual.»
  - «Las contraseñas no coinciden.»

  Al confirmarse, **se cierran todas las sesiones**, incluida la actual, y el usuario vuelve al acceso con el aviso correspondiente.
- ⛔ El estudiante no tiene «Mi cuenta» ni contraseña: entra siempre con el código de cada convocatoria.

---

## 4. Inventario de funcionalidades: DOCENTE

### 4.1 Panel docente (`TeacherDashboardView`)

| Bloque | Contenido | Estado |
|---|---|---|
| Saludo | «Hola, {nombre}», la fecha larga y el botón «Programar sesión» (lleva a Aulas). | ✅ |
| Cifras | en curso, próximas, por evaluar y finalizadas. | ✅ |
| «Para hacer ahora» | Tareas generadas a partir del estado real: **Abrir «caso»** (sesión dentro de su ventana y sin iniciar), **«caso» está en curso** (cuántos resuelven y cuántos han entrado) y **Evaluar «caso»** (intentos cerrados sin nota). Cada tarea tiene su botón. | ✅ |
| Accesos | Explorar aulas, Biblioteca de casos y Evaluaciones. | ✅ |
| Agenda | «Próximas sesiones» (hasta 5) y «Finalizadas recientemente» (hasta 4, con el enlace «Ver todas»). | ✅ |
| Vacío | «Aún no tienes sesiones», con el botón «Elegir un aula». | ✅ |

### 4.2 Aulas

| Funcionalidad | Detalle | Estado |
|---|---|---|
| Listar las aulas **activas** | Tarjetas con el periodo, el número de «sesiones tuyas» y la etiqueta «en curso». Aparece un buscador cuando hay más de 6 aulas. | ✅ |
| Crear o editar aulas | **Solo lo hace la administración** («Las aulas las crea la administración del simulador»). | ⛔ para el docente |
| Detalle del aula | Muestra **solo las sesiones del docente**, con las cifras (sesiones, intentos, evaluaciones y promedio sobre la escala), las secciones «En curso y próximas» y «Finalizadas», y la tabla «Casos usados en esta aula». | ✅ |
| Exportar el aula en CSV | Botón «CSV», visible si hay sesiones registradas. | ✅ (la descarga no se verificó en el navegador, según la matriz) |
| Programar desde el aula | Botón «Programar sesión», solo si el aula está activa. | ✅ |

### 4.3 Programar sesión (`ScheduleSessionView`)

| Campo | Reglas |
|---|---|
| Caso | Solo casos **PUBLICADOS**. Si no hay ninguno, aparece el aviso «No tienes casos publicados.» con un enlace a Casos. Al elegirlo, se propone su tiempo estimado. |
| Inicio / Finalización | Por defecto empieza «ahora» y termina 2 h después, en la hora local del equipo. |
| Tiempo máximo por intento | Entero, 1 o más, y como máximo el tiempo estimado del caso o 240 min. |
| Lugar o modalidad | Opcional, hasta 150 caracteres. |
| Mensaje para los estudiantes | Opcional, hasta 5000 caracteres. Se muestra al estudiante como «Mensaje de tu docente». |
| Estudiantes convocados | Correos separados por línea o coma. Se muestra el contador y la pista «Deben ser cuentas de estudiante activas. También puedes convocar después.» |

**Validaciones:**
- «Elige el caso que resolverán los estudiantes.»
- «Indica la fecha y hora de inicio/finalización.»
- «La finalización debe ser posterior al inicio.»
- «La finalización debe ser una hora futura.»
- «Indica un tiempo máximo en minutos.»
- «No puede superar el tiempo estimado del caso (N min).»
- «Revisa estos correos: …»

El botón dice «Crear sesión» y cambia a «Creando sesión…». Al terminar, se abre la sesión en la pestaña Convocados con el aviso «Sesión creada.».

> **Mensaje clave para la guía:** «La sesión no se abre sola: deberás abrirla tú a partir de la hora de inicio.»

### 4.4 Sesiones y ciclo de vida

**Estados de una sesión:** «Sin iniciar» → «En curso» → «Finalizada».

| Acción | Cuándo aparece | Detalle | Estado |
|---|---|---|---|
| **Abrir sesión** | SIN_INICIAR y la hora actual está dentro de la ventana [inicio, fin) | Aparece en la cabecera, en la agenda y en el panel. Fuera de la ventana: «Podrás abrirla a partir del …» o «La ventana programada ya terminó; el cierre automático la finalizará.» | ✅ |
| **Editar programación** | SIN_INICIAR | Diálogo con el inicio, el fin, el tiempo (de 1 a 240), el lugar y el mensaje. | ✅ |
| **Editar lugar y mensaje** | EN_CURSO | «Con la sesión en curso solo se pueden cambiar el lugar y el mensaje.» | ✅ |
| **Finalizar sesión** | EN_CURSO | Pide confirmación porque es **irreversible**: se cierran los intentos en curso y después los estudiantes pueden consultar sus resultados. | ✅ |
| Plazo de ingreso | EN_CURSO | Aviso informativo con el límite de ingreso. Cuando vence, aparece una advertencia: nadie puede empezar y el cierre automático actúa 24 h después del fin. | ✅ |
| Cierre automático | Servidor | Es un proceso del servidor (CU17), sin pantalla propia. | 🟡 (no se ve en la UI) |
| Lista de sesiones | — | Pestañas por estado, buscador por caso o aula y columnas Caso, Aula, Estado, Participación y «Con nota» (con la etiqueta «Por evaluar»). | ✅ |

### 4.5 Pestaña «Convocados» (`ConvocationsPanel`)

| Acción | Detalle | Estado |
|---|---|---|
| Convocar estudiantes | Correos separados por coma o salto de línea. Mensajes: «Escribe al menos un correo.» y «Revisa estos correos: …». **Solo si la sesión no está finalizada.** | ✅ |
| Lista de convocados | Nombre, correo, condición (Participó, Pendiente, Ausente, Retirado o «Resolviendo ahora») y «N de M intentos». | ✅ |
| **Ver código** | Muestra el código en bloques de 4 (`XXXX-XXXX-XXXX`) con el botón «Copiar código». Advierte que solo se entregue a ese estudiante. | ✅ |
| **Más intentos** | Pide el total de intentos autorizados (**solo se puede aumentar**, hasta 100) y un motivo de al menos 5 caracteres. | ✅ |
| **Regenerar código** | Pide un motivo. El código anterior **deja de funcionar de inmediato**. Al terminar, muestra el nuevo código. | ✅ |
| **Retirar** | Pide confirmación. El estudiante pierde el acceso y su intento en curso se cierra con lo guardado. Su historial se conserva y se le puede volver a convocar. | ✅ |
| Envío del código por correo | Depende del servidor. El propio aviso lo dice: «Si el envío por correo no está activo en el servidor, usa «Ver código» para entregárselo.» | 🟡 |

### 4.6 Pestaña «Resultados» y evaluación

| Funcionalidad | Detalle | Estado |
|---|---|---|
| Cifras | completados, cerrados sin finalizar, en curso, evaluados y por evaluar. | ✅ |
| **Evaluar intentos cerrados** (CU22) | Procesa todos los intentos cerrados. El resumen dice cuántos se revisaron, con nota nueva, actualizados, sin cambios y sin calificar, y cuántos se omitieron por estar en curso. **Se puede usar antes de finalizar la sesión**, pero los estudiantes solo ven el resultado cuando la sesión está finalizada. | ✅ |
| Tabla de intentos | Estudiante, número de intento, estado (con el motivo de cierre), calificación (con la etiqueta «Nota desactualizada»), nota sobre la escala y el botón «Ver detalle» para los intentos cerrados. | ✅ |
| Ausencias | «Ausencias» si la sesión finalizó, o «Aún no han ingresado» si no. La pantalla aclara que una ausencia «No equivale a una nota de cero.» | ✅ |
| **Evaluación de un intento** | Muestra la nota, la condición, la calificación, el motivo de cierre, los aciertos, errores y respuestas sin responder, y las observaciones. Incluye una tabla por criterio (aciertos, nivel, puntaje y peso), la retroalimentación por decisión (opción elegida y opción esperada con su justificación) y el «Resumen del sistema». | ✅ |
| **Registrar nota calculada** (CU23) | Solo aparece si la nota registrada no coincide con la calculada o si todavía no hay nota. | ✅ (no se verificó de punta a punta) |
| **Comentario para el estudiante** (CU24) | Hasta 5000 caracteres, con un contador. **No cambia la nota.** Si se deja vacío, se quita. El estudiante lo ve cuando la sesión está finalizada. Al guardar aparece «Comentario guardado». | ✅ |
| Cola «Evaluación» | Separa las sesiones «Por evaluar» (con la etiqueta «N intentos sin nota») de las que están «Al día». | ✅ |

### 4.7 Pestaña «Seguimiento» (CU31–CU35)

| Bloque | Contenido | Estado |
|---|---|---|
| Participación | Cuatro tasas en % con su numerador y denominador. Si hay intentos vencidos que todavía no se cerraron, se avisa. | ✅ |
| Notas | Promedio, mediana, mínima, máxima y número de intentos evaluados, más una tabla de distribución por rangos con barras. | ✅ |
| Desempeño por criterio | Aciertos, porcentaje y puntaje medio. Los criterios sin preguntas aparecen como «Sin preguntas asociadas». | ✅ |
| Desempeño por decisión | Aciertos, respuestas no acertadas, sin responder y % de aciertos («No corregible» cuando corresponde). | ✅ |
| Descargar en CSV | Resumen, Estudiantes, Intentos, Criterios y Preguntas. | ✅ (la descarga no se verificó en el navegador) |
| Actualización en vivo | ⛔ No hay actualización periódica: para ver el avance nuevo hay que volver a entrar a la pestaña o recargar la página. | ⛔ |

### 4.8 Casos: lista, creación y ciclo de vida

**Estados de un caso:** «Borrador» → «Publicado» → «Archivado». Un caso publicado **ya no se edita** y uno archivado **no se puede reactivar**.

| Funcionalidad | Detalle | Estado |
|---|---|---|
| Lista de casos | Pestañas por estado y buscador. Columnas: Caso, Estado, Tiempo estimado y Actualizado. El botón «Nuevo caso» solo aparece con permiso. | ✅ |
| Nuevo caso: «Empezar en blanco» (CU6) | Nombre (obligatorio, hasta 200 caracteres), tiempo estimado (de 1 a 240 min, opcional en el borrador y obligatorio para publicar), desarrollo situacional e historia. | ✅ |
| Nuevo caso: «Importar CaseDSL» (CU11) | Se carga un `.json` o se pega el contenido, que debe incluir `"dslVersion": "1.0"`. Si el JSON no es válido: «El contenido no es un JSON válido. Revisa comas, comillas y llaves.» | ✅ |
| Exportar CaseDSL | Está en cualquier estado, también sin permiso de edición. | ✅ |
| **Validar** (CU9) | Muestra «El caso cumple todas las reglas y puede publicarse.» o la lista «El caso todavía no se puede publicar (N).» con los mensajes del servidor. | ✅ |
| **Publicar** (CU9) | Si faltan requisitos, muestra la misma lista de errores. | ✅ |
| **Archivar** (CU10) | Pide confirmación: «Ya no podrás programarlo en nuevas sesiones… No se puede revertir.» | ✅ (no se verificó de punta a punta) |
| **Eliminar borrador** | Pide confirmación: «Se eliminará con todo su contenido. No se puede deshacer.» | ✅ |
| Sin permiso de casos | El docente ve el aviso «Tu cuenta no tiene permiso para modificar casos. Puedes consultarlo y exportarlo.» y el contenido en solo lectura. | ✅ |

### 4.9 Editor del contenido académico (pestaña «Contenido académico», solo en borrador)

| Pieza | Acciones | Notas para el usuario |
|---|---|---|
| Información general | Editar el nombre, el tiempo, el desarrollo situacional y la historia (en un diálogo). | Este texto es el **prólogo** del simulador. |
| Escenas | Añadir (título obligatorio, de hasta 200 caracteres, y contexto o narración), editar, subir, bajar y eliminar (con confirmación; también se borran sus decisiones). | El **contexto** es la narración que el estudiante lee en esa escena. |
| Decisiones | Añadir, editar, reordenar y eliminar (con confirmación). Cada una tiene un enunciado y un criterio de la rúbrica opcional. | «Cada decisión necesita al menos dos opciones, una correcta y una justificación por opción.» |
| Opciones | Añadir y editar (texto, «Es una respuesta correcta» y justificación). | La justificación «El estudiante la verá en su retroalimentación.». Si falta, aparece la etiqueta «Sin justificación». ⚠ **Eliminar una opción no pide confirmación** (es inmediato). |
| Rúbrica | Crear con la escala máxima (por defecto 5.00), guardar la escala y añadir, editar o eliminar criterios (descripción, peso de 0 a 100 y niveles con nombre, valor y «Desde % aciertos»). | Indicador «Suma de pesos: X de 100», que es orientativo (la suma la valida el servidor). «Un criterio necesita al menos dos niveles para que el caso pueda publicarse.» |

Si el caso no está en borrador, el contenido se muestra en solo lectura con las opciones correctas marcadas. La interfaz recuerda que «esto nunca se muestra al estudiante durante el caso».

### 4.10 Editor visual: «Personaje y reacciones» (pestaña `?vista=personaje`)

Esta pestaña está disponible en **cualquier estado del caso** y define cómo se verá la entrevista en el simulador. Tiene **tres zonas**: «Personaje», «Reacciones» y «Vista previa». En móvil se alternan con pestañas.

| Zona o acción | Detalle | Estado |
|---|---|---|
| Nombre visible del entrevistado | Hasta 60 caracteres y opcional. Se muestra sobre el escenario. | ✅ |
| **Personajes del sistema** | Galería de 6 personajes: Samuel, Inés, Julián, Carmen, Ernesto y Rosa (adultos jóvenes, adultos y personas mayores), cada uno con 8 expresiones (Neutral, Feliz, Triste, Enojado, Preocupado, Sorprendido, Incómodo y Reflexivo). Se abre una vista amplia del personaje, se elige con «Usar a {nombre}» y se fija la «Expresión por defecto». | 🟡 El arte es **provisional**, y la interfaz lo advierte. |
| **Mis personajes** (sprites propios) | Expresiones por defecto: Neutral, Inquieto, Incómodo, Reflexivo y Aliviado. Se pueden añadir expresiones (máx. 12), cambiar etiquetas (hasta 40 caracteres), marcar la expresión «Por defecto», usar «Cargar imagen», «Reemplazar» o «Retirar imagen», y eliminar expresiones. Las imágenes deben ser **PNG o WebP de hasta 2 MB**. | ✅ |
| Volver a mis sprites | Si se elige un personaje del sistema, los sprites propios se guardan aparte y se pueden recuperar. | ✅ |
| **Reacciones** | Para cada escena hay una «Expresión inicial». Para cada opción se elige una reacción («Sin cambio» o una expresión) y un movimiento (Fundido, Aparición suave, Respiración sutil o Sin animación). | ✅ |
| Revisión de cambios | Si cambia el texto de una opción o el título de una escena, la asociación queda «Pendiente de revisión» y se confirma con el botón «Confirmar». Las asociaciones que ya no existen se pueden quitar con «Quitarlas del borrador». | ✅ |
| **Vista previa jugable** | Usa los mismos componentes que el simulador. Permite elegir la decisión, el tema de la vista previa (Como la aplicación, Claro u Oscuro), «Probar reacción», «Siguiente decisión» y «Volver al estado inicial». **No crea intentos, no envía respuestas y no modifica notas.** | ✅ |
| Guardar borrador | Se guarda **solo en este navegador** (IndexedDB, por cuenta docente y caso). El estado se indica como «Cambios sin guardar», «Guardado en este navegador el …» o «Aún no hay un borrador guardado». | 🟡 No se sincroniza entre equipos. |
| Exportar / Importar paquete visual | Archivo `.zip` (`paquete-visual-<caso>.zip`). Al importar se comprueba que el paquete sea **del mismo caso** y se pide confirmación antes de reemplazar lo que hay. | ✅ |
| Descartar borrador | Pide confirmación. Solo borra lo guardado en el navegador. | ✅ |
| **Distribución a los estudiantes** | El aviso de la pantalla dice: exportar el paquete, instalarlo con `npm run visual:install` y desplegar. **«Publicar el caso no publica su paquete visual.»** Es un paso técnico que hace quien administra el despliegue, no la interfaz. | 🟡 Requiere un paso técnico fuera de la UI. |

> Las etiquetas de expresión son **dirección narrativa**: la interfaz aclara que no son categorías clínicas ni pistas de acierto, y que las reacciones no indican si una opción es correcta.

---

## 5. Inventario de funcionalidades: ESTUDIANTE

### 5.1 Concepto clave para la guía

El estudiante **no tiene cuenta con contraseña**. Cada **convocatoria** le da un **código personal de 12 caracteres** que sirve:
1. mientras la sesión está **en curso**, para resolver el caso (portal en modo «live»), y
2. cuando la sesión está **finalizada**, para ver sus resultados con el **mismo código** (modo «results»).

El portal muestra **una sola convocatoria**. Si el estudiante tiene otras, debe entrar con el código de cada una («Mi aula» no es una matrícula).

### 5.2 Estados de la convocatoria vistos por el estudiante

El estado se calcula a partir del servidor en `lib/student-session-adapters.ts`.

| Estado | Etiqueta | Acción principal (`StudentPrimaryAction`) |
|---|---|---|
| `disponible` | «Disponible» | El botón «Iniciar caso» (o «Iniciar otro intento») pide confirmación con el aviso «¿Iniciar el caso ahora?»: empieza a correr el tiempo, se consume un intento y el tiempo **no se detiene** aunque se cierre la página. |
| `en_curso` | «En curso» | El botón «Continuar caso» muestra la hora límite y las decisiones respondidas. |
| `completado` | «Completado» | Aviso «Ya resolviste este caso.»: los resultados estarán cuando el docente finalice la sesión y haya que volver a ingresar. |
| `plazo_cerrado` | «Plazo de ingreso cerrado» | Aviso «Ya no es posible iniciar el caso.», con la fecha y la recomendación de contactar al docente. |
| `finalizada` | «Sesión finalizada» | Botón «Ver mis resultados». |

### 5.3 Pantallas del portal

| Pantalla | Contenido | Estado |
|---|---|---|
| **Inicio** | Saludo con el nombre, una tarjeta con la sesión prioritaria (aula, caso, estado, horario, lugar y «Mensaje de tu docente») y su acción principal, las cifras (intentos realizados, autorizados y minutos por intento) y accesos a Mi aula y Mi sesión (o Mis resultados). Al lado están la **Agenda** (inicio, «Último momento para empezar un intento» y fin), los **Avisos recientes** (hasta 4, con la etiqueta «Nuevo») y «Tus intentos» con su medidor (o «Retroalimentación» en modo resultados). | ✅ |
| **Mi aula** | El aula de la sesión, con el aviso de que solo se ve esa convocatoria y un enlace a la sesión o a los resultados. | ✅ |
| **Mi sesión** | La acción principal, el mensaje del docente y «Tus intentos» (número, estado, decisiones respondidas y fecha de inicio). Al lado: aula, lugar, tiempo por intento, «Puedes empezar hasta» e intentos. En modo resultados: «La sesión terminó. Desde aquí solo puedes consultar tus resultados.» | ✅ |
| **Resultados** | Solo en modo resultados. Separa los intentos «Evaluados» (con nota y el botón «Ver resultado») de los que están «En revisión» («Pendiente de revisión»). Si no hubo intentos: «No registraste intentos en esta sesión». | ✅ |
| **Detalle de resultado** | Nota, condición, calificación, cierre, respuestas, «Comentario de tu docente», desempeño por criterio, «Retroalimentación por decisión» («Tu elección» y «Opción esperada» con su justificación) y «Resumen del sistema». | ✅ |
| **Retroalimentación** | Tarjetas con el «Comentario del docente» de cada intento, con un desplegable «Ver el resumen automático del sistema» y el enlace al resultado completo. | ✅ |
| **Avisos** | Avisos de la convocatoria (tipos: Convocatoria, Código regenerado, Cambio de programación, Retiro de la convocatoria, Resultados disponibles, Calificación actualizada y Retroalimentación), con el botón «Marcar como leído». | 🟡 Dependen del proceso de notificaciones del servidor. En las pruebas la lista quedó vacía. |

**Mensajes que aparecen mientras la sesión sigue en curso** (las guías deben anticiparlos):
- Resultados y detalle: «Tus resultados aparecerán cuando termine la sesión».
- Retroalimentación: «Los comentarios llegarán con tus resultados».
- Resultado sin evaluación registrada (409): «Este resultado está pendiente de revisión.»

### 5.4 El simulador: experiencia de novela visual

#### Estructura de la pantalla (`SimulatorPlayView`)

```
┌──────────────────────────────────────────────────────────────┐
│ ‹ Volver a mi sesión   Nombre del caso   Respondidas 2 de 6  ⏱ 12:34 │  ← SimulatorHeader
│ ▓▓▓▓▓▓░░░░░░░░░░ (barra de progreso)                            │
├──────────────────────────────────────────────────────────────┤
│  [Escena 1 de 3 · Título de la escena]                         │  ← SimulatorStage
│                 (sprite del personaje)                          │     fondo + suelo + sprite
│                    [Nombre del personaje]                       │
├──────────────────────────────────────────────────────────────┤
│  Narración de la escena (tipografía serif de lectura)           │  ← NarrativePanel
│  DECISIÓN 2 DE 6 · Enunciado                                    │  ← DecisionPanel
│   (A) Opción…   (B) Opción…   (C) Opción…                       │
│  [Anterior]   «Tu elección se guarda al confirmar.»  [Confirmar respuesta] │ ← SimulatorActions
└──────────────────────────────────────────────────────────────┘
```

#### Secuencia de pasos (`steps.ts`)

1. **Prólogo**, solo si el caso tiene desarrollo situacional o historia («Antes de empezar»). Tiene el botón «Comenzar» y la pista «Lee con calma: el tiempo corre desde que iniciaste el intento.»
2. **Una decisión por paso**, en el orden de escenas y decisiones que define el servidor. La escena muestra su narración y una sola decisión. Si una escena tiene varias decisiones, se repite la misma narración.
3. **Revisión final** («Final del caso · Revisa y entrega»): «Has respondido X de Y decisiones», la lista de decisiones «Quedan sin responder» con el botón «Responder», «Revisar mis respuestas» y «Entregar caso».

#### Reglas de interacción

| Regla | Comportamiento |
|---|---|
| Elegir no es confirmar | Al elegir una opción solo se marca. La respuesta se guarda con «Confirmar respuesta» (que cambia a «Guardando…»). |
| Respuesta ya guardada | Aparece la etiqueta «Respuesta guardada», la pista «Esta respuesta ya está guardada.» y el botón cambia a «Continuar». |
| Avance | Después de confirmar, se pasa a la **siguiente decisión sin responder** o a la revisión. |
| Volver | El botón «Anterior» lleva a la decisión previa, y se puede cambiar una respuesta antes de entregar. |
| Sin doble envío | Mientras se guarda, las opciones y el botón quedan bloqueados. |
| Error al guardar | «… Tu selección se conservó: puedes volver a confirmarla.» Si el intento ya se cerró (409/401), aparece el botón «Ver el estado de mi intento». |
| Reanudación | Al volver a entrar, el simulador sigue en la primera decisión pendiente (o en la revisión), con las respuestas guardadas. |
| Tiempo | Hay una cuenta atrás que se resalta en los últimos 5 min. **El servidor decide el cierre.** Al llegar a cero, la aplicación se sincroniza y lleva a la pantalla de cierre. |
| Entregar | Pide confirmación con «¿Entregar el caso?». Se advierte que las decisiones sin responder cuentan como no respondidas y que **después no se pueden cambiar las respuestas**. |
| Salida | El enlace superior lleva a Inicio, Mi sesión o Mi aula, según desde dónde se entró. Salir no detiene el tiempo. |
| Accesibilidad | El foco va al título de cada paso, las opciones son un grupo de radio con letras A, B, C… y la barra de acciones queda fija abajo en móvil. |

#### Personajes, sprites y emociones en el simulador

| Aspecto | Comportamiento real |
|---|---|
| Origen del personaje | El simulador busca en `public/visual-packages/index.json` un paquete cuyas escenas coincidan con las del cuestionario. Actualmente hay **un paquete instalado** («Conformidad grupal», con el personaje del sistema Inés). |
| Sin paquete o con imagen fallida | Se muestra un **personaje blanco sin rostro** (silueta SVG) y el caso se puede jugar igual. |
| Expresión al entrar en una escena | La «Expresión inicial» de esa escena o, si no tiene, la expresión por defecto. |
| Reacción | **Solo cuando el servidor acepta la respuesta**: elegir una opción no cambia nada y un error tampoco. Si la opción tiene una reacción asignada, el sprite cambia con el movimiento elegido. «Sin cambio» deja la expresión que había. |
| Cambio de escena | La reacción se mantiene unos 1,4 s y después aparece la expresión inicial de la nueva escena, sin bloquear el texto. |
| Reanudación | La última reacción **no se reconstruye**: se muestra la expresión inicial de la escena. |
| Movimiento reducido | Las animaciones son solo CSS y desaparecen con `prefers-reduced-motion`. |
| Nombre | Aparece una placa con el nombre del personaje sobre el escenario, si se definió. |

#### Lo que **no** existe (no prometerlo en las guías) ⛔

- **No hay diálogos línea a línea ni globos de texto del personaje.** El «diálogo» es la narración de la escena (su contexto) más el enunciado de la decisión. No hay avance por clic ni efecto de máquina de escribir («Sin animaciones que obliguen a esperar»).
- No hay fondos distintos por escena (el fondo del escenario es fijo), ni música, sonido o voz.
- No hay varios personajes a la vez en escena: hay un solo entrevistado por caso.
- El estudiante no ve si acertó durante el caso: las reacciones no indican si una opción es correcta.

#### Pantalla de cierre del intento (`AttemptClosedView`)

Muestra «Entregaste el caso» o «Tu intento se cerró», el estado con su motivo («Finalizado por el estudiante», «Se agotó el tiempo», «La convocatoria fue retirada» o «La sesión terminó»), «Intento N de M», las decisiones respondidas, la fecha de cierre y el aviso «Tu resultado aún no está disponible.». Tiene los botones «Volver a mi sesión» e «Ir al inicio». Si el intento sigue en curso, redirige al simulador.

---

## 6. Recorridos paso a paso

### 6.1 Recorrido A del docente: del caso a la evaluación (camino feliz)

| # | Paso | Pantalla | Acción visible |
|---|---|---|---|
| 1 | Ingresar | `/ingresar` | «Con contraseña» → correo + contraseña → «Ingresar» |
| 2 | Revisar el panel | `/docente` | Leer «Para hacer ahora» |
| 3 | Crear el caso | `/docente/casos` → «Nuevo caso» | «Empezar en blanco» → «Crear borrador» (o «Importar CaseDSL» → «Importar como borrador») |
| 4 | Redactar el contenido | `/docente/casos/:id` (Contenido académico) | Información general → «Añadir escena» → «Añadir decisión» → «Añadir opción» (marcar la correcta y escribir la justificación) |
| 5 | Crear la rúbrica | Misma pantalla, sección «Rúbrica» | «Crear rúbrica» → «Añadir criterio» (con peso y al menos 2 niveles) → asignar los criterios a las decisiones |
| 6 | Validar | Cabecera | «Validar» → corregir la lista de errores |
| 7 | Configurar el personaje (opcional) | `?vista=personaje` | Personaje → Reacciones → Vista previa → «Guardar borrador» → «Exportar paquete visual» (y pedir su instalación en el despliegue) |
| 8 | Publicar | Cabecera | «Publicar» |
| 9 | Programar | `/docente/aulas` → aula → «Programar» | Caso, ventana, tiempo, lugar, mensaje y correos → «Crear sesión» |
| 10 | Entregar los códigos | Pestaña Convocados | «Ver código» → «Copiar código» (si el correo no está activo) |
| 11 | Abrir la sesión | Cabecera de la sesión, agenda o panel | «Abrir sesión» (desde la hora de inicio) |
| 12 | Seguir el avance | Convocados o Seguimiento | Revisar la condición de cada estudiante y recargar para actualizar |
| 13 | Finalizar | Cabecera | «Finalizar sesión» → confirmar |
| 14 | Evaluar | Pestaña Resultados | «Evaluar intentos cerrados» |
| 15 | Retroalimentar | «Ver detalle» de un intento | Revisar el desglose → «Guardar comentario» (y, si aparece, «Registrar nota calculada») |
| 16 | Analizar | Pestaña Seguimiento | Revisar los indicadores y descargar los CSV |

### 6.2 Recorrido B del docente: gestión de incidencias durante la sesión

1. Si un estudiante perdió su código, usar **Convocados → «Ver código»**. Si el código pudo filtrarse, usar **«Regenerar código»** con un motivo; el código anterior deja de servir.
2. Si un estudiante necesita repetir, usar **«Más intentos»**: escribir el nuevo total (mayor que el actual) y el motivo.
3. Si alguien fue convocado por error, usar **«Retirar»** y confirmar; su intento en curso se cierra.
4. Si hay que convocar a alguien más, usar **«Convocar estudiantes»** mientras la sesión no esté finalizada.
5. Si hay que cambiar el aula física o el mensaje, usar **«Editar lugar y mensaje»**.
6. Si venció el plazo de ingreso, aparece la advertencia: conviene finalizar la sesión para poder evaluar.

### 6.3 Recorrido C del docente: reprogramar una sesión que no ha empezado

`/docente/sesiones` → pestaña «Próximas» → abrir la sesión → «Editar programación» (inicio, fin, tiempo, lugar y mensaje) → «Guardar cambios».

### 6.4 Recorrido D del docente: docente sin permiso de casos

Puede consultar los casos, exportar el CaseDSL, ver y configurar el editor visual (que es local), programar sesiones con casos publicados y evaluar. Para crear o editar casos debe pedir el permiso a la administración (lo indica la propia interfaz).

### 6.5 Recorrido A del estudiante: resolver un caso

| # | Paso | Pantalla | Acción visible |
|---|---|---|---|
| 1 | Recibir el código | Correo o entrega del docente | Código de 12 caracteres |
| 2 | Ingresar | `/ingresar` | «Con código de acceso» → correo + código → «Ingresar» |
| 3 | Conocer la sesión | `/estudiante` | Leer el mensaje del docente, la agenda y los intentos |
| 4 | Iniciar | Inicio o Mi sesión | «Iniciar caso» → confirmar en «¿Iniciar el caso ahora?» |
| 5 | Leer el prólogo | Simulador | «Comenzar» |
| 6 | Decidir | Simulador | Elegir una opción → «Confirmar respuesta» → ver la reacción del personaje |
| 7 | Revisar | Revisión final | «Responder» las pendientes o «Revisar mis respuestas» |
| 8 | Entregar | Revisión final | «Entregar caso» → confirmar |
| 9 | Confirmación | `/caso/:id/cierre` | Leer «Entregaste el caso» |

### 6.6 Recorrido B del estudiante: retomar un intento interrumpido

Volver a ingresar con el mismo correo y código → Inicio → «Continuar caso». El simulador sigue en la primera decisión pendiente. El tiempo siguió corriendo mientras tanto.

### 6.7 Recorrido C del estudiante: consultar los resultados

1. Esperar a que el docente **finalice la sesión** (puede llegar el aviso «Resultados disponibles» si las notificaciones están activas).
2. Volver a ingresar con el **mismo correo y código** («Con código de acceso»). La aplicación abre directamente el modo resultados.
3. Inicio → «Ver mis resultados» → **Resultados** → «Ver resultado» de un intento evaluado.
4. Revisar la nota, los criterios y la retroalimentación por decisión.
5. Ir a **Retroalimentación** para leer el comentario del docente.

### 6.8 Recorrido D del estudiante: situaciones sin acción posible

- «Plazo de ingreso cerrado»: el estudiante debe contactar al docente.
- «Completado»: ya no quedan intentos; toca esperar los resultados.
- Intento cerrado por tiempo, por retiro o por fin de la sesión: la pantalla de cierre explica el motivo.
- Resultado «En revisión»: hay que consultarlo más tarde.

---

## 7. Estados de carga, vacíos, validaciones y errores

### 7.1 Patrones comunes (`components/design-system/states.tsx`)

| Patrón | Aspecto | Ejemplos de texto |
|---|---|---|
| **Carga** | Barra animada con texto, `role="status"` | «Cargando tus sesiones…», «Preparando el caso…», «Consultando tu intento…», «Cargando el borrador visual…» |
| **Vacío** | Icono, título y explicación, a veces con una acción | «Aún no tienes casos», «Nadie convocado todavía», «No tienes avisos» |
| **Error de carga** | Mensaje del servidor con el botón «Reintentar» | «No se pudieron cargar tus sesiones» |
| **404** | — | «No encontramos lo que buscas» |
| **403** | Candado y «Ir a mi inicio» | «No tienes acceso a esta sección» |
| **Error en línea** | Aviso rojo bajo el formulario o la acción | Mensaje del servidor |
| **Botón ocupado** | Texto alternativo y bloqueo | «Guardando…», «Abriendo…», «Publicando…», «Evaluando…», «Preparando…» |
| **Confirmación** | Diálogo modal; las acciones destructivas usan un botón rojo | Finalizar sesión, Retirar, Archivar, Eliminar, Entregar |

### 7.2 Mensajes genéricos por código HTTP (`http-client.ts`)

| Código | Mensaje cuando el servidor no envía `detail` |
|---|---|
| 400 | «La solicitud no cumple una regla del sistema.» |
| 401 | «Tu sesión no es válida o expiró. Vuelve a ingresar.» (y se cierra la sesión) |
| 403 | «No tienes permiso para realizar esta acción.» |
| 404 | «No se encontró el recurso solicitado.» |
| 409 | «La operación no es posible en el estado actual.» |
| 422 | «Revisa los datos: hay valores con un formato no válido.» o «Revisa los datos de: campo1, campo2.» |
| 429 | «Demasiados intentos. Espera unos minutos antes de volver a intentarlo.» |
| 500 | «El servidor tuvo un problema. Inténtalo de nuevo más tarde.» |

### 7.3 Validaciones del cliente por formulario (resumen)

| Formulario | Validaciones |
|---|---|
| Acceso | Correo obligatorio y con formato válido; secreto obligatorio. |
| Cambio de contraseña | Contraseña actual obligatoria; nueva de 8 a 128 caracteres y distinta de la actual; repetición igual. |
| Programar sesión | Caso obligatorio; inicio y fin válidos; fin posterior al inicio y en el futuro; tiempo entero de 1 a min(estimado, 240); correos válidos. |
| Editar programación | Campos obligatorios (HTML); el resto lo valida el servidor. |
| Convocar | Al menos un correo y todos válidos. |
| Regenerar código / Más intentos | Motivo de al menos 5 caracteres; número mayor que el actual. |
| Nuevo caso | Nombre obligatorio; tiempo de 1 a 240 si se indica. |
| Importar CaseDSL | JSON válido (lo demás lo valida el servidor). |
| Escena, decisión u opción | Título, enunciado o texto obligatorio: el botón queda deshabilitado mientras falte. |
| Criterio | Descripción obligatoria; peso mayor que 0 y como máximo 100. |
| Sprites propios | PNG o WebP de hasta 2 MB («… supera los 2 MB por imagen.», «… no es una imagen PNG o WebP.»); máximo 12 expresiones. |
| Paquete visual | Debe ser del mismo caso («Este paquete es del caso «X», no de este. No se importó.»). |
| Comentario del docente | Hasta 5000 caracteres, con contador. |

### 7.4 Reglas de negocio que conviene explicar porque generan dudas

| Regla | Dónde se ve |
|---|---|
| La sesión **no se abre sola**: la abre el docente. | Programar sesión y detalle |
| Solo se pueden programar los casos **publicados**, y un caso publicado no se edita. | Lista de casos y Programar |
| Los estudiantes ven su nota **solo con la sesión finalizada y la evaluación registrada**. | Cola de evaluación y Resultados |
| Una **ausencia no es un cero**, y «Sin calificar» tampoco. | Resultados del docente y del estudiante |
| Iniciar un intento **consume un intento** y el tiempo no se detiene. | Confirmación de inicio |
| El paquete visual **no viaja con el caso**: hay que instalarlo en el frontend. | Editor visual |

---

## 8. Resumen de implementado, parcial y no disponible

### 8.1 Docente

| Funcionalidad | Estado |
|---|---|
| Ingreso, cierre de sesión, tema y cambio de contraseña | ✅ |
| Panel con tareas, cifras y agenda | ✅ |
| Ver aulas activas y su detalle (con CSV) | ✅ |
| Crear o editar aulas | ⛔ (lo hace la administración) |
| Programar, editar, abrir y finalizar sesiones | ✅ |
| Convocar, ver y regenerar códigos, ampliar intentos y retirar | ✅ |
| Envío del código por correo | 🟡 (depende del servidor) |
| Crear, importar, exportar, validar, publicar, archivar y eliminar casos | ✅ (con el permiso de casos) |
| Editor de escenas, decisiones, opciones y rúbrica | ✅ |
| Personaje del sistema o sprites propios, reacciones y vista previa | ✅ (arte del sistema provisional) |
| Guardar el borrador visual | 🟡 (solo en ese navegador) |
| Llevar el paquete visual a los estudiantes | 🟡 (requiere `npm run visual:install` y desplegar) |
| Evaluar en lote, recalcular, comentar | ✅ |
| Seguimiento: indicadores, notas, criterios, decisiones y CSV | ✅ |
| Actualización automática del avance en vivo | ⛔ |
| Avisos o notificaciones para el docente | ⛔ («Docentes y administración no tienen avisos en el modelo actual») |
| Contador de avisos no leídos en el menú | ⛔ (el servicio `unreadCount` existe, pero ninguna pantalla lo usa) |
| Recuperar la contraseña | ⛔ |

### 8.2 Estudiante

| Funcionalidad | Estado |
|---|---|
| Ingreso con código y paso automático a resultados | ✅ |
| Inicio, Mi aula y Mi sesión, según el estado de la convocatoria | ✅ |
| Iniciar, continuar, responder, revisar y entregar en el simulador | ✅ |
| Cuenta atrás, reanudación y cierre según el servidor | ✅ |
| Personaje con sprite y reacciones por decisión | ✅ (solo si el caso tiene un paquete instalado; si no, silueta sin rostro) |
| Resultados, detalle y retroalimentación | ✅ (solo con la sesión finalizada) |
| Avisos | 🟡 (dependen del proceso de notificaciones del servidor) |
| Ver varias convocatorias en un solo portal | ⛔ (un código por convocatoria) |
| Cuenta propia o contraseña | ⛔ |
| Diálogos línea a línea, voz, música o fondos por escena | ⛔ |

### 8.3 Verificación previa (según `frontend/docs/MATRIZ_REQUISITOS.md`)

No se verificaron de punta a punta: **CU3** (cambio de contraseña), **CU10** (archivado), **CU23** (recalificación) y **CU35** (clic de descarga del CSV). Los avisos (**CU27–CU29**) se comprobaron solo con la lista vacía. Conviene probar estas funciones antes de capturar las pantallas de las guías.

---

## 9. Pantallas que deben incluirse en los documentos de onboarding

Las capturas que ya existen están en `frontend/docs/capturas/`. Las que faltan están marcadas como **Nueva**.

### 9.1 Guía para docentes

| # | Pantalla | Ruta / estado necesario | Qué destacar | Captura |
|---|---|---|---|---|
| D1 | Ingresar con contraseña | `/ingresar` | Selector de método y errores | Nueva |
| D2 | Panel docente | `/docente` con sesiones en varios estados | «Para hacer ahora» y cifras | `07-docente-panel.jpg` |
| D3 | Aulas | `/docente/aulas` | Botón «Programar» | Nueva |
| D4 | Detalle del aula | `/docente/aulas/:id` | Cifras, agenda, casos usados y CSV | Nueva |
| D5 | Lista de casos | `/docente/casos` | Pestañas de estado y «Nuevo caso» | Nueva |
| D6 | Nuevo caso en blanco e importar | `/docente/casos/nuevo` (ambas pestañas) | Campos y pista de `dslVersion` | Nueva |
| D7 | Editor de contenido | `/docente/casos/:id` (borrador) | Escenas, decisiones, opciones y «Sin justificación» | `08-docente-editor-de-casos.jpg` |
| D8 | Rúbrica | Misma pantalla, sección Rúbrica | Suma de pesos y niveles | Nueva |
| D9 | Errores de validación | Después de «Validar» con fallos | Lista de errores | Nueva |
| D10 | Personajes del sistema | `?vista=personaje` → Personaje | Galería, expresiones y «Usar a…» | `docs/capturas/biblioteca/` y `21-docente-personaje-movil.jpg` |
| D11 | Mis personajes | Pestaña «Mis personajes» | Cargar imágenes y expresión por defecto | Nueva |
| D12 | Reacciones | Zona Reacciones | Expresión inicial, reacción y movimiento; «Pendiente de revisión» | `22-docente-reacciones-movil.jpg` (falta la de escritorio) |
| D13 | Vista previa jugable | Zona Vista previa | «Probar reacción» y tema | `23-docente-vista-previa-movil.jpg` |
| D14 | Barra de guardar y exportar | Editor visual | Estado de guardado y aviso de distribución | Nueva |
| D15 | Programar sesión | `/docente/aulas/:id/programar` | Todos los campos y el aviso «no se abre sola» | Nueva |
| D16 | Sesión SIN_INICIAR | `/docente/sesiones/:id` | «Abrir sesión» y «Editar programación» | Nueva |
| D17 | Convocados | Pestaña Convocados (EN_CURSO) | Acciones por estudiante | Nueva |
| D18 | Diálogo «Ver código» | Convocados | Código con guiones y «Copiar código» | Nueva |
| D19 | Diálogos Regenerar, Más intentos y Retirar | Convocados | Motivo y consecuencias | Nueva |
| D20 | Confirmación «Finalizar sesión» | Cabecera EN_CURSO | Irreversibilidad | Nueva |
| D21 | Resultados | Pestaña Resultados (FINALIZADO) | «Evaluar intentos cerrados», tabla y ausencias | Nueva |
| D22 | Evaluación de un intento | `/docente/sesiones/:id/intentos/:pid` | Desglose, «Registrar nota calculada» y comentario | Nueva |
| D23 | Seguimiento | Pestaña Seguimiento | Indicadores, distribución y CSV | Nueva |
| D24 | Cola de Evaluación | `/docente/evaluacion` | «Por evaluar» y «Al día» | Nueva |
| D25 | Mi cuenta | `/docente/cuenta` | Tema y cambio de contraseña | Nueva |
| D26 | Menú móvil | Cualquier ruta, 375 px | Cajón lateral | Nueva |

### 9.2 Guía para estudiantes

| # | Pantalla | Ruta / estado necesario | Qué destacar | Captura |
|---|---|---|---|---|
| E1 | Ingresar con código | `/ingresar`, «Con código de acceso» | Pista de 12 caracteres | Nueva |
| E2 | Inicio con la sesión disponible | `/estudiante` (`disponible`) | Mensaje del docente, agenda y «Iniciar caso» | Nueva |
| E3 | Confirmación de inicio | Diálogo «¿Iniciar el caso ahora?» | El tiempo corre y se consume un intento | Nueva |
| E4 | Inicio con un intento en curso | `/estudiante` (`en_curso`) | «Continuar caso» y hora límite | `01-estudiante-inicio-sesion-en-curso.jpg` |
| E5 | Prólogo del simulador | `/estudiante/caso/:id` | Cabecera con tiempo y progreso | `02-simulador-prologo.jpg` |
| E6 | Decisión seleccionada | Simulador | Elegir y confirmar | `03-simulador-decision-seleccionada.jpg` |
| E7 | Reacción del personaje | Después de confirmar (con paquete instalado) | Cambio de expresión | `20-estudiante-reaccion-movil.jpg` (falta la de escritorio) |
| E8 | Simulador sin paquete visual | Caso sin paquete | Silueta sin rostro (es normal) | Nueva |
| E9 | Error al guardar | Simulador sin red | «Tu selección se conservó» | Nueva |
| E10 | Revisión final | Último paso | Pendientes y «Entregar caso» | Nueva |
| E11 | Confirmación de entrega | Diálogo «¿Entregar el caso?» | No se puede cambiar después | Nueva |
| E12 | Cierre del intento | `/estudiante/caso/:id/cierre` | Motivo y «Tu resultado aún no está disponible» | Nueva |
| E13 | Simulador en móvil | 375 px | Barra de acciones fija | `04-simulador-movil.jpg` |
| E14 | Mi sesión | `/estudiante/sesion` | Intentos y «Puedes empezar hasta» | Nueva |
| E15 | Mi aula | `/estudiante/aula` | Solo una convocatoria | Nueva |
| E16 | Estados sin acción | `completado` y `plazo_cerrado` | Avisos | Nueva |
| E17 | Resultados no disponibles aún | `/estudiante/resultados` en modo live | «Tus resultados aparecerán cuando termine la sesión» | Nueva |
| E18 | Inicio en modo resultados | `/estudiante` (`finalizada`) | «Ver mis resultados» | `05-estudiante-inicio-resultados.jpg` |
| E19 | Resultados | `/estudiante/resultados` | Evaluados y En revisión | Nueva |
| E20 | Detalle de resultado | `/estudiante/resultados/:pid` | Criterios y retroalimentación por decisión | Nueva |
| E21 | Retroalimentación | `/estudiante/retroalimentacion` | Comentario del docente y resumen automático | `06-estudiante-retroalimentacion.jpg` |
| E22 | Avisos | `/estudiante/avisos` | Tipos y «Marcar como leído» | Nueva (necesita el proceso de notificaciones activo) |

### 9.3 Datos de prueba necesarios para capturar

- Un docente **con** permiso de casos y otro **sin** él.
- Un caso en cada estado (borrador con errores, publicado y archivado).
- Un caso **con paquete visual instalado** (el actual es «Conformidad grupal») y otro sin paquete.
- Sesiones en los tres estados, con convocados que hayan participado, que estén pendientes, ausentes o retirados, e intentos completados, cerrados por tiempo y en curso.
- Al menos un intento con un comentario del docente y otro sin evaluación registrada.
- El proceso de notificaciones activo, para capturar los avisos.

---

## 10. Dependencia con la administración (para mencionarla en las guías)

Las guías deberían remitir a la administración (`/admin`) para lo siguiente:
- **Crear las cuentas de estudiante.** Hacen falta para poder convocar: «Deben ser cuentas de estudiante activas». Los estudiantes no tienen contraseña.
- **Crear y activar aulas.**
- **Conceder o quitar el permiso de crear casos** a un docente.
- **Revisar las entregas de correo** (`/admin/entregas`) cuando los códigos o los avisos no llegan.
