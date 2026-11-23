// Paquetes visuales instalados en el frontend servido (public/visual-packages/).
// El simulador los carga por URL relativa: no depende de IndexedDB, del equipo del docente ni de una API nueva.
// El cuestionario del estudiante no expone el id del caso, así que el índice relaciona cada paquete con los
// ids de sus escenas (únicos por caso) y se elige el paquete cuyas escenas coinciden con las del cuestionario.
import { libraryUrls, loadLibrary } from './library.ts'
import { validateManifest } from './package.ts'
import type { VisualManifest } from './types.ts'

export interface PackageIndex {
  version: 1
  packages: { caseId: string; path: string; escenarioIds: string[] }[]
}

export interface StaticPackage {
  manifest: VisualManifest
  /** URL absoluta de cada sprite por id de expresión (o null si no tiene imagen). */
  spriteUrls: Record<string, string | null>
}

const base = () => `${(import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/')}visual-packages/`

async function getJson(url: string): Promise<unknown | null> {
  try {
    const res = await fetch(url, { cache: 'no-cache' })
    if (!res.ok || !(res.headers.get('content-type') ?? '').includes('json')) return null
    return await res.json()
  } catch {
    return null
  }
}

/**
 * Busca el paquete instalado para un conjunto de escenas. Devuelve null si no hay paquete o si es inválido:
 * en ese caso el simulador usa el personaje sin imagen y el caso sigue siendo jugable.
 */
export async function loadStaticPackage(escenarioIds: string[]): Promise<StaticPackage | null> {
  const index = (await getJson(`${base()}index.json`)) as PackageIndex | null
  if (!index || !Array.isArray(index.packages)) return null
  const wanted = new Set(escenarioIds)
  const entry = index.packages.find((p) => Array.isArray(p.escenarioIds) && p.escenarioIds.some((id) => wanted.has(id)))
  if (!entry || typeof entry.path !== 'string' || entry.path.includes('..') || /^[a-z]+:|^\//i.test(entry.path)) return null
  const manifestUrl = new URL(entry.path, new URL(base(), location.origin))
  const json = await getJson(manifestUrl.href)
  if (!json) return null
  let manifest: VisualManifest
  try {
    manifest = validateManifest(json)
  } catch {
    return null
  }
  // Personaje del sistema: las imágenes vienen de la biblioteca estática (si falta, personaje sin rostro).
  if (manifest.character.library) return { manifest, spriteUrls: libraryUrls(await loadLibrary(), manifest) }
  const spriteUrls: Record<string, string | null> = {}
  for (const e of manifest.expressions) spriteUrls[e.id] = e.sprite ? new URL(e.sprite, manifestUrl).href : null
  return { manifest, spriteUrls }
}
