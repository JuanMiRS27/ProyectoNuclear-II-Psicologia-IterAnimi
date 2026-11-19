// Personaje de la escena: monigote blanco sin rostro, con contorno azul grisáceo y una sombra en el suelo.
// Aislado en este componente para sustituirlo por un sprite real: basta con devolver otra imagen
// con la misma clase. No usa imágenes externas ni avatares de personas reales.

export function SceneCharacter({ className = 'sim-character', decorative = false }: { className?: string; decorative?: boolean }) {
  return (
    <svg
      className={className}
      viewBox="0 0 240 360"
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : 'Personaje de la escena'}
    >
      {/* Sombra en el suelo: integra la figura en la escena */}
      <ellipse cx="120" cy="350" rx="92" ry="9" fill="#5d7390" opacity="0.18" />
      <g fill="#ffffff" stroke="var(--scene-line, #7f93ab)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round">
        {/* Cuerpo */}
        <path d="M36 348 C36 280 62 236 104 224 L136 224 C178 236 204 280 204 348 Z" />
        {/* Brazos insinuados */}
        <path d="M70 262 C64 292 62 318 64 344" fill="none" opacity="0.55" />
        <path d="M170 262 C176 292 178 318 176 344" fill="none" opacity="0.55" />
        {/* Cuello */}
        <path d="M106 226 L106 198 C106 192 134 192 134 198 L134 226 Z" strokeWidth="2.5" />
        {/* Cabeza sin rostro */}
        <ellipse cx="120" cy="140" rx="50" ry="60" />
      </g>
    </svg>
  )
}
