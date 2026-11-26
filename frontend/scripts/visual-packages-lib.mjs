// Instalación de paquetes visuales en una carpeta estática del frontend.
// La comparten el script de línea de órdenes (scripts/visual-packages.mjs) y el plugin de publicación del servidor
// del frontend (scripts/vite-visual-publish.mjs), así que ambos aplican exactamente la misma validación que el editor
// (src/lib/visual/package.ts): formato, versión, rutas internas, PNG/WebP reales, tamaños y referencias.
import { mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { detectImage, parsePackage, SPRITE_PATH_RE, validateManifest } from '../src/lib/visual/package.ts'

export const PUBLIC_PACKAGES = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'visual-packages')
const LIBRARY = resolve(PUBLIC_PACKAGES, '..', 'sprite-library', 'index.json')
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

/** Avisos (no errores) si el personaje del sistema referido no está en la biblioteca incluida en este frontend. */
export async function libraryWarnings(manifest) {
  const id = manifest.character.library
  if (!id) return []
  try {
    const lib = JSON.parse(await readFile(LIBRARY, 'utf8'))
    const ch = lib.characters?.find((c) => c.id === id)
    if (!ch) return [`El personaje del sistema ${id} no está en public/sprite-library/; el caso se jugará con el personaje sin rostro.`]
    const missing = manifest.expressions.filter((e) => !ch.expressions.some((x) => x.id === e.id)).map((e) => e.id)
    return missing.length ? [`${id} no tiene las expresiones ${missing.join(', ')}; en ellas se mostrará el personaje sin rostro.`] : []
  } catch {
    return [`No se pudo leer la biblioteca de personajes; el caso se jugará con el personaje sin rostro.`]
  }
}

/** Valida e instala los bytes de un paquete ZIP en <root>/<id-del-caso>/ y regenera el índice. */
export async function installPackage(bytes, root = PUBLIC_PACKAGES) {
  const { manifest, files } = await parsePackage(bytes)
  const dest = inside(root, manifest.case.id)
  await rm(dest, { recursive: true, force: true })
  await mkdir(Object.keys(files).length ? join(dest, 'sprites') : dest, { recursive: true })
  await writeFile(join(dest, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n')
  for (const [name, data] of Object.entries(files)) await writeFile(inside(dest, name), data)
  const count = await rebuildIndex(root)
  return { manifest, images: Object.keys(files).length, warnings: await libraryWarnings(manifest), installed: count }
}

async function readInstalled(root, caseId) {
  const dir = inside(root, caseId)
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

/** Regenera <root>/index.json a partir de las carpetas instaladas. Devuelve cuántos paquetes quedaron. */
export async function rebuildIndex(root = PUBLIC_PACKAGES, log = () => {}) {
  await mkdir(root, { recursive: true })
  const packages = []
  for (const name of (await readdir(root, { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name).sort()) {
    if (!UUID_RE.test(name)) {
      log(`Se ignora ${name}: el nombre de la carpeta debe ser el id del caso.`)
      continue
    }
    try {
      const m = await readInstalled(root, name)
      const escenarioIds = [...new Set([...m.scenes.map((s) => s.escenarioId), ...m.reactions.map((r) => r.escenarioId)])]
      packages.push({ caseId: m.case.id, nombre: m.case.nombre, path: `${name}/manifest.json`, escenarioIds })
    } catch (err) {
      // Un paquete roto no rompe el build: el caso se juega con el personaje sin imagen.
      log(`Se ignora el paquete ${name}: ${err.message}`)
    }
  }
  await writeFile(join(root, 'index.json'), JSON.stringify({ version: 1, packages }, null, 2) + '\n')
  return packages.length
}

/** Retira el paquete de un caso. */
export async function removePackage(caseId, root = PUBLIC_PACKAGES) {
  if (!caseId || !UUID_RE.test(caseId)) throw new Error('Indica el id del caso (UUID).')
  const dir = inside(root, caseId)
  if (!(await exists(dir))) throw new Error('No hay un paquete instalado para ese caso.')
  await rm(dir, { recursive: true, force: true })
  return rebuildIndex(root)
}
