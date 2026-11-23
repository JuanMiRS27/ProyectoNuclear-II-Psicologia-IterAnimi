/** Una sesión sin iniciar puede abrirse entre su inicio (incluido) y su fin (excluido). El servidor lo valida. */
export function canOpenNow(s: { estado: string; inicio: string; fin: string }, now: number) {
  return s.estado === 'SIN_INICIAR' && new Date(s.inicio).getTime() <= now && now < new Date(s.fin).getTime()
}

/** Hay intentos cerrados sin nota registrada (según los conteos del reporte del servidor). */
export function pendingEvaluation(s: { calificados: number; finalizados: number; expirados: number }) {
  return s.calificados < s.finalizados + s.expirados
}
