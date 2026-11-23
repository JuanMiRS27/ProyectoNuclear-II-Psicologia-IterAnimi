# Biblioteca de personajes del sistema

En **Caso → Personaje y reacciones** el docente puede elegir entre dos orígenes:

- **Personajes del sistema:** sprites incluidos con Iter Animi, con ocho expresiones cada uno.
- **Mis personajes:** sprites propios en PNG o WebP, como hasta ahora.

Los personajes del sistema funcionan igual que los propios en la vista previa, el paquete visual y el simulador del
estudiante. El backend no cambia.

## Estado del arte: PROVISIONAL

> El entorno donde se construyó esta función no tiene herramienta de generación de imágenes. Los sprites incluidos son
> **provisionales**: ilustraciones vectoriales 2D sencillas, generadas por código con
> `scripts/generate-provisional-sprites.mjs`. **No son** la ilustración semirrealista de inspiración anime que pide el
> encargo, y la biblioteca artística no está terminada. La interfaz lo indica con el aviso «Arte provisional».

Lo que sí cumplen:

- **Seis perfiles diferenciados:**

  | Id | Nombre | Perfil |
  |---|---|---|
  | `system-young-adult-m-01` | Samuel | adulto joven masculino |
  | `system-young-adult-f-01` | Inés | adulta joven femenina |
  | `system-adult-m-01` | Julián | hombre adulto |
  | `system-adult-f-01` | Carmen | mujer adulta |
  | `system-older-m-01` | Ernesto | persona mayor masculina |
  | `system-older-f-01` | Rosa | persona mayor femenina |

  Cada uno tiene su propio tono de piel, peinado, ropa y rasgos, sin asociar la apariencia a estados psicológicos.
- **Ocho expresiones por personaje:** Neutral, Feliz, Triste, Enojado, Preocupado, Sorprendido, Incómodo y Reflexivo.
- **Misma persona en todas las expresiones.** El rostro, peinado, ropa, proporciones e iluminación se dibujan una vez; solo
  cambian cejas, párpados, mirada, boca y detalles como rubor, lágrima o gota de sudor.
- **Encuadre idéntico** (480 × 720, fondo transparente): cambiar de expresión no produce saltos.

### Cómo instalar el arte final

1. Encargar o generar las ilustraciones finales: WebP transparente de 480 × 720, mismo encuadre de busto, un archivo por
   expresión.
2. Copiarlas en `public/sprite-library/<id-del-personaje>/<expresión>.webp`, con los mismos ids de personaje y de
   expresión.
3. En `public/sprite-library/index.json`, cambiar `file` a `.webp` y poner `"status": "final"`. Cuando ningún personaje
   sea provisional, el aviso desaparece solo.

No hay que tocar código, y los casos y paquetes ya configurados siguen funcionando: guardan ids, no imágenes. También se
pueden añadir personajes nuevos al catálogo con un id `system-…` propio.

## Uso en el editor

1. **Personajes del sistema.** Una galería de tarjetas con retrato, nombre y perfil, y debajo una vista previa amplia con
   las ocho expresiones. Al pulsar una expresión se ve en grande.
2. **Usar a [nombre].** Aplica el personaje al caso:
   - Las asociaciones compatibles se conservan.
   - Las expresiones equivalentes se reasignan: Inquieto → Preocupado y Aliviado → Feliz, en ambos sentidos.
   - Lo que no tiene equivalente vuelve a «Sin cambio», o a la expresión por defecto en una escena. Un aviso detalla cada
     cambio.
3. **Reacciones.** Expresión inicial por escena y expresión, más movimiento, por opción, como siempre. Los ids son los del
   caso, nunca la letra.
4. **Vista previa.** Prueba cualquier opción sin crear intentos.
5. **Mis personajes → Volver a mis sprites.** Recupera las imágenes propias que había antes de elegir un personaje del
   sistema; quedan apartadas en el borrador.
6. **Cambiar entre personajes del sistema** conserva todas las asociaciones, porque comparten los ids de expresión.
7. **El nombre visible** sigue al personaje elegido, salvo que el docente haya escrito uno propio.

## Almacenamiento y paquetes

- **Recursos estáticos.** El catálogo y las imágenes están en `public/sprite-library/`, copiado a `dist/sprite-library/` en
  cada build. Están disponibles en cualquier despliegue del frontend.
- **IndexedDB.** El borrador solo guarda el id del personaje (`character.library`) y la configuración. Las imágenes del
  sistema nunca se copian; las propias, sí, como antes.
- **Paquete visual versión 2.** Un paquete con personaje del sistema solo contiene `manifest.json`, con `version: 2`,
  `character.library` y `sprite: null` en cada expresión. Pesa unos 3 KB.
  - Los paquetes de la versión 1, con sprites propios, siguen siendo válidos.
- **Validación:**
  - el id debe tener la forma `system-…`;
  - solo se admite en la versión 2;
  - un paquete con personaje del sistema no puede incluir imágenes propias;
  - en el catálogo, cada archivo debe estar dentro de la carpeta de su personaje (sin `..`, rutas absolutas ni URLs).
- **Respaldo.** Si el personaje referido no está en la biblioteca servida:
  - el editor lo avisa al importar;
  - `npm run visual:install` lo avisa al instalar;
  - el simulador muestra el personaje sin rostro y el caso sigue jugable. Lo mismo ocurre si falta una sola imagen.
- **Paquete de demostración:** `docs/ejemplos/paquete-visual-conformidad-grupal-sistema.zip`, con Inés:
  - decisión 1: A → Reflexivo, B → Preocupado, C → Sin cambio;
  - decisión 2: A → Feliz, B → Enojado, C → Triste.

  Es el que está instalado ahora en `public/visual-packages/`. Para volver al paquete con Camila (sprites propios):

  ```bash
  npm run visual:install -- ../docs/ejemplos/paquete-visual-conformidad-grupal.zip
  ```

## Verificación (20-nov-2026, API real local)

- **Hoja de contacto** de los 48 sprites: cada fila es la misma persona y los seis personajes son distintos.
- **Editor** en `localhost:5173`:
  - Partiendo de reacciones con las expresiones propias, al elegir a Inés se remapeó Inquieto → Preocupado y Aliviado → Feliz.
    Reflexivo e Incómodo se conservaron.
  - Se asignaron Enojado y Triste.
  - Vista previa: seleccionar no reacciona; B → Preocupado; C mantiene la expresión; A → Reflexivo.
  - Al pasar a Rosa se conservó todo. Al volver a mis sprites, Triste y Enojado quedaron sin equivalente, como avisa el
    editor. Al volver a Inés se remapeó de nuevo.
  - Tras guardar y recargar, IndexedDB contiene `library: system-young-adult-f-01`, ninguna imagen y todos los `sprite`
    en `null`.
  - Exportar (ZIP de 2,7 KB, solo manifiesto), descartar e importar restauraron personaje y reacciones.
- **Estudiante** en `localhost:4173` (build de producción, otro origen sin IndexedDB):
  - Inés en Neutral, servida desde `/sprite-library/…`.
  - Seleccionar no cambia la expresión.
  - Confirmar D1-B → Preocupado (`motion-rise`). Al recargar se reanudó en Neutral. Confirmar D2-B → Enojado.
  - Probado en oscuro y en claro.
  - Sin `neutral.svg` en el build apareció el personaje sin rostro y el caso siguió jugable.
- **Calidad:** TypeScript, lint, 39 pruebas, build y contraste sin fallos. Las pruebas nuevas están en
  `src/test/library.test.ts`.

Capturas en [`capturas/biblioteca/`](capturas/biblioteca):

- galería del editor: `editor-galeria-claro.jpg`;
- expresiones del editor: `editor-expresiones-claro.jpg` y `editor-expresiones-oscuro.jpg`;
- reacción en el simulador: `estudiante-reaccion-sistema-oscuro.jpg` (Preocupado) y `estudiante-reaccion-sistema-claro.jpg`
  (Enojado).
