// Personaje de la escena: silueta humana genérica, blanca, sin rostro.
// Está aislada en este componente para poder sustituirla por un sprite real más adelante:
// basta con devolver aquí un <img> (o un SVG distinto) con la misma clase `sim-character`.

export function SceneCharacter({ className = 'sim-character' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 240 340" role="img" aria-label="Silueta del personaje de la escena">
      <defs>
        <filter id="char-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="4" stdDeviation="5" floodColor="#5d7390" floodOpacity="0.28" />
        </filter>
      </defs>
      <g filter="url(#char-shadow)" fill="#ffffff" stroke="var(--scene-line)" strokeWidth="3" strokeLinejoin="round">
        {/* Torso y hombros */}
        <path d="M22 340 C22 268 48 226 96 212 L144 212 C192 226 218 268 218 340 Z" />
        {/* Cuello */}
        <path d="M104 214 L104 186 C104 180 136 180 136 186 L136 214 Z" strokeWidth="2.5" />
        {/* Cabeza */}
        <ellipse cx="120" cy="128" rx="50" ry="60" />
      </g>
    </svg>
  )
}
