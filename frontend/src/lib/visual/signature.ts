// Huellas de contenido (FNV-1a de 32 bits). No son seguridad: detectan que el texto de una escena
// u opción cambió desde que se configuró su reacción, para no mostrar una reacción equivocada.

function fnv1a(text: string): string {
  let h = 0x811c9dc5
  for (const ch of new TextEncoder().encode(text)) {
    h ^= ch
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

const norm = (s: string | null | undefined) => (s ?? '').replace(/\s+/g, ' ').trim()

export const sceneSignature = (titulo: string) => fnv1a(`escena|${norm(titulo)}`)

export const optionSignature = (enunciado: string, texto: string) => fnv1a(`opcion|${norm(enunciado)}|${norm(texto)}`)
