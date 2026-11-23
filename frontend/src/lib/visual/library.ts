// Biblioteca de personajes del sistema: recursos estáticos del frontend (public/sprite-library/).
// Disponibles en cualquier equipo donde esté desplegada la aplicación, sin IndexedDB ni API: el manifiesto solo guarda
// el id del personaje (character.library) y las imágenes se resuelven aquí por id de expresión.
import { SYSTEM_ID_RE } from './package.ts'
import type { ExpressionDef, VisualManifest } from './types.ts'

export interface LibraryExpression {
  id: string
  label: string
  /** Ruta relativa a sprite-library/ (personaje/expresión.ext). */
  file: string
}

export interface LibraryCharacter {
  id: string
  name: string
  profile: string
  description: string
  /** «provisional» mientras no se instale el arte final. */
  status: 'provisional' | 'final'
  defaultExpression: string
  expressions: LibraryExpression[]
}

export interface LibraryCatalog {
  version: 1
  characters: LibraryCharacter[]
}

const EXPR_ID_RE = /^[a-z0-9][a-z0-9_-]{0,31}$/
/** Solo rutas internas de la biblioteca: sin «..», absolutas ni externas. */
export const LIBRARY_FILE_RE = /^system-[a-z0-9-]+\/[a-z0-9][a-z0-9_-]{0,40}\.(webp|png|svg)$/

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

/** Valida el catálogo; descarta personajes mal formados en lugar de romper todo. */
export function validateCatalog(value: unknown): LibraryCatalog | null {
  if (!isObj(value) || value.version !== 1 || !Array.isArray(value.characters)) return null
  const characters: LibraryCharacter[] = []
  for (const c of value.characters as unknown[]) {
    if (!isObj(c) || typeof c.id !== 'string' || !SYSTEM_ID_RE.test(c.id) || typeof c.name !== 'string' || !Array.isArray(c.expressions)) continue
    const expressions = (c.expressions as unknown[]).filter(
      (e): e is LibraryExpression =>
        isObj(e) && typeof e.id === 'string' && EXPR_ID_RE.test(e.id) && typeof e.label === 'string' && typeof e.file === 'string' && LIBRARY_FILE_RE.test(e.file) && e.file.startsWith(`${c.id}/`),
    )
    if (expressions.length === 0) continue
    const def = typeof c.defaultExpression === 'string' && expressions.some((e) => e.id === c.defaultExpression) ? c.defaultExpression : expressions[0]!.id
    characters.push({
      id: c.id,
      name: c.name,
      profile: typeof c.profile === 'string' ? c.profile : '',
      description: typeof c.description === 'string' ? c.description : '',
      status: c.status === 'final' ? 'final' : 'provisional',
      defaultExpression: def,
      expressions,
    })
  }
  return { version: 1, characters }
}

export const libraryBase = () => `${(import.meta.env?.BASE_URL ?? '/').replace(/\/?$/, '/')}sprite-library/`

/** Carga el catálogo servido por el frontend. null si falta o es inválido (el editor y el simulador siguen funcionando). */
export async function loadLibrary(): Promise<LibraryCatalog | null> {
  try {
    const res = await fetch(`${libraryBase()}index.json`, { cache: 'no-cache' })
    if (!res.ok || !(res.headers.get('content-type') ?? '').includes('json')) return null
    return validateCatalog(await res.json())
  } catch {
    return null
  }
}

/**
 * URL de cada expresión del manifiesto para un personaje del sistema.
 * Si el personaje o una expresión no existen en la biblioteca servida, la URL es null y se usa el personaje sin rostro.
 */
export function libraryUrls(catalog: LibraryCatalog | null, manifest: VisualManifest): Record<string, string | null> {
  const ch = catalog?.characters.find((c) => c.id === manifest.character.library)
  const out: Record<string, string | null> = {}
  for (const e of manifest.expressions) {
    const file = ch?.expressions.find((x) => x.id === e.id)?.file
    out[e.id] = file ? new URL(file, new URL(libraryBase(), location.origin)).href : null
  }
  return out
}

/** Equivalencias narrativas entre las expresiones de partida propias y las del sistema (en ambos sentidos). */
const COMPATIBLE: Record<string, string[]> = {
  inquieto: ['preocupado'],
  aliviado: ['feliz'],
  preocupado: ['inquieto'],
  feliz: ['aliviado'],
}

export interface RemapReport {
  /** Asociaciones que pasaron a una expresión equivalente: [antes, después]. */
  remapped: [string, string][]
  /** Expresiones sin equivalente: sus reacciones vuelven a «Sin cambio» y las escenas a la expresión por defecto. */
  dropped: string[]
}

/** Cambia el conjunto de expresiones conservando las asociaciones compatibles. */
export function remapToExpressions(
  manifest: VisualManifest,
  expressions: ExpressionDef[],
  defaultExpression: string,
  library: string | null,
): { manifest: VisualManifest; report: RemapReport } {
  const ids = new Set(expressions.map((e) => e.id))
  const report: RemapReport = { remapped: [], dropped: [] }
  const map = (id: string | null): string | null => {
    if (id === null || ids.has(id)) return id
    const alt = COMPATIBLE[id]?.find((x) => ids.has(x))
    if (alt) {
      if (!report.remapped.some(([a]) => a === id)) report.remapped.push([id, alt])
      return alt
    }
    if (!report.dropped.includes(id)) report.dropped.push(id)
    return null
  }
  const reactions = manifest.reactions.flatMap((r) => {
    const expression = map(r.expression)
    return expression === null ? [] : [{ ...r, expression }]
  })
  const scenes = manifest.scenes.map((s) => ({ ...s, initialExpression: map(s.initialExpression) }))
  return {
    manifest: {
      ...manifest,
      character: { ...manifest.character, defaultExpression: ids.has(defaultExpression) ? defaultExpression : expressions[0]!.id, library },
      expressions,
      scenes,
      reactions,
    },
    report,
  }
}

/** Expresiones del manifiesto para un personaje del sistema (sin imágenes propias; etiquetas de la biblioteca). */
export function systemExpressions(ch: LibraryCharacter): ExpressionDef[] {
  return ch.expressions.map((e) => ({ id: e.id, label: e.label, sprite: null }))
}
