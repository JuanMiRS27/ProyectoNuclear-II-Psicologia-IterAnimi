// DTO de la API → modelo de vista del portal estudiantil.
// El estado se deriva solo de lo que dice el servidor (puede_iniciar_participacion, estados de intento,
// estado de la sesión). No se calcula ninguna regla de ventana ni de nota en el cliente.
import type { AccesoEstudiantil, Participacion, ResultadosEstudiante } from '../types/api'

export type StudentSessionStatus =
  | 'disponible' // puede iniciar un intento ahora
  | 'en_curso' // tiene un intento EN_PROGRESO
  | 'completado' // ya no tiene intentos abiertos y la sesión sigue en curso
  | 'plazo_cerrado' // sesión en curso, sin intentos y sin poder iniciar
  | 'finalizada' // la sesión terminó (acceso de resultados)

export interface StudentSessionView {
  mode: 'live' | 'results'
  casoNombre: string
  aula: { nombre: string; periodo: string }
  status: StudentSessionStatus
  estudiante?: string
  inicio?: string
  fin?: string
  limiteIngreso?: string
  tiempoMaxMin?: number
  lugar?: string | null
  mensaje?: string | null
  intentosAutorizados?: number
  intentosUsados: number
  intentoEnCurso?: Participacion
}

export const STATUS_LABEL: Record<StudentSessionStatus, string> = {
  disponible: 'Disponible',
  en_curso: 'En curso',
  completado: 'Completado',
  plazo_cerrado: 'Plazo de ingreso cerrado',
  finalizada: 'Sesión finalizada',
}

export function fromLiveAccess(acceso: AccesoEstudiantil, attempts: Participacion[]): StudentSessionView {
  const enCurso = attempts.find((p) => p.estado === 'EN_PROGRESO')
  const usados = attempts.length
  let status: StudentSessionStatus
  if (enCurso) status = 'en_curso'
  else if (acceso.puede_iniciar_participacion && usados < acceso.intentos_autorizados) status = 'disponible'
  else if (usados > 0) status = 'completado'
  else status = 'plazo_cerrado'
  return {
    mode: 'live',
    casoNombre: acceso.sesion.caso_nombre,
    aula: acceso.sesion.espacio_academico,
    status,
    estudiante: acceso.nombre_completo,
    inicio: acceso.sesion.inicio,
    fin: acceso.sesion.fin,
    limiteIngreso: acceso.sesion.limite_ingreso,
    tiempoMaxMin: acceso.sesion.tiempo_max_min,
    lugar: acceso.sesion.lugar,
    mensaje: acceso.sesion.mensaje,
    intentosAutorizados: acceso.intentos_autorizados,
    intentosUsados: usados,
    intentoEnCurso: enCurso,
  }
}

export function fromResults(r: ResultadosEstudiante): StudentSessionView {
  return {
    mode: 'results',
    casoNombre: r.caso_nombre,
    aula: r.espacio_academico,
    status: 'finalizada',
    intentosUsados: r.resultados.length,
  }
}

/** Hitos de la ventana de la sesión, en orden, para la agenda del estudiante. */
export function agendaOf(v: StudentSessionView) {
  if (!v.inicio || !v.fin || !v.limiteIngreso) return []
  return [
    { when: v.inicio, label: 'Inicio de la sesión' },
    { when: v.limiteIngreso, label: 'Último momento para empezar un intento' },
    { when: v.fin, label: 'Fin programado de la sesión' },
  ]
}
