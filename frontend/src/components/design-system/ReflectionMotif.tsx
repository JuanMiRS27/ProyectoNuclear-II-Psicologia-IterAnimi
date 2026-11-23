/** Motivo de identidad: dos perspectivas conectadas. SVG ligero, sin imágenes ni animación continua. */
export function ReflectionMotif({ className = '' }: { className?: string }) {
  return (
    <svg className={`reflection-motif ${className}`} viewBox="0 0 360 280" fill="none" aria-hidden="true" focusable="false">
      <circle className="motif-halo" cx="190" cy="140" r="112" />
      <circle className="motif-orbit" cx="190" cy="140" r="111" strokeDasharray="2 9" />
      <path className="motif-line" d="M32 206C92 206 74 72 155 72s52 136 131 136h48M48 92c75 0 58 116 128 116S232 72 310 72" />
      <rect className="motif-plane" x="104" y="66" width="116" height="148" rx="58" transform="rotate(-20 162 140)" />
      <rect className="motif-plane motif-plane-front" x="160" y="66" width="116" height="148" rx="58" transform="rotate(20 218 140)" />
      <circle className="motif-node" cx="102" cy="109" r="6" />
      <circle className="motif-node motif-node-accent" cx="281" cy="180" r="7" />
      <circle className="motif-node" cx="242" cy="44" r="4" />
      <path className="motif-line" d="M190 127v26m-13-13h26" />
    </svg>
  )
}
