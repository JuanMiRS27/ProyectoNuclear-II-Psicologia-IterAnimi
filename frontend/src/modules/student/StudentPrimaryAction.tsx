import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Notice } from '../../components/design-system/layout'
import { InlineError } from '../../components/design-system/states'
import { Button, ButtonLink } from '../../components/ui/Button'
import { ConfirmDialog } from '../../components/ui/Dialog'
import { useStartAttempt } from '../../hooks/use-student'
import { formatDateTime, plural } from '../../lib/format'
import type { StudentSessionView } from '../../lib/student-session-adapters'

/** La próxima acción útil del estudiante según el estado que devuelve el servidor. */
export function StudentPrimaryAction({ view, from }: { view: StudentSessionView; from: string }) {
  const navigate = useNavigate()
  const start = useStartAttempt()
  const [confirm, setConfirm] = useState(false)
  const restantes = Math.max(0, (view.intentosAutorizados ?? 0) - view.intentosUsados)

  switch (view.status) {
    case 'en_curso':
      return (
        <div className="action-block">
          <ButtonLink to={`/estudiante/caso/${view.intentoEnCurso!.id}`} state={{ from }} variant="primary" icon="play">
            Continuar caso
          </ButtonLink>
          <p className="small muted">
            Tu tiempo sigue corriendo hasta el {formatDateTime(view.intentoEnCurso!.fecha_limite)}; llevas{' '}
            {view.intentoEnCurso!.progreso.respondidas} de {view.intentoEnCurso!.progreso.total_preguntas} decisiones.
          </p>
        </div>
      )
    case 'disponible':
      return (
        <div className="action-block">
          <Button variant="primary" icon="play" onClick={() => setConfirm(true)}>
            {view.intentosUsados ? 'Iniciar otro intento' : 'Iniciar caso'}
          </Button>
          <p className="small muted">
            Tendrás {view.tiempoMaxMin} minutos desde que inicies; {plural(restantes, 'intento disponible', 'intentos disponibles')}.
          </p>
          <InlineError error={start.error} />
          <ConfirmDialog
            open={confirm}
            title="¿Iniciar el caso ahora?"
            confirmLabel="Iniciar"
            pending={start.isPending}
            error={<InlineError error={start.error} />}
            onConfirm={() =>
              start.mutate(undefined, { onSuccess: (p) => navigate(`/estudiante/caso/${p.id}`, { state: { from } }) })
            }
            onClose={() => setConfirm(false)}
          >
            <p>
              Al iniciar empieza a correr tu tiempo de {view.tiempoMaxMin} minutos y se usa uno de tus intentos. El tiempo no se detiene si
              cierras la página, pero podrás retomar el caso donde lo dejaste.
            </p>
          </ConfirmDialog>
        </div>
      )
    case 'completado':
      return (
        <Notice tone="info" title="Ya resolviste este caso.">
          Los resultados estarán disponibles cuando tu docente finalice la sesión. Entonces vuelve a ingresar con tu correo y el mismo código.
        </Notice>
      )
    case 'plazo_cerrado':
      return (
        <Notice tone="warn" title="Ya no es posible iniciar el caso.">
          El plazo de ingreso terminó{view.limiteIngreso ? ` el ${formatDateTime(view.limiteIngreso)}` : ''}; si crees que es un error,
          comunícate con tu docente.
        </Notice>
      )
    case 'finalizada':
      return (
        <ButtonLink to="/estudiante/resultados" variant="primary" icon="chart">
          Ver mis resultados
        </ButtonLink>
      )
  }
}
