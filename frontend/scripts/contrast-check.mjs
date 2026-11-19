#!/usr/bin/env node
// Contraste WCAG 2.x de los pares de tokens que se usan juntos, en claro y oscuro (npm run check:contrast).
// Falla (código 1) si algún par no alcanza el mínimo: 4.5:1 texto normal, 3:1 bordes de control y foco.
import fs from 'node:fs'
const css = fs.readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')
function block(sel) {
  const i = css.indexOf(sel)
  const body = css.slice(css.indexOf('{', i) + 1, css.indexOf('\n}', i))
  const out = {}
  for (const m of body.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-f]{6})/gi)) out[m[1]] = m[2]
  return out
}
const themes = { claro: block(":root,\n[data-theme='light']"), oscuro: block("[data-theme='dark'] {") }
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}
// [texto, fondo, mínimo, descripción]
const pairs = [
  ['text', 'bg', 4.5, 'texto sobre lienzo'],
  ['text', 'surface', 4.5, 'texto sobre superficie'],
  ['text-strong', 'surface-muted', 4.5, 'títulos sobre bruma'],
  ['text-muted', 'bg', 4.5, 'secundario sobre lienzo'],
  ['text-muted', 'surface', 4.5, 'secundario sobre superficie'],
  ['text-muted', 'surface-muted', 4.5, 'secundario sobre bruma'],
  ['text-subtle', 'surface', 4.5, 'sutil sobre superficie'],
  ['text-subtle', 'sidebar-bg', 4.5, 'sutil sobre barra lateral'],
  ['text', 'sidebar-bg', 4.5, 'navegación'],
  ['link', 'surface', 4.5, 'enlace sobre superficie'],
  ['link', 'bg', 4.5, 'enlace sobre lienzo'],
  ['on-action', 'action', 4.5, 'texto del botón principal'],
  ['on-action', 'action-hover', 4.5, 'botón principal (hover)'],
  ['on-action', 'danger', 4.5, 'botón peligro sólido'],
  ['text', 'selection-bg', 4.5, 'opción seleccionada'],
  ['danger', 'danger-bg', 4.5, 'error'],
  ['danger', 'surface', 4.5, 'texto de error en formulario'],
  ['warn', 'warn-bg', 4.5, 'aviso'],
  ['ok', 'ok-bg', 4.5, 'confirmación'],
  ['scene-label', 'scene-top', 4.5, 'rótulo de escena (arriba)'],
  ['scene-label-muted', 'scene-top', 4.5, 'kicker de escena'],
  ['scene-label', 'scene-mid', 4.5, 'rótulo de escena (medio)'],
  ['brand-panel-text', 'brand-panel', 4.5, 'panel de acceso'],
  ['control-border', 'surface', 3, 'borde de control (3:1)'],
  ['control-border', 'bg', 3, 'borde de control sobre lienzo (3:1)'],
  ['control-border', 'surface-muted', 3, 'borde de control sobre bruma (3:1)'],
  ['action', 'surface', 3, 'anillo de selección / foco (3:1)'],
  ['focus-ring', 'bg', 3, 'foco sobre lienzo (3:1)'],
  ['figure-fill', 'scene-mid', 1.3, 'monigote frente al fondo (referencia)'],
]
let fails = 0
for (const [name, t] of Object.entries(themes)) {
  console.log(`\n== ${name}`)
  for (const [a, b, min, label] of pairs) {
    if (!t[a] || !t[b]) {
      console.log(`  ?  ${label}: falta ${!t[a] ? a : b}`)
      continue
    }
    const r = ratio(t[a], t[b])
    const ok = r >= min
    if (!ok) fails++
    console.log(`  ${ok ? 'OK ' : 'NO '} ${r.toFixed(2).padStart(5)}  (mín ${min})  ${label}`)
  }
}
console.log(`\nFallos: ${fails}`)
if (fails) process.exit(1)
