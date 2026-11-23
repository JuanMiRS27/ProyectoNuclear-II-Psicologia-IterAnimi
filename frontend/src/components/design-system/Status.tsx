// Motivo propio de Iter Animi: un círculo que se llena según el avance.
// El estado nunca depende solo del color: forma + texto siempre presentes.

export type Fill = 'empty' | 'half' | 'full' | 'alert'

export function Glyph({ fill, size = 14 }: { fill: Fill; size?: number }) {
  const r = 6
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      {fill === 'alert' ? (
        <>
          <circle cx="8" cy="8" r={r} fill="none" stroke="var(--danger)" strokeWidth="1.8" />
          <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="var(--danger)" strokeWidth="1.8" strokeLinecap="round" />
        </>
      ) : (
        <>
          <circle cx="8" cy="8" r={r} fill={fill === 'full' ? 'currentColor' : 'var(--surface)'} stroke="currentColor" strokeWidth="1.8" />
          {fill === 'half' && <path d={`M8 2 A${r} ${r} 0 0 1 8 14 Z`} fill="currentColor" />}
        </>
      )}
    </svg>
  )
}

export function Status({ fill, children, tone }: { fill: Fill; children: React.ReactNode; tone?: 'muted' | 'alert' }) {
  return (
    <span className={`status${tone ? ` status-${tone}` : ''}`}>
      <Glyph fill={fill} />
      {children}
    </span>
  )
}
