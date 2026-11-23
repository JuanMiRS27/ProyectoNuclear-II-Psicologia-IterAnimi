// Resuelve qué expresión mostrar a partir del manifiesto y del contenido REAL del caso.
// Las asociaciones usan los identificadores de escena, pregunta y opción que expone la API; la letra A/B/C/D
// nunca es clave. Si el contenido cambió (huella distinta o id inexistente), la asociación se ignora y se usa
// la expresión inicial o por defecto: nunca se muestra una reacción equivocada.
import { DEFAULT_EXPRESSIONS, PACKAGE_FORMAT, PACKAGE_VERSION, type Motion, type ReactionDef, type VisualManifest } from './types.ts'
import { optionSignature, sceneSignature } from './signature.ts'

/** Forma común al caso del docente (CasoDetalle) y al cuestionario del estudiante. */
export interface ContentLike {
  escenarios: {
    id: string
    titulo: string
    preguntas: { id: string; enunciado: string; opciones: { id: string; texto: string }[] }[]
  }[]
}

export interface ReactionResult {
  expression: string
  motion: Motion
}

export type IssueKind = 'opcion-inexistente' | 'opcion-cambiada' | 'escena-inexistente' | 'escena-cambiada'
export interface Issue {
  kind: IssueKind
  id: string
}

export interface VisualRuntime {
  characterName: string
  defaultExpression: string
  label: (expression: string) => string
  /** Expresión inicial de una escena (o la por defecto si no hay una válida). */
  initialFor: (escenarioId: string) => string
  /** Reacción de una opción; null = sin cambio (o asociación no válida). */
  reactionFor: (opcionId: string) => ReactionResult | null
  issues: Issue[]
  /** Reacciones válidas por id de opción (para el editor). */
  validReactions: Map<string, ReactionDef>
}

export function buildRuntime(manifest: VisualManifest, content: ContentLike): VisualRuntime {
  const exprIds = new Set(manifest.expressions.map((e) => e.id))
  const def = exprIds.has(manifest.character.defaultExpression) ? manifest.character.defaultExpression : manifest.expressions[0]!.id
  const scenes = new Map(content.escenarios.map((e) => [e.id, e]))
  const options = new Map<string, { preguntaId: string; escenarioId: string; signature: string }>()
  for (const e of content.escenarios)
    for (const p of e.preguntas)
      for (const o of p.opciones) options.set(o.id, { preguntaId: p.id, escenarioId: e.id, signature: optionSignature(p.enunciado, o.texto) })

  const issues: Issue[] = []
  const initial = new Map<string, string>()
  for (const s of manifest.scenes) {
    const real = scenes.get(s.escenarioId)
    if (!real) {
      issues.push({ kind: 'escena-inexistente', id: s.escenarioId })
      continue
    }
    if (sceneSignature(real.titulo) !== s.signature) {
      issues.push({ kind: 'escena-cambiada', id: s.escenarioId })
      continue
    }
    if (s.initialExpression && exprIds.has(s.initialExpression)) initial.set(s.escenarioId, s.initialExpression)
  }

  const valid = new Map<string, ReactionDef>()
  for (const r of manifest.reactions) {
    const real = options.get(r.opcionId)
    if (!real || real.preguntaId !== r.preguntaId || real.escenarioId !== r.escenarioId) {
      issues.push({ kind: 'opcion-inexistente', id: r.opcionId })
      continue
    }
    if (real.signature !== r.signature) {
      issues.push({ kind: 'opcion-cambiada', id: r.opcionId })
      continue
    }
    if (r.expression === null || exprIds.has(r.expression)) valid.set(r.opcionId, r)
  }

  const labels = new Map(manifest.expressions.map((e) => [e.id, e.label]))
  return {
    characterName: manifest.character.name,
    defaultExpression: def,
    label: (e) => labels.get(e) ?? e,
    initialFor: (id) => initial.get(id) ?? def,
    reactionFor: (id) => {
      const r = valid.get(id)
      return r && r.expression ? { expression: r.expression, motion: r.motion } : null
    },
    issues,
    validReactions: valid,
  }
}

/** Borrador nuevo para un caso: expresiones de partida editables, sin imágenes ni reacciones. */
export function emptyManifest(caso: { id: string; nombre: string } & ContentLike): VisualManifest {
  return {
    format: PACKAGE_FORMAT,
    version: PACKAGE_VERSION,
    case: { id: caso.id, nombre: caso.nombre },
    character: { name: '', defaultExpression: 'neutral' },
    expressions: DEFAULT_EXPRESSIONS.map((e) => ({ ...e, sprite: null })),
    scenes: caso.escenarios.map((e) => ({ escenarioId: e.id, signature: sceneSignature(e.titulo), initialExpression: null })),
    reactions: [],
    createdAt: new Date().toISOString(),
  }
}
