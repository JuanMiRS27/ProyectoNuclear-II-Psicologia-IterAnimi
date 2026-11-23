/** Marca de Iter Animi: dos círculos que se cruzan (el yo y el otro de la psicología social). */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className="brand-mark">
      <circle cx="9" cy="12" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="15" cy="12" r="6.5" fill="none" stroke="currentColor" className="brand-mark-accent" strokeWidth="1.8" />
    </svg>
  )
}
