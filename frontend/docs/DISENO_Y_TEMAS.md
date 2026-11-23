# Diseño, tipografía y temas

Esta guía describe la capa visual del frontend de Iter Animi:

- tipografía local: Manrope para la interfaz y Source Serif 4 para la narración del simulador;
- tema Claro, Oscuro o Sistema, sobre un único sistema de tokens;
- la composición por portal.

El backend no cambia. Para paquetes visuales (personaje y reacciones), vea [`PAQUETES_VISUALES.md`](PAQUETES_VISUALES.md).

## Qué hacía sentir brutalistas las pantallas

Lo encontrado al revisar las pantallas en el navegador antes de editar, y cómo se corrigió:

| Hallazgo | Corrección |
|---|---|
| En el acceso móvil, un bloque de tinta ocupaba media pantalla antes del formulario. | Es una banda breve con la marca y una línea. El formulario y el selector de tema van primero. |
| El nombre de la marca era invisible sobre el panel oscuro del acceso. | La marca usa un token del panel: `--brand-panel-strong`. |
| El método de acceso activo era un bloque de tinta macizo. | El activo es una superficie elevada, con borde, sombra y texto en negrita. |
| Títulos serif pesados en toda la interfaz. | Manrope seminegrita (650) para la jerarquía. La serif queda para la narración. |
| El estado del caso mostraba un punto negro macizo, porque el token `--navy` no existía. | El icono de estado usa `currentColor` y sigue el color de su texto. |
| Filtros, búsqueda y etiquetas con forma de píldora. | Radio moderado, el mismo que el resto de controles. |
| Pestañas con barra de desplazamiento visible y etiquetas cortadas en móvil. | Sin barra visible. En móvil, dos pestañas se reparten el ancho y el texto se ajusta. |
| Franjas vacías en móvil en la barra superior y entre el escenario y el panel. Venían de filas de rejilla estiradas. | Las filas fijas miden lo suyo y el contenido ocupa el resto. |
| La sesión del estudiante cortaba el título del caso. | Tamaño fluido y ajuste de palabras. |

Esto se suma a la capa «campus sereno» anterior: barra lateral clara, acción principal azul medio y estados vacíos en azul
bruma.

## Tipografía

- **Manrope Variable**, pesos 200 a 800: navegación, títulos, formularios, botones, tablas, paneles, opciones, temporizador y
  enunciados.
  - La jerarquía usa 600 a 650, no negrita en todo.
  - Las tablas, cifras, progreso y temporizador usan `font-variant-numeric: tabular-nums`.
- **Source Serif 4 Variable**: narración y diálogo del simulador. Son el contexto de la escena, el título de la pantalla
  narrativa, el rótulo de la escena y el nombre del personaje.
  - Ancho máximo de 64ch, interlineado de 1,75 y entre 17 y 19 px. En móvil no se reduce la letra.
- Ambas se alojan localmente en **WOFF2**, tomadas de los paquetes `@fontsource-variable/*`. Vite las emite en
  `dist/assets/`, sin CDN.
  - Licencia SIL OFL 1.1, copiada en [`licencias-fuentes/`](licencias-fuentes).
  - Las reglas `@font-face` propias están en `src/styles/fonts.css` y `src/styles/story-font.css`.
- **Español.** El subconjunto `latin` cubre U+0000–00FF (á é í ó ú ü ñ Á É Í Ó Ú Ü Ñ ¿ ¡ « ») y U+2000–206F (— – … “ ”).
  `latin-ext` queda declarado por si aparece otro carácter. El navegador solo descarga el subconjunto que el texto necesita.
- **Carga.** Todas usan `font-display: swap`, con respaldo del sistema (Segoe UI o system-ui para la interfaz; Georgia para
  la narración).
  - Source Serif 4 solo la importan el simulador y la vista previa del editor. Sus `@font-face` viven en el fragmento CSS
    diferido de esas vistas, así que el resto del portal no la descarga (comprobado en `dist/assets`).
- Se retiraron Literata y Atkinson Hyperlegible, que ya no se usan.

## Temas: Claro, Oscuro y Sistema

- **Preferencia.** «Sistema» es el valor por defecto y sigue `prefers-color-scheme` en vivo mientras esté elegido.
  - Solo la preferencia visual se guarda en `localStorage`, con la clave `iter-animi.theme`. «Sistema» borra la clave.
  - No se asocia a la sesión ni a las credenciales.
- **Aplicación.** El tema se aplica en `<html data-theme="light|dark">` con `color-scheme`, para que los controles
  nativos, las barras de desplazamiento y los selects sigan el tema.
- **Sin destello.** Un script en línea de `index.html` resuelve el tema antes de cargar CSS o JavaScript. También fija el
  color de fondo provisional y `theme-color`. Al recargar una página oscura o abrir directamente una ruta protegida, no hay
  destello blanco.
- **Código.** `src/lib/theme.ts` (lógica), `src/providers/ThemeProvider.tsx` (estado, `matchMedia` y respaldo al volver
  a la pestaña), `src/components/ui/ThemeSwitcher.tsx` (grupo de radios nativos).
- **Dónde está el selector:**
  - en el acceso, arriba del formulario;
  - en la barra lateral del portal, o en el menú en móvil;
  - en «Mi cuenta → Apariencia».
  - El simulador hereda el tema sin ningún menú.
- **Tokens.** Hay un único sistema semántico en `src/styles/tokens.css`: lienzo, superficies, texto, texto secundario,
  bordes, borde de control, foco, acción, selección, estados, escena, monigote y panel de acceso.
  - Los nombres antiguos (`--ink`, `--paper`, `--mist`…) son alias de los semánticos.
  - Ningún componente se duplica por tema, y no hay filtros de inversión.
- **Paletas:**
  - **Claro:** lienzo blanco cálido (#fbfaf7), superficies blancas y azul bruma, texto azul tinta, grises suaves y azul medio
    (#3f6a9a) para la acción. Rojo apagado solo para errores.
  - **Oscuro:** lienzo azul carbón (#131a24), no negro; superficies pizarra azulada; texto blanco cálido (#e6e2da), no puro;
    secundarios gris azulado; acentos azul claro (#8fb6e4).
    - Las tarjetas se distinguen por tono, sin bordes luminosos.
- **Simulador:**
  - El fondo de la escena, el panel narrativo y las opciones cambian con el tema.
  - Los sprites del docente no se tiñen ni se invierten. En oscuro solo reciben una sombra suave de apoyo.
  - El monigote blanco usa `--figure-fill`, `--figure-line` y `--figure-shadow` para destacar en ambos temas.
- **Vista previa del editor.** Su selector propio, Como la aplicación, Claro u Oscuro, pone `data-theme` solo en el marco
  de la vista previa, sin cambiar la preferencia global.

## Accesibilidad

`npm run check:contrast` comprueba con la fórmula de WCAG 2.x los pares de tokens que se usan juntos, en ambos temas.
Resultado actual: 0 fallos.

| Par | Claro | Oscuro | Mínimo |
|---|---|---|---|
| Texto sobre lienzo / superficie | 14,7 / 15,4 | 13,5 / 12,3 | 4,5 |
| Texto secundario sobre superficie / bruma | 6,4 / 5,6 | 7,3 / 6,5 | 4,5 |
| Texto sutil sobre barra lateral | 5,1 | 5,9 | 4,5 |
| Enlace sobre superficie | 7,0 | 8,5 | 4,5 |
| Texto del botón principal | 5,6 | 8,4 | 4,5 |
| Opción seleccionada | 13,8 | 10,3 | 4,5 |
| Error / aviso / confirmación sobre su fondo | 5,4 / 5,9 / 6,0 | 7,3 / 8,2 / 7,8 | 4,5 |
| Rótulo y kicker de escena | 8,2 / 5,4 | 9,7 / 5,7 | 4,5 |
| Borde de control sobre superficie / lienzo / bruma | 3,5 / 3,4 / 3,1 | 3,4 / 3,8 / 3,0 | 3 |
| Foco sobre lienzo | 5,4 | 9,4 | 3 |

- **Bordes.** Los controles (campos, selects, botones secundarios y opciones) usan `--control-border`, a 3:1. Las tarjetas y
  separadores conservan `--border`, fino y suave: no son controles.
- **No solo color:**
  - la opción elegida se marca con borde, fondo, letra rellena y ✓;
  - el tema activo, con el radio marcado, la superficie y la negrita;
  - los estados, con icono más texto;
  - los errores, con un mensaje escrito.
- **Teclado.** Foco visible con un anillo de dos tonos. El selector de tema se recorre con las flechas: comprobado en el
  navegador, la flecha derecha pasa de Claro a Oscuro y el foco queda visible.

## Composición por portal

- **Estudiante.** La sesión protagonista va primero: escena, aula, caso, estado, horario y acción. Después, una agenda
  tranquila.
  - Resultados y comentarios aparecen cuando el token es de resultados.
  - Con la sesión en curso, el detalle de un resultado explica cuándo estará. Antes se quedaba en «Cargando resultado…»;
    ahora tiene prueba automática.
- **Docente.** «Para hacer ahora» va primero en móvil, con abrir, seguir o evaluar. Después vienen las cifras y la agenda.
  El editor de casos tiene «Contenido académico» y «Personaje y reacciones».
- **Administración.** Tablas con cabeceras discretas, cifras tabulares y acciones visibles en cada fila. En móvil se apilan
  con la etiqueta en una columna proporcional.

## Verificación en navegador (19-nov-2026, API real local)

- **Claro, Oscuro y Sistema.**
  - Cambio inmediato y persistencia al recargar, resuelta antes del render: el tema ya era el guardado al leer el DOM justo
    después de navegar.
  - El acceso directo a rutas protegidas muestra el tema correcto, sin pantallas en blanco.
- **Cambio del sistema.** La emulación de `prefers-color-scheme` del navegador integrado cambia la consulta pero no emite
  el evento `change`: ni un oyente añadido a mano lo recibió.
  - En el navegador se comprobó con el respaldo al volver a la pestaña. Con Sistema elegido, al pasar el sistema a oscuro,
    la interfaz cambió.
  - El seguimiento en vivo por `change` está cubierto por `src/test/theme.test.tsx`.
- **Pantallas revisadas en ambos temas:** acceso, panel del estudiante, simulador (selección, error 503, reacción,
  reanudación, sprite ausente), editor con vista previa en el otro tema, administración de usuarios en escritorio, estado de
  acceso denegado, estado vacío y carga.
- **Recorrido del paquete visual con el build servido** (`vite preview` en `localhost:4173`, otro origen con almacenamiento
  vacío):
  - el docente importó el paquete en `localhost:5173` y lo guardó;
  - el estudiante vio a Camila en Neutral; seleccionar no reacciona;
  - el 503 conserva la expresión y la selección;
  - al confirmar, el servidor acepta y la expresión pasa a Inquieto;
  - la reanudación muestra Neutral, y sin `neutral.png` aparece el monigote;
  - con las reglas de movimiento reducido forzadas, la expresión pasó a Reflexivo con `animation: none`.

Capturas comparables en [`capturas/temas/`](capturas/temas). Son de cuentas de prueba, sin contraseñas ni códigos.

| Pantalla | Claro | Oscuro |
|---|---|---|
| Panel del estudiante | `estudiante-inicio-claro.jpg` | `estudiante-inicio-oscuro.jpg` |
| Editor, personaje | `editor-claro.jpg` | `editor-oscuro.jpg` |
| Simulador, opción seleccionada | `simulador-seleccion-claro.jpg` | `simulador-seleccion-oscuro.jpg` |
| Administración, escritorio | `admin-usuarios-escritorio-claro.jpg` | `admin-usuarios-escritorio-oscuro.jpg` |
| Otras | `editor-vista-previa-oscura-en-app-clara.jpg` | `simulador-reaccion-oscuro.jpg`, `simulador-sin-sprite-oscuro.jpg`, `simulador-escritorio-oscuro.jpg`, `estudiante-resultado-en-curso-oscuro.jpg` |

## Límites

- **Identidad del estudiante.** El estudiante entra con un token de una sola convocatoria. El portal no puede listar otras
  sesiones ni resultados de otras convocatorias, porque la API no los expone para ese token.
- **Borrador visual antes de existir el caso.** No hace falta: crear un caso o importar un CaseDSL crea el borrador en el
  servidor y devuelve su id antes de abrir el editor. La pestaña «Personaje y reacciones» siempre tiene un id estable al
  que asociar el borrador.
- **Capturas.** Se hicieron en el panel de navegador de la app, de unos 360 a 430 px de ancho, más una vista de escritorio
  de administración a 1280 px. En escritorio, el resto de pantallas se comprobó midiendo el diseño en el navegador (sin
  desbordamiento horizontal).
