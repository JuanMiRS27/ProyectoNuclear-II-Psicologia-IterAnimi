// Paquete visual de un caso: personaje, sprites y reacciones por decisión.
// Es dirección narrativa, no evaluación: nunca contiene claves, rúbricas ni opciones correctas.
// Vive solo en el frontend (borrador en IndexedDB → paquete exportado → carpeta estática del despliegue).

export const PACKAGE_FORMAT = 'iter-animi-paquete-visual'
/** Versión que se escribe al exportar. La 2 añade personajes de la biblioteca del sistema; la 1 sigue siendo válida. */
export const PACKAGE_VERSION = 2
export const SUPPORTED_VERSIONS = [1, 2] as const

export type Motion = 'fade' | 'rise' | 'breathe' | 'none'
export const MOTIONS: Motion[] = ['fade', 'rise', 'breathe', 'none']

export interface ExpressionDef {
  /** Identificador estable dentro del paquete (minúsculas, cifras, guion). */
  id: string
  /** Etiqueta editable que ve el docente. */
  label: string
  /**
   * Ruta relativa dentro del paquete (sprites/x.png) o null. Con un personaje del sistema siempre es null: la imagen
   * se resuelve desde la biblioteca estática del frontend por el id de la expresión.
   */
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
  version: (typeof SUPPORTED_VERSIONS)[number]
  case: { id: string; nombre: string }
  character: {
    name: string
    defaultExpression: string
    /** Id estable de un personaje del sistema (p. ej. system-young-adult-m-01); ausente o null = sprites propios. */
    library?: string | null
  }
  expressions: ExpressionDef[]
  scenes: SceneDef[]
  reactions: ReactionDef[]
  createdAt: string
}

/** Borrador local: el manifiesto más las imágenes en memoria (Blob por expresión). */
export interface VisualDraft {
  manifest: VisualManifest
  /** Solo sprites propios. Los del sistema nunca se copian aquí: se guardan como referencia en el manifiesto. */
  images: Record<string, Blob>
  /** Personaje propio guardado mientras se usa uno del sistema, para poder volver a él sin perderlo. */
  stash?: { expressions: ExpressionDef[]; images: Record<string, Blob>; defaultExpression: string } | null
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
