// Paquete visual de un caso: personaje, sprites y reacciones por decisión.
// Es dirección narrativa, no evaluación: nunca contiene claves, rúbricas ni opciones correctas.
// Vive solo en el frontend (borrador en IndexedDB → paquete exportado → carpeta estática del despliegue).

export const PACKAGE_FORMAT = 'iter-animi-paquete-visual'
export const PACKAGE_VERSION = 1

export type Motion = 'fade' | 'rise' | 'breathe' | 'none'
export const MOTIONS: Motion[] = ['fade', 'rise', 'breathe', 'none']

export interface ExpressionDef {
  /** Identificador estable dentro del paquete (minúsculas, cifras, guion). */
  id: string
  /** Etiqueta editable que ve el docente. */
  label: string
  /** Ruta relativa dentro del paquete (sprites/x.png) o null si usa el personaje sin imagen. */
  sprite: string | null
}

export interface SceneDef {
  escenarioId: string
  /** Huella del título de la escena: si cambia, la configuración queda pendiente de revisión. */
  signature: string
  initialExpression: string | null
}

export interface ReactionDef {
  opcionId: string
  preguntaId: string
  escenarioId: string
  /** Huella de enunciado + texto de la opción. */
  signature: string
  /** null = «Sin cambio». */
  expression: string | null
  motion: Motion
}

export interface VisualManifest {
  format: typeof PACKAGE_FORMAT
  version: typeof PACKAGE_VERSION
  case: { id: string; nombre: string }
  character: { name: string; defaultExpression: string }
  expressions: ExpressionDef[]
  scenes: SceneDef[]
  reactions: ReactionDef[]
  createdAt: string
}

/** Borrador local: el manifiesto más las imágenes en memoria (Blob por expresión). */
export interface VisualDraft {
  manifest: VisualManifest
  images: Record<string, Blob>
  savedAt?: string
}

export const LIMITS = {
  maxExpressions: 12,
  maxImageBytes: 2 * 1024 * 1024,
  maxPackageBytes: 20 * 1024 * 1024,
  maxEntries: 64,
  labelMax: 40,
  nameMax: 60,
} as const

export const DEFAULT_EXPRESSIONS: { id: string; label: string }[] = [
  { id: 'neutral', label: 'Neutral' },
  { id: 'inquieto', label: 'Inquieto' },
  { id: 'incomodo', label: 'Incómodo' },
  { id: 'reflexivo', label: 'Reflexivo' },
  { id: 'aliviado', label: 'Aliviado' },
]
