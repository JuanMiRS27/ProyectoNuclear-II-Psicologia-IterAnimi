// Estado de ánimo del personaje a partir de su expresión: decide la animación continua (respiración, temblor…)
// mientras la expresión está en pantalla. Funciona con los ids del sistema y con expresiones propias del docente
// (se busca por palabras clave en el id y en la etiqueta).

export type Mood = 'calm' | 'happy' | 'sad' | 'anxious' | 'uneasy' | 'angry' | 'surprised' | 'thoughtful'

const RULES: [Mood, RegExp][] = [
  ['angry', /enoj|enfad|ira|furi|rabi|molest|agresiv|frustr|colera|irrit/],
  ['anxious', /preocup|inquiet|ansi|nervi|miedo|asust|temor|angust|panico|estres|tens/],
  ['surprised', /sorpr|asombr|impact|shock/],
  ['uneasy', /incomod|avergonz|verguenz|culpa|incert|confus|dud/],
  ['sad', /trist|llor|deprim|dolor|desanim|abatid|melanc|desol|cansad/],
  ['happy', /feliz|alegr|content|aliviad|sonr|satisf|tranquil|esperanz|agradec/],
  ['thoughtful', /reflex|pensat|concentr|serio|analiz|curios/],
]

const normalize = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')

/** Ánimo de una expresión; «calm» (respiración tranquila) si no se reconoce. */
export function moodFor(expression: string, label?: string | null): Mood {
  const text = normalize(`${expression} ${label ?? ''}`)
  for (const [mood, re] of RULES) if (re.test(text)) return mood
  return 'calm'
}
