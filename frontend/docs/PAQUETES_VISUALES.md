# Paquetes visuales: personaje y reacciones

Los casos se juegan como una novela visual. Un entrevistado ocupa un hueco fijo del escenario, y su expresión cambia
cuando el servidor acepta una respuesta. El docente define el personaje, sus imágenes y las reacciones en la pestaña
**Personaje y reacciones** del caso.

Todo esto vive en el frontend. El backend no cambia: no hay rutas, tablas, permisos ni campos nuevos, el CaseDSL es el
mismo y no se usa ningún servicio externo de imágenes.

> Desde la versión 2 del paquete, el personaje puede ser uno de la biblioteca del sistema: el paquete solo guarda su id y las imágenes salen de `public/sprite-library/`. Ver [`BIBLIOTECA_PERSONAJES.md`](BIBLIOTECA_PERSONAJES.md).

## Publicación automática («Guardar y publicar»)

Cuando el frontend se sirve con `npm run dev` o `npm run preview`, el editor muestra **Guardar y publicar** en lugar de
«Guardar borrador». Al pulsarlo, y también al **Exportar paquete visual**:

1. guarda el borrador en este navegador (IndexedDB), como siempre;
2. arma el paquete (manifiesto más imágenes propias; un personaje del sistema solo viaja como id) y lo envía al servidor del
   frontend;
3. el servidor lo valida con las mismas reglas que `npm run visual:install` y lo instala en `public/visual-packages/<caso>/`;
4. los estudiantes del caso ven el personaje y sus reacciones al abrir o volver a entrar al simulador. Los sprites del sistema
   se cargan desde `public/sprite-library/` y los propios desde la carpeta del paquete.

Lo hace un plugin del servidor del frontend (`vite-plugins/visual-publish.ts`), no el backend. Solo acepta peticiones del
propio equipo, del mismo origen y con la cabecera del editor. La carpeta `public/visual-packages/` forma parte del frontend,
así que lo publicado queda incluido en el siguiente `npm run build`.

**Límite:** si se despliega solo `dist/` como archivos estáticos (Nginx, Netlify…), no hay servidor del frontend que reciba
la publicación. El editor lo detecta, vuelve a mostrar «Guardar borrador» y queda el recorrido manual descrito abajo.

## Recorrido: borrador local → paquete exportado → paquete en el despliegue

```
 Docente (su navegador)               Repositorio del frontend                Estudiantes (cualquier equipo)
 ─────────────────────────            ──────────────────────────────          ─────────────────────────────
 Personaje y reacciones               npm run visual:install -- paquete.zip   El simulador pide
 «Guardar borrador» → IndexedDB  ──►  public/visual-packages/<id-del-caso>/ ─► /visual-packages/index.json
 «Exportar paquete visual» → .zip     npm run build → dist/visual-packages/   y las imágenes del caso
```

1. **Borrador local.** «Guardar borrador» guarda el personaje, las imágenes y las reacciones en IndexedDB, separado por
   caso y por cuenta docente. Aparece el aviso «Borrador visual guardado en este navegador.». Las imágenes nunca van a
   `localStorage`. El borrador solo existe en ese navegador: los estudiantes no lo ven.
2. **Paquete exportado.** «Exportar paquete visual» descarga `paquete-visual-<id-del-caso>.zip`, que contiene:
   - `manifest.json`: formato `iter-animi-paquete-visual`, versión 1, id y nombre del caso, personaje, expresiones,
     expresión inicial por escena y reacción por opción;
   - `sprites/<expresión>.png|webp`, referenciadas desde el manifiesto con rutas relativas.
3. **Paquete en el despliegue.** Desde `frontend/`, instale el paquete y vuelva a compilar:
   ```bash
   npm run visual:install -- ruta/paquete-visual-<id-del-caso>.zip
   ```
   ```bash
   npm run build
   ```
   El script valida el paquete, lo copia en `public/visual-packages/<id-del-caso>/` y regenera
   `public/visual-packages/index.json`. `npm run build` vuelve a generar el índice antes de compilar (`prebuild`), y Vite copia
   la carpeta a `dist/visual-packages/`. Después se despliega `dist/` como siempre. Conviene versionar la carpeta en git
   para que el paquete forme parte del frontend publicado.

Otros comandos: `npm run visual:index` (reconstruye el índice) y `npm run visual:remove -- <id-del-caso>` (retira un paquete).

**Ubicación estática documentada:** `frontend/public/visual-packages/`. En el servidor queda en `/visual-packages/`, junto al
frontend, sin IndexedDB, sin API nueva y sin depender del equipo del docente.

## Cómo encuentra el simulador el paquete

El cuestionario del estudiante no incluye el id del caso. Por eso `index.json` relaciona cada paquete con los ids de sus
escenas, que son únicos. El simulador elige el paquete cuyas escenas coinciden con las del cuestionario, valida el
manifiesto y carga las imágenes por URL relativa.

Si falta el índice, el paquete o una imagen, o si el paquete es inválido, se muestra el personaje blanco sin rostro y el
caso sigue siendo jugable.

## Reglas de las reacciones

- Las asociaciones usan los ids estables de escena, pregunta y opción que entrega la API, nunca la letra. Reordenar las
  opciones no rompe nada.
- Cada asociación guarda una firma del texto: título de la escena, o enunciado más texto de la opción.
  - Si el caso cambia después, la asociación queda **pendiente de revisión** en el editor.
  - Mientras tanto, el simulador la ignora y usa la expresión inicial.
  - Si la opción o la escena ya no existen, el editor lo avisa y ofrece quitarlas.
- «Sin cambio» deja la expresión que había. Movimientos disponibles: fundido, aparición suave, respiración sutil o sin animación.
- Las reacciones son dirección narrativa, no evaluación. El paquete no contiene claves, opciones correctas, rúbricas,
  puntajes ni datos de estudiantes.
- La expresión cambia solo cuando el servidor acepta la respuesta.
  - Seleccionar una opción no cambia nada, y un error de envío conserva la selección y la expresión anterior.
  - Si la siguiente decisión es de otra escena, la reacción se ve un momento (1,4 s) sin bloquear el texto.
  - Al reanudar un intento se usa la expresión inicial de la escena.
- Las transiciones son solo CSS (opacidad y un desplazamiento mínimo). Con `prefers-reduced-motion` la expresión cambia
  igual, pero sin animación.

## Validaciones (editor e instalador usan el mismo código, `src/lib/visual/package.ts`)

- ZIP sin cifrar (store o deflate), con CRC comprobado. Como máximo 64 entradas y 20 MB en total.
- Solo se aceptan `manifest.json` y `sprites/<id>.png|webp`.
  - Se rechazan rutas absolutas, URLs externas, `..` y barras invertidas.
- Las imágenes deben ser PNG o WebP reales, según sus bytes iniciales, de 2 MB como máximo cada una.
  - No puede haber imágenes sin referencia ni referencias sin imagen.
- Manifiesto con formato y versión conocidos, ids con forma de UUID, hasta 12 expresiones, firmas, movimientos válidos y
  referencias coherentes entre expresiones, escenas y reacciones.
- Al importar en el editor, el paquete debe ser del mismo caso. Si no lo es, se rechaza.

## Guía rápida para la sustentación

Datos de prueba autorizados: caso «Conformidad grupal». El paquete de demostración está en
`docs/ejemplos/paquete-visual-conformidad-grupal.zip` y ya viene instalado en `public/visual-packages/`.

1. **Docente → Casos → Conformidad grupal → Personaje y reacciones.**
   - Se ven el personaje Camila, cinco expresiones con miniatura y las reacciones de la escena 1:
     - decisión 1: A → Reflexivo, B → Inquieto (aparición suave), C → Sin cambio;
     - decisión 2: A → Aliviado, B → Incómodo, C → Inquieto.
   - Si el navegador no tiene el borrador, use **Importar paquete visual** con el ZIP de `docs/ejemplos/`.
2. **Vista previa jugable.** Elija una opción: la expresión no cambia. Pulse **Probar reacción**: cambia. Pruebe la opción C:
   «Esta opción no cambia la expresión». **Volver al estado inicial** restablece todo. No se crean intentos.
3. **Guardar borrador**, recargar la página: todo sigue ahí. **Exportar paquete visual** descarga el ZIP.
4. En una terminal, desde `frontend/`, instale el ZIP y compile. Después, sirva el build:
   ```bash
   npm run visual:install -- ../docs/ejemplos/paquete-visual-conformidad-grupal.zip
   ```
   ```bash
   npm run build
   ```
   ```bash
   npm run preview
   ```
5. **Estudiante en otro navegador o perfil** (u otro origen, por ejemplo `http://localhost:4173`), con una sesión en curso del
   caso. Al iniciar, Camila aparece en Neutral. Al seleccionar una opción no cambia. Al pulsar **Confirmar respuesta**,
   cambia según la reacción configurada.
6. Si algo falla durante la presentación, el caso sigue jugable con el personaje sin rostro. Para retirar el paquete use
   `npm run visual:remove -- 2c2f099a-0e5e-41be-9a0e-43b403e2a41c`.

## Verificación realizada (19-nov-2026, entorno local con la API real)

- Docente en `http://localhost:5174`, servidor de desarrollo:
  - cinco imágenes PNG cargadas por los campos de archivo y reacciones vinculadas;
  - vista previa: seleccionar no reacciona, «Probar reacción» sí, «Sin cambio» conserva y el estado inicial se restablece;
  - guardado y recarga: el borrador persiste; `localStorage` solo contiene la sesión;
  - exportación del ZIP, instalación con `npm run visual:install` y `npm run build`, que incluye `dist/visual-packages/`.
- Estudiante en `http://localhost:4173`, `vite preview` del build. Es otro origen, con `localStorage` e IndexedDB propios y
  vacíos; no es otro perfil del navegador.
  - Entra con su correo y código y ve a Camila en Neutral, servida desde `/visual-packages/...`.
  - Seleccionar B no cambia la expresión.
  - Un 503 forzado al enviar conserva Neutral y la selección.
  - Al confirmar, el servidor acepta y la expresión pasa a Inquieto con `motion-rise`.
- Movimiento reducido: el navegador del panel no emula `prefers-reduced-motion`, así que se forzaron las reglas de esa
  consulta. Al confirmar la decisión 2, la expresión pasó a Aliviado con `animation: none`.
- Reanudar (recargar) muestra la expresión inicial. Con una imagen retirada del build, o sin `index.json`, aparece el
  personaje sin rostro y el caso sigue jugable.
- Pruebas automáticas en `src/test/visual.test.tsx`:
  - ZIP de ida y vuelta, y alteración detectada;
  - exportar e importar;
  - rechazo de rutas externas, `..` y falsos PNG;
  - paquete sin datos de evaluación;
  - firmas e ids estables;
  - reacción con traspaso entre escenas;
  - simulador con paquete: seleccionar no reacciona, el error conserva la expresión y la confirmación la cambia;
  - simulador sin paquete.
