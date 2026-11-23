#!/usr/bin/env node
// Instalación de paquetes visuales en el frontend antes de desplegar.
//
//   npm run visual:install -- ruta/paquete-visual-<caso>.zip   valida e instala en public/visual-packages/<caso>/
//   npm run visual:index                                        regenera public/visual-packages/index.json
//   npm run visual:remove -- <id-del-caso>                      retira un paquete instalado
//
// Reutiliza la validación del frontend (src/lib/visual/package.ts), así que el script y el editor aplican
// exactamente las mismas reglas: formato, versión, rutas internas, PNG/WebP reales, tamaños y referencias.
// `npm run build` ejecuta `visual:index` antes de compilar (prebuild).
import { mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { detectImage, parsePackage, SPRITE_PATH_RE, validateManifest } from '../src/lib/visual/package.ts'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'visual-packages')
const LIBRARY = resolve(ROOT, '..', 'sprite-library', 'index.json')

/** Comprueba que el personaje del sistema referido exista en la biblioteca incluida en este frontend. */
async function checkLibrary(manifest) {
  const id = manifest.character.library
  if (!id) return
  let ok = false
  try {
    const lib = JSON.parse(await readFile(LIBRARY, 'utf8'))
    const ch = lib.characters?.find((c) => c.id === id)
    ok = Boolean(ch)
    const missing = ch ? manifest.expressions.filter((e) => !ch.expressions.some((x) => x.id === e.id)).map((e) => e.id) : []
    if (missing.length) console.warn(`Aviso: ${id} no tiene las expresiones ${missing.join(', ')}; se mostrará el personaje sin rostro en ellas.`)
  } catch {
    ok = false
  }
  if (!ok) console.warn(`Aviso: el personaje del sistema ${id} no está en public/sprite-library/; el caso se jugará con el personaje sin rostro.`)
}
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function inside(base, target) {
  const full = resolve(base, target)
  if (full !== base && !full.startsWith(base + sep)) throw new Error(`Ruta fuera de la carpeta del paquete: ${target}`)
  return full
}

async function exists(p) {
  try {
    await stat(p)
    return true
  } catch {
    return false
  }
}

async function install(zipPath) {
  if (!zipPath) throw new Error('Indica la ruta del paquete .zip exportado desde el editor.')
  const bytes = new Uint8Array(await readFile(zipPath))
  const { manifest, files } = await parsePackage(bytes)
  const dest = inside(ROOT, manifest.case.id)
  await rm(dest, { recursive: true, force: true })
  await mkdir(Object.keys(files).length ? join(dest, 'sprites') : dest, { recursive: true })
  await writeFile(join(dest, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
  for (const [name, data] of Object.entries(files)) await writeFile(inside(dest, name), data)
  await checkLibrary(manifest)
  const origin = manifest.character.library ? `personaje del sistema ${manifest.character.library}` : `${Object.keys(files).length} imágenes`
  console.log(`Instalado: ${manifest.case.nombre} (${manifest.case.id}) con ${origin}.`)
  await index()
}

async function readInstalled(caseId) {
  const dir = inside(ROOT, caseId)
  const manifest = validateManifest(JSON.parse(await readFile(join(dir, 'manifest.json'), 'utf8')))
  if (manifest.case.id !== caseId) throw new Error('la carpeta no coincide con el id del caso del manifiesto')
  for (const e of manifest.expressions) {
    if (!e.sprite) continue
    if (!SPRITE_PATH_RE.test(e.sprite)) throw new Error(`ruta no permitida ${e.sprite}`)
    const data = new Uint8Array(await readFile(inside(dir, e.sprite)))
    if (!detectImage(data)) throw new Error(`${e.sprite} no es PNG ni WebP`)
  }
  return manifest
}

async function index() {
  await mkdir(ROOT, { recursive: true })
  const packages = []
  for (const name of (await readdir(ROOT, { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name).sort()) {
    if (!UUID_RE.test(name)) {
      console.warn(`Se ignora ${name}: el nombre de la carpeta debe ser el id del caso.`)
      continue
    }
    try {
      const m = await readInstalled(name)
      const escenarioIds = [...new Set([...m.scenes.map((s) => s.escenarioId), ...m.reactions.map((r) => r.escenarioId)])]
      packages.push({ caseId: m.case.id, nombre: m.case.nombre, path: `${name}/manifest.json`, escenarioIds })
    } catch (err) {
      // Un paquete roto no rompe el build: el caso se juega con el personaje sin imagen.
      console.warn(`Se ignora el paquete ${name}: ${err.message}`)
    }
  }
  await writeFile(join(ROOT, 'index.json'), JSON.stringify({ version: 1, packages }, null, 2) + '\n')
  console.log(`Índice de paquetes visuales: ${packages.length} instalado(s).`)
}

async function remove(caseId) {
  if (!caseId || !UUID_RE.test(caseId)) throw new Error('Indica el id del caso (UUID).')
  const dir = inside(ROOT, caseId)
  if (!(await exists(dir))) throw new Error('No hay un paquete instalado para ese caso.')
  await rm(dir, { recursive: true, force: true })
  console.log(`Paquete retirado: ${caseId}`)
  await index()
}

const [cmd, arg] = process.argv.slice(2)
const actions = { install: () => install(arg), index, remove: () => remove(arg) }
if (!actions[cmd]) {
  console.error('Uso: visual-packages.mjs install <paquete.zip> | index | remove <id-del-caso>')
  process.exit(2)
}
actions[cmd]().catch((err) => {
  console.error(`Error: ${err.message}`)
  process.exit(1)
})
