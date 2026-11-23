// Validación del manifiesto y conversión borrador ↔ paquete ZIP.
// Lo usan el editor (exportar/importar), el simulador (paquete estático) y scripts/visual-packages.mjs.
import { LIMITS, MOTIONS, PACKAGE_FORMAT, PACKAGE_VERSION, SUPPORTED_VERSIONS, type ExpressionDef, type VisualManifest } from './types.ts'
import { readZip, writeZip, ZipError, type ZipEntry } from './zip.ts'

export class PackageError extends Error {}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const EXPR_ID_RE = /^[a-z0-9][a-z0-9_-]{0,31}$/
const SIG_RE = /^[0-9a-f]{8}$/
/** Id de un personaje de la biblioteca del sistema. */
export const SYSTEM_ID_RE = /^system-[a-z0-9]+(-[a-z0-9]+){0,8}$/
/** Únicas rutas admitidas dentro de un paquete: sin carpetas superiores, absolutas ni externas. */
export const SPRITE_PATH_RE = /^sprites\/[a-z0-9][a-z0-9_-]{0,40}\.(png|webp)$/

export type ImageKind = 'png' | 'webp'

/** Formato real de la imagen por su firma de bytes (no por la extensión). */
export function detectImage(bytes: Uint8Array): ImageKind | null {
  const png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]
  if (bytes.length > 8 && png.every((b, i) => bytes[i] === b)) return 'png'
  const ascii = (a: number, b: number) => String.fromCharCode(...bytes.subarray(a, b))
  if (bytes.length > 12 && ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP') return 'webp'
  return null
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const str = (v: unknown, max: number) => typeof v === 'string' && v.trim().length > 0 && v.length <= max

/** Valida la estructura del manifiesto. Lanza PackageError con un mensaje legible. */
export function validateManifest(value: unknown): VisualManifest {
  if (!isObj(value)) throw new PackageError('El manifiesto no es un objeto JSON.')
  if (value.format !== PACKAGE_FORMAT) throw new PackageError('El archivo no es un paquete visual de Iter Animi.')
  if (!SUPPORTED_VERSIONS.includes(value.version as never)) throw new PackageError(`Versión de paquete no admitida (${String(value.version)}).`)
  const c = value.case
  if (!isObj(c) || typeof c.id !== 'string' || !UUID_RE.test(c.id) || !str(c.nombre, 300))
    throw new PackageError('El paquete no identifica correctamente el caso.')
  const ch = value.character
  if (!isObj(ch) || typeof ch.name !== 'string' || ch.name.length > LIMITS.nameMax || typeof ch.defaultExpression !== 'string')
    throw new PackageError('Los datos del personaje no son válidos.')
  const library = ch.library ?? null
  if (library !== null && (value.version !== 2 || typeof library !== 'string' || !SYSTEM_ID_RE.test(library)))
    throw new PackageError('El personaje del sistema indicado no tiene un identificador válido.')
  if (!Array.isArray(value.expressions) || value.expressions.length < 1 || value.expressions.length > LIMITS.maxExpressions)
    throw new PackageError(`El paquete debe tener entre 1 y ${LIMITS.maxExpressions} expresiones.`)
  const ids = new Set<string>()
  const sprites = new Set<string>()
  for (const e of value.expressions as unknown[]) {
    if (!isObj(e) || typeof e.id !== 'string' || !EXPR_ID_RE.test(e.id) || !str(e.label, LIMITS.labelMax))
      throw new PackageError('Hay una expresión con identificador o etiqueta no válidos.')
    if (ids.has(e.id)) throw new PackageError(`La expresión «${e.id}» está repetida.`)
    ids.add(e.id)
    if (e.sprite !== null && library !== null)
      throw new PackageError('Un paquete con personaje del sistema no puede incluir imágenes propias.')
    if (e.sprite !== null) {
      if (typeof e.sprite !== 'string' || !SPRITE_PATH_RE.test(e.sprite))
        throw new PackageError(`La imagen de «${e.label as string}» apunta a una ruta no permitida.`)
      if (sprites.has(e.sprite)) throw new PackageError(`La imagen ${e.sprite} está asignada dos veces.`)
      sprites.add(e.sprite)
    }
  }
  if (!ids.has(ch.defaultExpression)) throw new PackageError('La expresión por defecto no existe en el paquete.')
  const exprRef = (v: unknown) => v === null || (typeof v === 'string' && ids.has(v))
  if (!Array.isArray(value.scenes) || !Array.isArray(value.reactions)) throw new PackageError('Faltan las escenas o las reacciones.')
  for (const s of value.scenes as unknown[]) {
    if (!isObj(s) || typeof s.escenarioId !== 'string' || !UUID_RE.test(s.escenarioId) || typeof s.signature !== 'string' || !SIG_RE.test(s.signature) || !exprRef(s.initialExpression))
      throw new PackageError('Hay una escena mal configurada en el paquete.')
  }
  for (const r of value.reactions as unknown[]) {
    if (
      !isObj(r) ||
      ![r.opcionId, r.preguntaId, r.escenarioId].every((x) => typeof x === 'string' && UUID_RE.test(x)) ||
      typeof r.signature !== 'string' ||
      !SIG_RE.test(r.signature) ||
      !exprRef(r.expression) ||
      !MOTIONS.includes(r.motion as never)
    )
      throw new PackageError('Hay una reacción mal configurada en el paquete.')
  }
  return value as unknown as VisualManifest
}

export function extensionFor(kind: ImageKind) {
  return kind === 'png' ? 'png' : 'webp'
}

/** Construye el ZIP: manifest.json + sprites/<expresión>.<ext>. Las rutas son relativas al paquete. */
export async function buildPackage(manifest: VisualManifest, images: Record<string, Blob>): Promise<Uint8Array> {
  const entries: ZipEntry[] = []
  const expressions: ExpressionDef[] = []
  // Personaje del sistema: solo la referencia, sin copiar imágenes al paquete.
  const library = manifest.character.library ?? null
  for (const e of manifest.expressions) {
    const blob = library ? undefined : images[e.id]
    if (!blob) {
      expressions.push({ ...e, sprite: null })
      continue
    }
    const data = new Uint8Array(await blob.arrayBuffer())
    const kind = detectImage(data)
    if (!kind) throw new PackageError(`La imagen de «${e.label}» no es PNG ni WebP.`)
    const path = `sprites/${e.id}.${extensionFor(kind)}`
    entries.push({ name: path, data })
    expressions.push({ ...e, sprite: path })
  }
  const finalManifest: VisualManifest = { ...manifest, version: PACKAGE_VERSION, character: { ...manifest.character, library }, expressions, createdAt: new Date().toISOString() }
  validateManifest(finalManifest)
  const json = new TextEncoder().encode(JSON.stringify(finalManifest, null, 2))
  return writeZip([{ name: 'manifest.json', data: json }, ...entries])
}

export interface ParsedPackage {
  manifest: VisualManifest
  /** Bytes por ruta relativa (sprites/x.png). */
  files: Record<string, Uint8Array>
}

/** Lee y valida un paquete ZIP: estructura, rutas, formatos reales, tamaños y referencias. */
export async function parsePackage(bytes: Uint8Array): Promise<ParsedPackage> {
  if (bytes.length > LIMITS.maxPackageBytes) throw new PackageError('El paquete supera los 20 MB permitidos.')
  let entries: ZipEntry[]
  try {
    entries = await readZip(bytes, { maxEntries: LIMITS.maxEntries, maxTotalBytes: LIMITS.maxPackageBytes })
  } catch (err) {
    throw new PackageError(err instanceof ZipError ? err.message : 'No se pudo leer el paquete.')
  }
  const files: Record<string, Uint8Array> = {}
  let manifestBytes: Uint8Array | null = null
  for (const e of entries) {
    if (e.name === 'manifest.json') {
      manifestBytes = e.data
      continue
    }
    if (!SPRITE_PATH_RE.test(e.name)) throw new PackageError(`Archivo no permitido en el paquete: ${e.name}`)
    if (e.data.length > LIMITS.maxImageBytes) throw new PackageError(`${e.name} supera los 2 MB por imagen.`)
    const kind = detectImage(e.data)
    if (!kind || !e.name.endsWith(`.${extensionFor(kind)}`)) throw new PackageError(`${e.name} no es una imagen PNG o WebP válida.`)
    files[e.name] = e.data
  }
  if (!manifestBytes) throw new PackageError('Al paquete le falta manifest.json.')
  let json: unknown
  try {
    json = JSON.parse(new TextDecoder().decode(manifestBytes))
  } catch {
    throw new PackageError('manifest.json no es un JSON válido.')
  }
  const manifest = validateManifest(json)
  for (const e of manifest.expressions) {
    if (e.sprite && !files[e.sprite]) throw new PackageError(`Falta la imagen ${e.sprite} referida por «${e.label}».`)
  }
  const referenced = new Set(manifest.expressions.map((e) => e.sprite).filter(Boolean))
  for (const name of Object.keys(files)) if (!referenced.has(name)) throw new PackageError(`La imagen ${name} no está referida en el manifiesto.`)
  return { manifest, files }
}
