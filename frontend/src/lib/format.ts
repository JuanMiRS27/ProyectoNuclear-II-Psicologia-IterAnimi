// Presentación de fechas y cifras en español. Los cálculos académicos los hace siempre el servidor.

const fechaHora = new Intl.DateTimeFormat('es-CO', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
})
const fechaLarga = new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
const soloFecha = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
const soloHora = new Intl.DateTimeFormat('es-CO', { hour: 'numeric', minute: '2-digit' })
const diaCorto = new Intl.DateTimeFormat('es-CO', { weekday: 'short', day: 'numeric', month: 'short' })

export const formatDateTime = (iso: string) => fechaHora.format(new Date(iso))
export const formatLongDate = (iso: string) => fechaLarga.format(new Date(iso))
export const formatDate = (iso: string) => soloFecha.format(new Date(iso))
export const formatTime = (iso: string) => soloHora.format(new Date(iso))
export const formatShortDay = (iso: string) => diaCorto.format(new Date(iso))

export function formatRange(inicio: string, fin: string) {
  const a = new Date(inicio)
  const b = new Date(fin)
  const mismoDia = a.toDateString() === b.toDateString()
  return mismoDia ? `${formatDateTime(inicio)} – ${formatTime(fin)}` : `${formatDateTime(inicio)} – ${formatDateTime(fin)}`
}

/** "3.40" → "3,40". Solo para mostrar: no se recalcula nada. */
export function formatDecimal(value: string | null | undefined, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return value
  return n.toLocaleString('es-CO', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function formatPercent(value: string | null | undefined) {
  if (value === null || value === undefined) return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('es-CO', { maximumFractionDigits: 1 })} %`
}

export function formatCountdown(totalSeconds: number) {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(m).padStart(h ? 2 : 1, '0')
  const ss = String(sec).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

export function plural(n: number, uno: string, varios: string) {
  return `${n} ${n === 1 ? uno : varios}`
}

/** Valor para <input type="datetime-local"> en la zona horaria del navegador. */
export function toLocalInput(date: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** "2026-11-18T08:00" (hora local) → ISO con desplazamiento explícito, como exige el backend. */
export function localInputToIso(value: string) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  const off = -d.getTimezoneOffset()
  const sign = off >= 0 ? '+' : '-'
  const abs = Math.abs(off)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${value.length === 16 ? `${value}:00` : value}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Separa correos por comas, punto y coma, espacios o saltos de línea. */
export function parseEmails(text: string) {
  return [
    ...new Set(
      text
        .split(/[\s,;]+/)
        .map((e) => e.trim().toLowerCase())
        .filter(Boolean),
    ),
  ]
}

export const optionLetter = (index: number) => String.fromCharCode(65 + index)
