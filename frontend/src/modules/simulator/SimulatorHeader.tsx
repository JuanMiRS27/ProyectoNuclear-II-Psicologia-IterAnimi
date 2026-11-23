import { Link } from 'react-router'
import { Icon } from '../../components/ui/Icon'
import { formatCountdown } from '../../lib/format'
import type { Progreso } from '../../types/api'

/** Barra superior: salida, título del caso, decisiones respondidas y tiempo (todo según el servidor). */
export function SimulatorHeader({ title, progress, secondsLeft, exitTo, exitLabel }: { title: string; progress: Progreso; secondsLeft: number; exitTo: string; exitLabel: string }) {
  const low = secondsLeft <= 300
  const pct = progress.total_preguntas ? Math.floor((progress.respondidas / progress.total_preguntas) * 100) : 0
  return (
    <header className="sim-top">
      <div className="sim-top-inner">
        <Link className="sim-back" to={exitTo}>
          <Icon name="chevronLeft" size={16} />
          {exitLabel}
        </Link>
        <p className="sim-title">{title}</p>
        <div className="sim-meta">
          <span>
            Respondidas <strong>{progress.respondidas}</strong> de {progress.total_preguntas}
          </span>
          <span className={low ? 'sim-time-low' : undefined} role="timer" aria-live={low ? 'polite' : 'off'}>
            <Icon name="clock" size={15} /> <strong>{formatCountdown(secondsLeft)}</strong>
          </span>
        </div>
      </div>
      <div
        className="sim-progress"
        role="progressbar"
        aria-label="Decisiones respondidas"
        aria-valuemin={0}
        aria-valuemax={progress.total_preguntas}
        aria-valuenow={progress.respondidas}
      >
        <span style={{ width: `${pct}%` }} />
      </div>
    </header>
  )
}
