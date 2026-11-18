import type { EstadoCaso, EstadoParticipacion, EstadoSesion, MotivoCierre } from '../api/types'
import { ESTADO_CASO, ESTADO_SESION } from '../lib/labels'
import { Status, type Fill } from './Status'

const SESION_FILL: Record<EstadoSesion, Fill> = { SIN_INICIAR: 'empty', EN_CURSO: 'half', FINALIZADO: 'full' }

export function SessionStatus({ estado }: { estado: EstadoSesion }) {
  return <Status fill={SESION_FILL[estado]}>{ESTADO_SESION[estado]}</Status>
}

const CASO_FILL: Record<EstadoCaso, Fill> = { BORRADOR: 'empty', PUBLICADO: 'full', ARCHIVADO: 'full' }

export function CaseStatus({ estado }: { estado: EstadoCaso }) {
  return (
    <Status fill={CASO_FILL[estado]} tone={estado === 'ARCHIVADO' ? 'muted' : undefined}>
      {ESTADO_CASO[estado]}
    </Status>
  )
}

/** Estado de un intento tal como lo devuelve el servidor. */
export function AttemptStatus({ estado, motivo }: { estado: EstadoParticipacion; motivo?: MotivoCierre | null }) {
  if (estado === 'EN_PROGRESO') return <Status fill="half">En curso</Status>
  if (estado === 'FINALIZADA') return <Status fill="full">Completado</Status>
  const texto =
    motivo === 'TIEMPO_AGOTADO'
      ? 'Cerrado: tiempo agotado'
      : motivo === 'CONVOCATORIA_REVOCADA'
        ? 'Cerrado: convocatoria retirada'
        : motivo === 'SESION_FINALIZADA'
          ? 'Cerrado: la sesión terminó'
          : 'Cerrado'
  return <Status fill="full">{texto}</Status>
}
