# Iter Animi — Modern Academic Serenity

## Cambios visuales

La revisión inicial encontró estilos que se sobrescribían entre `app.css`, `serene.css` y `theme.css`, una bienvenida con poco contenido contextual, cifras con poca jerarquía, aulas presentadas como filas uniformes y controles de reacciones demasiado comprimidos. Se mantuvieron las hojas y los componentes existentes; no se incorporó otro framework ni un sistema de temas paralelo.

- **Base y navegación:** lienzo azul perla y medianoche, Manrope con pesos y escalas más equilibrados, navegación activa azul suave, perfil compacto, selector de tema con objetivos táctiles de 44 px y focos visibles. Los fondos iniciales y la barra del navegador siguen sincronizados con los tokens para evitar destellos al cargar.
- **Acceso:** composición editorial, mensaje de bienvenida, motivo SVG propio de dos perspectivas conectadas y formulario con un ritmo de lectura más cómodo.
- **Estudiante:** sesión protagonista, mensaje docente integrado, cifras de intentos y tiempo recibidas de la API, medidor de intentos utilizados, accesos al aula y a la sesión o resultados. Se conserva el alcance de una sola convocatoria; no se inventan otras aulas o sesiones.
- **Docente:** tareas prioritarias y recursos en columnas distintas, cifras con iconos, agenda y sesiones finalizadas como zonas de consulta.
- **Administración:** conteos con identidad visual, acciones de gestión más claras, filtros, formularios y tablas coherentes con el resto del campus.
- **Aulas, resultados y evaluación:** tarjetas de aula, encabezados, etiquetas, comentarios y presentación de notas refinados. Las tablas de intentos, criterios y seguimiento reutilizan `DataTable`, incluida su presentación apilada en móvil. Cada celda agrupa su contenido para que el correo o una aclaración permanezcan junto a su valor.
- **Personaje y reacciones:** miniaturas más legibles, selección por defecto reconocible, controles de reacción en filas separadas y vista previa integrada. Se conservan las operaciones de importación, exportación y almacenamiento.
- **Simulador:** escenario con arcos y luz ambiental, encuadre estable del personaje, nombre sobre una superficie translúcida, lectura en Source Serif 4 y decisiones con selección clara. En móvil, las acciones participan del flujo de lectura para que no tapen contenido. El movimiento de respiración se ejecuta una vez por reacción, sin animación permanente; `prefers-reduced-motion` desactiva el movimiento.

## Componentes y mantenimiento

- `ReflectionMotif`: SVG decorativo reutilizado en el acceso y los inicios; usa los mismos tokens del tema y no tiene dependencias externas.
- `DashboardIntro`: cabecera accesible compartida, con contexto del rol, título, descripción y acciones opcionales.
- `Figures`: conserva sus datos y admite iconos opcionales.
- `Page`: admite una clase de presentación opcional para componer cada inicio.
- `DataTable`: mantiene columnas, filas y títulos, y agrupa el contenido de cada celda para el diseño móvil. Sustituye tablas duplicadas de presentación en resultados y seguimiento.
- `tokens.css` sigue siendo la fuente de colores. `app.css` conserva la estructura; `serene.css` mantiene las piezas especializadas; `theme.css` reúne los ajustes de presentación compartidos. Las reglas nuevas no usan colores de contenido fijos.

No se modificaron el backend, los servicios HTTP, contratos, permisos, evaluación, temporizador, selección/confirmación de respuestas, CaseDSL ni persistencia de sprites. No se añadieron dependencias al proyecto ni se realizó commit, push o despliegue.

## Validación

- `npm run typecheck`: correcto.
- `npm run lint`: correcto.
- `npm run test`: 34 pruebas existentes correctas, incluidos flujos de selección/confirmación, guardas, temas y paquetes visuales.
- `npm run build`: correcto.
- `npm run check:contrast`: 66 combinaciones de tokens verificadas entre ambos temas, sin fallos. Se añadieron comprobaciones para navegación activa, texto secundario, placeholders y la etiqueta editorial del acceso. Esto verifica los pares de tokens definidos, no constituye una auditoría WCAG completa.
- Chrome: 28 pantallas × 6 anchos (320, 390, 768, 1280, 1440 y 1920 px) × 2 temas = **336 comprobaciones**, sin errores de JavaScript ni desbordamientos de página. Se verificaron también los estados vacío/error, las pestañas móviles del editor, la selección de una decisión, la persistencia del tema, los cambios del tema Sistema y el cierre de menú y modal con Escape. Los resultados están en [validation.json](visual-review/validation.json).

La inspección visual se realiza en Chrome mediante respuestas de API interceptadas **solo en el navegador de prueba**, sin escribir en el backend. Los nombres, casos y cifras de las capturas son fixtures aislados; no se incorporaron al producto. Las capturas «before» proceden de una copia temporal de `HEAD`, con las mismas fixtures y las fuentes cargadas.

Las capturas se encuentran en [visual-review](visual-review/). Por ejemplo:

| Pantalla | Antes | Después |
| --- | --- | --- |
| Acceso | [Claro](visual-review/before-login-light-1440.png) | [Claro](visual-review/login-light-1440.png) |
| Estudiante | [Claro](visual-review/before-student-light-1440.png) | [Claro](visual-review/student-light-1440.png) |
| Docente | [Claro](visual-review/before-teacher-light-1440.png) | [Claro](visual-review/teacher-light-1440.png) |
| Administración | [Oscuro](visual-review/before-admin-dark-1440.png) | [Oscuro](visual-review/admin-dark-1440.png) |
| Simulador móvil | [Oscuro](visual-review/before-simulator-dark-390.png) | [Oscuro](visual-review/simulator-dark-390.png) |

La revisión de integración con credenciales y datos reales del servidor no forma parte de estas capturas aisladas. Las pruebas existentes validan los flujos funcionales del frontend.

## Ajustes del login — 21 de noviembre de 2026

El banner ocupa toda la zona izquierda, sin margen exterior ni esquinas redondeadas. El login adapta su separación y contenido decorativo a la altura disponible; el selector compacto de tema muestra solo iconos, conserva etiquetas accesibles y ofrece ayudas al pasar el cursor. Se verificaron ambos métodos de ingreso sin scroll en diez resoluciones, desde 320 × 568 hasta 1920 × 1080, incluida 844 × 390 horizontal. Typecheck, lint, las 39 pruebas actuales y build correctos. Capturas: `visual-review/login-adaptive-1366.png` y `visual-review/login-adaptive-320.png`.
