import type { Cuestionario } from '../types/api'

export function questionnaire(overrides: Partial<Cuestionario> = {}): Cuestionario {
  return {
    participacion_id: 'p1',
    estado: 'EN_PROGRESO',
    fecha_limite: '2026-11-18T10:00:00Z',
    tiempo_restante_segundos: 1200,
    caso: { nombre: 'Caso de prueba', desarrollo_situacional: 'Situación inicial.', historia: null },
    progreso: { total_preguntas: 3, respondidas: 0, pendientes: 3, porcentaje: 0 },
    escenarios: [
      {
        id: 'e2',
        orden: 2,
        titulo: 'Segunda escena',
        contexto: 'Contexto 2',
        preguntas: [{ id: 'q3', orden: 1, enunciado: 'Pregunta 3', opcion_seleccionada_id: null, opciones: [{ id: 'o5', orden: 1, texto: 'X' }, { id: 'o6', orden: 2, texto: 'Y' }] }],
      },
      {
        id: 'e1',
        orden: 1,
        titulo: 'Primera escena',
        contexto: 'Contexto 1',
        preguntas: [
          { id: 'q2', orden: 2, enunciado: 'Pregunta 2', opcion_seleccionada_id: null, opciones: [{ id: 'o3', orden: 1, texto: 'C' }, { id: 'o4', orden: 2, texto: 'D' }] },
          { id: 'q1', orden: 1, enunciado: 'Pregunta 1', opcion_seleccionada_id: null, opciones: [{ id: 'o1', orden: 1, texto: 'A' }, { id: 'o2', orden: 2, texto: 'B' }] },
        ],
      },
    ],
    ...overrides,
  }
}
