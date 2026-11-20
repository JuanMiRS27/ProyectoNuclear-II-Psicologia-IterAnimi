#!/usr/bin/env node
// Genera los sprites PROVISIONALES de la biblioteca de personajes del sistema (SVG vectoriales).
//
//   node scripts/generate-provisional-sprites.mjs
//
// No son el arte final: son ilustraciones 2D simples, generadas por código, para que la biblioteca funcione de punta a
// punta mientras se encarga el arte definitivo (ilustración 2D semirrealista de inspiración anime, WebP transparente).
// Cada personaje se dibuja una sola vez (rostro, peinado, ropa, proporciones e iluminación) y solo cambian cejas,
// ojos, boca y pequeños detalles por expresión: todas las expresiones son la misma persona y el encuadre es idéntico
// (480 × 720, mismo origen), así que cambiar de expresión no produce saltos.
//
// Para instalar el arte final basta con sustituir los archivos de public/sprite-library/<id>/ por WebP con el mismo
// nombre de expresión, actualizar "file" y poner "status": "final" en public/sprite-library/index.json.
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'sprite-library')
const LINE = '#3b2b2b'

export const EXPRESSIONS = [
  { id: 'neutral', label: 'Neutral' },
  { id: 'feliz', label: 'Feliz' },
  { id: 'triste', label: 'Triste' },
  { id: 'enojado', label: 'Enojado' },
  { id: 'preocupado', label: 'Preocupado' },
  { id: 'sorprendido', label: 'Sorprendido' },
  { id: 'incomodo', label: 'Incómodo' },
  { id: 'reflexivo', label: 'Reflexivo' },
]

// Parámetros faciales por expresión (mismo rostro, distinta gestualidad).
const FACE = {
  neutral: { browIn: 0, browOut: 0, open: 1, look: [0, 0], mouth: 'neutral' },
  feliz: { browIn: -4, browOut: -2, open: 0, eyes: 'smile', look: [0, 0], mouth: 'smile', blush: true },
  triste: { browIn: -9, browOut: 7, open: 0.72, lidSad: true, look: [0, 3], mouth: 'sad', tear: true },
  enojado: { browIn: 10, browOut: -6, open: 0.8, lidAngry: true, look: [0, 0], mouth: 'angry', furrow: true },
  preocupado: { browIn: -8, browOut: 4, open: 0.95, look: [0, 1], mouth: 'worried', sweat: true },
  sorprendido: { browIn: -12, browOut: -12, open: 1.28, small: true, look: [0, 0], mouth: 'o' },
  incomodo: { browIn: -3, browOut: 5, open: 0.82, look: [7, 1], mouth: 'crooked', sweat: true },
  reflexivo: { browIn: 3, browOut: -1, open: 0.7, look: [-8, -6], mouth: 'thinking' },
}

// Seis perfiles con apariencias diferenciadas; ninguno asocia rasgos físicos con un estado psicológico.
export const CHARACTERS = [
  {
    id: 'system-young-adult-m-01',
    name: 'Samuel',
    profile: 'Adulto joven masculino',
    description: 'Veintitantos años, pelo oscuro corto y sudadera.',
    skin: ['#c99a76', '#b0815f'],
    hair: { style: 'short', color: '#2a211d' },
    iris: '#4a3326',
    clothes: { style: 'hoodie', color: '#3f7a8c', accent: '#e9edf0' },
  },
  {
    id: 'system-young-adult-f-01',
    name: 'Inés',
    profile: 'Adulta joven femenina',
    description: 'Veintitantos años, melena larga castaña y jersey de punto.',
    skin: ['#f1d2bd', '#dcb39a'],
    hair: { style: 'long', color: '#6b4430' },
    iris: '#5b7a3a',
    freckles: true,
    clothes: { style: 'sweater', color: '#b8775e', accent: '#f3e6dc' },
  },
  {
    id: 'system-adult-m-01',
    name: 'Julián',
    profile: 'Hombre adulto',
    description: 'Cuarenta y tantos, pelo muy corto, barba recortada y chaqueta.',
    skin: ['#8a5a3c', '#734a30'],
    hair: { style: 'buzz', color: '#1d1714' },
    iris: '#2f2019',
    beard: '#241b17',
    clothes: { style: 'blazer', color: '#3d4a63', accent: '#dfe5ee' },
  },
  {
    id: 'system-adult-f-01',
    name: 'Carmen',
    profile: 'Mujer adulta',
    description: 'Cuarenta y tantos, media melena con flequillo, gafas y rebeca.',
    skin: ['#d9a878', '#c18f62'],
    hair: { style: 'bob', color: '#2e2522' },
    iris: '#3d2a1f',
    glasses: '#5a3d32',
    clothes: { style: 'cardigan', color: '#6f6a9a', accent: '#efe9e0' },
  },
  {
    id: 'system-older-m-01',
    name: 'Ernesto',
    profile: 'Persona mayor masculina',
    description: 'Setenta y tantos, pelo canoso con entradas, gafas y jersey.',
    skin: ['#e8c3a6', '#cfa587'],
    hair: { style: 'receding', color: '#d7d5d1' },
    iris: '#4f6b86',
    glasses: '#7a7f86',
    age: true,
    clothes: { style: 'collar', color: '#7d6a4f', accent: '#eef0f2' },
  },
  {
    id: 'system-older-f-01',
    name: 'Rosa',
    profile: 'Persona mayor femenina',
    description: 'Setenta y tantos, pelo canoso recogido y blusa con pañuelo.',
    skin: ['#6e4631', '#5b3726'],
    hair: { style: 'bun', color: '#cfccc8' },
    iris: '#2a1b14',
    age: true,
    clothes: { style: 'blouse', color: '#4f7f6a', accent: '#d9a441' },
  },
]

// ---------------------------------------------------------------------------------------------------------------
// Piezas comunes. Cabeza centrada en (240, 320); hombros hacia y = 560; el encuadre es idéntico en todos.

const face = 'M150 300 C150 214 190 176 240 176 C290 176 330 214 330 300 C330 372 304 430 240 452 C176 430 150 372 150 300 Z'

function hairBack(h) {
  const c = h.color
  switch (h.style) {
    case 'long':
      return `<path d="M138 300 C130 200 180 156 240 156 C300 156 350 200 342 300 C350 420 372 520 360 610 L120 610 C108 520 130 420 138 300 Z" fill="${c}"/>`
    case 'bob':
      return `<path d="M136 300 C130 200 182 158 240 158 C298 158 350 200 344 300 C348 360 346 410 334 446 L146 446 C134 410 132 360 136 300 Z" fill="${c}"/>`
    case 'bun':
      return `<circle cx="240" cy="160" r="44" fill="${c}" stroke="${LINE}" stroke-width="3"/><path d="M146 300 C140 210 186 168 240 168 C294 168 340 210 334 300 Z" fill="${c}"/>`
    default:
      return ''
  }
}

function hairFront(h) {
  const c = h.color
  const st = `stroke="${LINE}" stroke-width="3" stroke-linejoin="round"`
  switch (h.style) {
    case 'short':
      return `<path d="M148 296 C140 210 186 166 242 166 C300 166 344 212 332 296 C326 262 318 240 300 228 L292 252 L276 226 L262 250 L246 222 L232 252 L216 228 L204 254 L190 232 C170 248 156 270 148 296 Z" fill="${c}" ${st}/>`
    case 'long':
      return `<path d="M146 310 C140 214 186 170 240 170 C296 170 342 214 334 310 C326 270 312 240 288 224 C276 250 252 262 224 262 C204 262 186 254 176 242 C160 262 150 286 146 310 Z" fill="${c}" ${st}/>`
    case 'buzz':
      return `<path d="M152 288 C150 214 190 178 240 178 C290 178 330 214 328 288 C320 246 300 222 240 220 C180 222 160 246 152 288 Z" fill="${c}" opacity="0.92" ${st}/>`
    case 'bob':
      return `<path d="M144 320 C138 216 186 172 240 172 C294 172 342 216 336 320 C330 290 324 268 314 252 L166 252 C156 268 150 290 144 320 Z" fill="${c}" ${st}/><path d="M166 252 C190 236 214 228 240 228 C266 228 290 236 314 252" fill="none" stroke="${LINE}" stroke-width="2" opacity="0.5"/>`
    case 'receding':
      return `<path d="M150 318 C146 268 156 232 176 214 C182 246 176 280 168 318 Z" fill="${c}" ${st}/><path d="M330 318 C334 268 324 232 304 214 C298 246 304 280 312 318 Z" fill="${c}" ${st}/><path d="M196 196 C220 186 262 186 284 196" fill="none" stroke="${c}" stroke-width="7" stroke-linecap="round"/>`
    case 'bun':
      return `<path d="M148 300 C144 214 188 176 240 176 C292 176 336 214 332 300 C326 252 300 222 240 218 C180 222 154 252 148 300 Z" fill="${c}" ${st}/><path d="M188 214 C206 200 224 194 240 194 M292 214 C274 200 256 194 240 194" fill="none" stroke="${LINE}" stroke-width="2" opacity="0.45"/>`
    default:
      return ''
  }
}

function clothes(cl) {
  const c = cl.color
  const a = cl.accent
  const st = `stroke="${LINE}" stroke-width="3" stroke-linejoin="round"`
  const body = `<path d="M54 720 C58 616 98 566 176 540 L304 540 C382 566 422 616 426 720 Z" fill="${c}" ${st}/>`
  const shade = `<path d="M54 720 C58 640 84 596 130 572 C120 620 118 670 124 720 Z M426 720 C422 640 396 596 350 572 C360 620 362 670 356 720 Z" fill="#000" opacity="0.12"/>`
  switch (cl.style) {
    case 'hoodie':
      return `${body}${shade}<path d="M168 544 C186 590 294 590 312 544 C300 576 180 576 168 544 Z" fill="#000" opacity="0.15"/><path d="M214 574 L210 640 M266 574 L270 640" stroke="${a}" stroke-width="5" stroke-linecap="round"/>`
    case 'sweater':
      return `${body}${shade}<path d="M196 540 C206 566 274 566 284 540" fill="none" stroke="${a}" stroke-width="8"/><path d="M90 660 L390 660" stroke="#000" stroke-width="2" opacity="0.1"/>`
    case 'blazer':
      return `${body}${shade}<path d="M200 540 L240 640 L280 540 Z" fill="${a}" ${st}/><path d="M200 540 L222 600 L196 620 L176 552 Z M280 540 L258 600 L284 620 L304 552 Z" fill="#000" opacity="0.18"/>`
    case 'cardigan':
      return `${body}${shade}<path d="M198 540 C210 580 270 580 282 540 L276 720 L204 720 Z" fill="${a}" ${st}/><circle cx="240" cy="640" r="0"/><path d="M204 600 L204 720 M276 600 L276 720" stroke="${LINE}" stroke-width="2"/>`
    case 'collar':
      return `${body}${shade}<path d="M194 540 L240 588 L286 540 L276 528 L240 560 L204 528 Z" fill="${a}" ${st}/>`
    case 'blouse':
      return `${body}${shade}<path d="M196 540 C214 570 266 570 284 540 C276 590 252 610 240 640 C228 610 204 590 196 540 Z" fill="${a}" ${st}/><path d="M232 600 L224 650 L240 640 L256 650 L248 600" fill="${a}" ${st}/>`
    default:
      return body
  }
}

function eye(cx, cy, ch, f, side) {
  const open = f.open
  const [lx, ly] = f.look
  if (f.eyes === 'smile') {
    // Ojos cerrados en arco (sonrisa): mismo tamaño y posición que los abiertos.
    return `<path d="M${cx - 22} ${cy + 4} Q${cx} ${cy - 14} ${cx + 22} ${cy + 4}" fill="none" stroke="${LINE}" stroke-width="5" stroke-linecap="round"/>`
  }
  const ry = 15 * open
  const r = f.small ? 10 : 13
  const outer = side * 22
  // Párpado superior: inclinado hacia fuera (triste) o hacia dentro (enojado).
  const tiltIn = f.lidAngry ? 7 : f.lidSad ? -2 : 0
  const tiltOut = f.lidSad ? 6 : f.lidAngry ? -2 : 0
  const inX = cx - outer
  const outX = cx + outer
  const lid = `M${inX} ${cy - ry * 0.55 + tiltIn} Q${cx} ${cy - ry - 6} ${outX} ${cy - ry * 0.55 + tiltOut}`
  return `
    <clipPath id="e${side}"><ellipse cx="${cx}" cy="${cy}" rx="22" ry="${ry}"/></clipPath>
    <ellipse cx="${cx}" cy="${cy}" rx="22" ry="${ry}" fill="#fbfaf8"/>
    <g clip-path="url(#e${side})">
      <circle cx="${cx + lx}" cy="${cy + ly}" r="${r}" fill="${ch.iris}"/>
      <circle cx="${cx + lx}" cy="${cy + ly}" r="${r * 0.48}" fill="#16110f"/>
      <circle cx="${cx + lx - 4}" cy="${cy + ly - 5}" r="${r * 0.3}" fill="#fff"/>
      <circle cx="${cx + lx + 4}" cy="${cy + ly + 4}" r="${r * 0.14}" fill="#fff" opacity="0.8"/>
      ${f.lidAngry || f.lidSad ? `<path d="${lid} L${outX} ${cy - 30} L${inX} ${cy - 30} Z" fill="${ch.skin[0]}"/>` : ''}
    </g>
    <path d="${lid}" fill="none" stroke="${LINE}" stroke-width="5" stroke-linecap="round"/>
    <path d="M${cx - 18} ${cy + ry * 0.85} Q${cx} ${cy + ry + 2} ${cx + 18} ${cy + ry * 0.85}" fill="none" stroke="${LINE}" stroke-width="1.8" opacity="0.55"/>`
}

function brows(ch, f) {
  const col = ch.hair.style === 'receding' || ch.hair.style === 'bun' ? '#9b968f' : ch.hair.color
  const y = 282
  const L = `M178 ${y + f.browOut} Q198 ${y - 8 + (f.browIn + f.browOut) / 2} 220 ${y + f.browIn}`
  const R = `M260 ${y + f.browIn} Q282 ${y - 8 + (f.browIn + f.browOut) / 2} 302 ${y + f.browOut}`
  return `<path d="${L} M${R.slice(1)}" fill="none" stroke="${col}" stroke-width="6.5" stroke-linecap="round"/>`
}

function mouth(f) {
  const s = `stroke="${LINE}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"`
  switch (f.mouth) {
    case 'smile':
      return `<path d="M214 392 Q240 424 266 392 Q240 402 214 392 Z" fill="#8f3f3f" ${s}/><path d="M226 404 Q240 414 254 404" fill="#d97f7f"/>`
    case 'sad':
      return `<path d="M222 404 Q240 392 258 404" fill="none" ${s}/>`
    case 'angry':
      return `<path d="M220 400 Q240 394 260 400" fill="none" ${s}/><path d="M224 404 L256 404" stroke="${LINE}" stroke-width="1.5" opacity="0.5"/>`
    case 'worried':
      return `<path d="M222 400 Q231 394 240 400 Q249 406 258 398" fill="none" ${s}/>`
    case 'o':
      return `<ellipse cx="240" cy="402" rx="10" ry="13" fill="#7c3535" ${s}/>`
    case 'crooked':
      return `<path d="M222 402 Q238 400 256 394" fill="none" ${s}/>`
    case 'thinking':
      return `<path d="M228 400 Q238 403 248 399" fill="none" ${s}/>`
    default:
      return `<path d="M222 398 Q240 404 258 398" fill="none" ${s}/>`
  }
}

function extras(ch, f) {
  let out = ''
  if (f.blush) out += `<ellipse cx="186" cy="362" rx="18" ry="8" fill="#e8746b" opacity="0.32"/><ellipse cx="294" cy="362" rx="18" ry="8" fill="#e8746b" opacity="0.32"/>`
  if (f.tear) out += `<path d="M296 336 C292 350 290 360 296 366 C302 360 300 350 296 336 Z" fill="#9cc8ee" stroke="#5f8fb9" stroke-width="1.5"/>`
  if (f.sweat) out += `<path d="M328 250 C322 266 320 276 328 282 C336 276 334 266 328 250 Z" fill="#cfe6f7" stroke="#6f9cc2" stroke-width="2"/>`
  if (f.furrow) out += `<path d="M232 292 L236 300 M248 292 L244 300" stroke="${LINE}" stroke-width="2" opacity="0.55" stroke-linecap="round"/>`
  return out
}

function svgFor(ch, exprId) {
  const f = FACE[exprId]
  const [skin, shadow] = ch.skin
  const age = ch.age
    ? `<path d="M166 326 L156 322 M166 334 L158 336 M314 326 L324 322 M314 334 L322 336 M208 380 Q204 400 214 418 M272 380 Q276 400 266 418 M200 244 Q240 236 280 244" fill="none" stroke="${shadow}" stroke-width="2.4" stroke-linecap="round"/>`
    : ''
  const freckles = ch.freckles
    ? [176, 188, 200, 280, 292, 304].map((x, i) => `<circle cx="${x}" cy="${352 + (i % 2) * 6}" r="2" fill="${shadow}"/>`).join('')
    : ''
  const beard = ch.beard
    ? `<path d="M164 360 C172 418 206 450 240 452 C274 450 308 418 316 360 C302 400 280 420 240 422 C200 420 178 400 164 360 Z" fill="${ch.beard}" opacity="0.85"/><path d="M212 384 Q240 376 268 384 Q258 392 240 390 Q222 392 212 384 Z" fill="${ch.beard}"/>`
    : ''
  const glasses = ch.glasses
    ? `<g fill="none" stroke="${ch.glasses}" stroke-width="3.5"><rect x="168" y="300" width="64" height="44" rx="14"/><rect x="248" y="300" width="64" height="44" rx="14"/><path d="M232 318 Q240 312 248 318 M168 316 L152 310 M312 316 L328 310"/></g><path d="M176 306 L194 306" stroke="#fff" stroke-width="3" opacity="0.5"/>`
    : ''
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 720" width="480" height="720">
  <title>${ch.name}: ${EXPRESSIONS.find((e) => e.id === exprId).label} (sprite provisional)</title>
  ${hairBack(ch.hair)}
  ${clothes(ch.clothes)}
  <path d="M208 430 L208 548 Q240 566 272 548 L272 430 Z" fill="${skin}" stroke="${LINE}" stroke-width="3"/>
  <path d="M208 470 Q240 500 272 470 L272 446 L208 446 Z" fill="${shadow}" opacity="0.7"/>
  <ellipse cx="152" cy="324" rx="14" ry="22" fill="${skin}" stroke="${LINE}" stroke-width="3"/>
  <ellipse cx="328" cy="324" rx="14" ry="22" fill="${skin}" stroke="${LINE}" stroke-width="3"/>
  <path d="${face}" fill="${skin}" stroke="${LINE}" stroke-width="3.2" stroke-linejoin="round"/>
  <path d="M160 300 C170 260 200 236 240 236 C280 236 310 260 320 300 C300 274 274 262 240 262 C206 262 180 274 160 300 Z" fill="${shadow}" opacity="0.35"/>
  ${beard}
  ${age}
  ${freckles}
  ${brows(ch, f)}
  ${eye(200, 322, ch, f, -1)}
  ${eye(280, 322, ch, f, 1)}
  <path d="M240 340 L234 368 Q240 372 246 368" fill="none" stroke="${shadow}" stroke-width="3" stroke-linecap="round"/>
  ${mouth(f)}
  ${extras(ch, f)}
  ${glasses}
  ${hairFront(ch.hair)}
</svg>
`
}

async function main() {
  const characters = []
  for (const ch of CHARACTERS) {
    const dir = join(OUT, ch.id)
    await mkdir(dir, { recursive: true })
    for (const e of EXPRESSIONS) await writeFile(join(dir, `${e.id}.svg`), svgFor(ch, e.id))
    characters.push({
      id: ch.id,
      name: ch.name,
      profile: ch.profile,
      description: ch.description,
      status: 'provisional',
      defaultExpression: 'neutral',
      expressions: EXPRESSIONS.map((e) => ({ id: e.id, label: e.label, file: `${ch.id}/${e.id}.svg` })),
    })
  }
  const index = {
    version: 1,
    note: 'Sprites provisionales generados por scripts/generate-provisional-sprites.mjs. Sustituir por el arte final (WebP transparente, 480×720) manteniendo ids de personaje y de expresión.',
    characters,
  }
  await writeFile(join(OUT, 'index.json'), JSON.stringify(index, null, 2) + '\n')
  console.log(`Biblioteca provisional: ${characters.length} personajes × ${EXPRESSIONS.length} expresiones en public/sprite-library/`)
}

main()
