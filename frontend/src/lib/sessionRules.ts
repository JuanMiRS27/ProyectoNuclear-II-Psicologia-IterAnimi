/** Una sesión sin iniciar puede abrirse entre su inicio (incluido) y su fin (excluido). El servidor lo valida. */
export function canOpenNow(s: { estado: string; inicio: string; fin: string }, now: number) {
  return s.estado === 'SIN_INICIAR' && new Date(s.inicio).getTime() <= now && now < new Date(s.fin).getTime()
}
