import { useState, type FormEvent } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { SessionStatus } from '../../components/design-system/domain-status'
import { Notice, Page, PageHeader } from '../../components/design-system/layout'
import { ErrorState, InlineError, LoadingState } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog, Dialog } from '../../components/ui/Dialog'
import { TextAreaField, TextField } from '../../components/ui/Field'
import { LinkTabs } from '../../components/ui/Tabs'
import { useSessionDetail, useSessionLifecycle, useSessionSummary } from '../../hooks/use-academic'
import { formatDateTime, formatRange, localInputToIso, toLocalInput } from '../../lib/format'
import { canOpenNow } from '../../lib/session-rules'
import type { Sesion, SesionUpdate } from '../../types/api'
import { ConvocationsPanel } from './ConvocationsPanel'
import { ResultsPanel } from './ResultsPanel'
import { TrackingPanel } from './TrackingPanel'

type Tab = 'convocados' | 'resultados' | 'seguimiento'
const TABS: { id: Tab; label: string }[] = [
  { id: 'convocados', label: 'Convocados' },
  { id: 'resultados', label: 'Resultados' },
  { id: 'seguimiento', label: 'Seguimiento' },
]

/** Sesión del docente: estado y acciones válidas, con Convocados, Resultados y Seguimiento agrupados. */
export function SessionDetailView() {
  const { sessionId = '' } = useParams()
  const [params] = useSearchParams()
  const tab = (TABS.find((t) => t.id === params.get('tab'))?.id ?? 'convocados') as Tab
  const sesion = useSessionDetail(sessionId)
  const summary = useSessionSummary(sessionId)
  const life = useSessionLifecycle(sessionId)
  const [editing, setEditing] = useState(false)
  const [confirmFinish, setConfirmFinish] = useState(false)
  const [now] = useState(() => Date.now())

  if (sesion.isPending)
    return (
      <Page>
        <LoadingState label="Cargando sesión…" />
      </Page>
    )
  if (sesion.isError)
    return (
      <Page>
        <ErrorState error={sesion.error} onRetry={() => sesion.refetch()} />
      </Page>
    )

  const s = sesion.data
  const info = summary.data?.sesion
  const openable = canOpenNow(s, now)

  return (
    <Page>
      <PageHeader
        crumbs={[
          { label: 'Sesiones', to: '/docente/sesiones' },
          ...(info ? [{ label: `${info.espacio_academico.nombre} (${info.espacio_academico.periodo})`, to: `/docente/aulas/${info.espacio_academico.id}` }] : []),
        ]}
        title={info?.caso.nombre ?? 'Sesión'}
        meta={
          <>
            <SessionStatus estado={s.estado} />
            <span>{formatRange(s.inicio, s.fin)}</span>
            <span>{s.tiempo_max_min} min por intento</span>
            {s.lugar && <span>{s.lugar}</span>}
          </>
        }
        actions={
          <>
            {s.estado !== 'FINALIZADO' && (
              <Button icon="edit" onClick={() => setEditing(true)}>
                {s.estado === 'SIN_INICIAR' ? 'Editar programación' : 'Editar lugar y mensaje'}
              </Button>
            )}
            {s.estado === 'SIN_INICIAR' && (
              <Button
                variant="primary"
                icon="play"
                onClick={() => life.start.mutate()}
                disabled={!openable}
                pending={life.start.isPending}
                pendingLabel="Abriendo…"
                aria-describedby={!openable ? 'open-hint' : undefined}
              >
                Abrir sesión
              </Button>
            )}
            {s.estado === 'EN_CURSO' && (
              <Button variant="danger" icon="flag" onClick={() => setConfirmFinish(true)}>
                Finalizar sesión
              </Button>
            )}
          </>
        }
      />

      {s.estado === 'SIN_INICIAR' && !openable && (
        <p id="open-hint" className="small muted">
          {new Date(s.inicio).getTime() > now
            ? `Podrás abrirla a partir del ${formatDateTime(s.inicio)}.`
            : 'La ventana programada ya terminó; el cierre automático la finalizará.'}
        </p>
      )}
      <InlineError error={life.start.error} />
      {s.estado === 'EN_CURSO' &&
        (new Date(s.limite_ingreso).getTime() >= now ? (
          <Notice tone="info">
            Los estudiantes pueden ingresar con su código hasta el <strong className="inline">{formatDateTime(s.limite_ingreso)}</strong>; quien ya
            empezó puede terminar su intento dentro de su tiempo.
          </Notice>
        ) : (
          <Notice tone="warn">
            El plazo de ingreso terminó el {formatDateTime(s.limite_ingreso)}: ya nadie puede empezar un intento. Finaliza la sesión para cerrar los
            intentos y evaluar; si no lo haces, el cierre automático la finalizará 24 horas después de su fin.
          </Notice>
        )
      )}
      {s.mensaje && (
        <p className="small">
          <span className="muted">Mensaje para los estudiantes: </span>
          {s.mensaje}
        </p>
      )}

      <LinkTabs label="Secciones de la sesión" tabs={TABS} current={tab} />
      {tab === 'convocados' && <ConvocationsPanel sesion={s} />}
      {tab === 'resultados' && <ResultsPanel sesion={s} />}
      {tab === 'seguimiento' && <TrackingPanel sesion={s} />}

      {editing && <EditSessionDialog s={s} onClose={() => setEditing(false)} save={life.update} />}
      <ConfirmDialog
        open={confirmFinish}
        title="¿Finalizar la sesión?"
        confirmLabel="Finalizar sesión"
        danger
        pending={life.finish.isPending}
        error={<InlineError error={life.finish.error} />}
        onConfirm={() => life.finish.mutate(undefined, { onSuccess: () => setConfirmFinish(false) })}
        onClose={() => setConfirmFinish(false)}
      >
        <p>Nadie podrá ingresar ni seguir respondiendo. Los intentos que estén en curso se cerrarán con las respuestas que tengan guardadas.</p>
        <p>No se puede deshacer. Después podrás evaluar y los estudiantes podrán consultar sus resultados.</p>
      </ConfirmDialog>
    </Page>
  )
}

function EditSessionDialog({
  s,
  onClose,
  save,
}: {
  s: Sesion
  onClose: () => void
  save: ReturnType<typeof useSessionLifecycle>['update']
}) {
  const full = s.estado === 'SIN_INICIAR'
  const [inicio, setInicio] = useState(() => toLocalInput(new Date(s.inicio)))
  const [fin, setFin] = useState(() => toLocalInput(new Date(s.fin)))
  const [tiempo, setTiempo] = useState(String(s.tiempo_max_min))
  const [lugar, setLugar] = useState(s.lugar ?? '')
  const [mensaje, setMensaje] = useState(s.mensaje ?? '')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const data: SesionUpdate = { lugar: lugar.trim() || null, mensaje: mensaje.trim() || null }
    if (full) {
      data.inicio = localInputToIso(inicio) ?? undefined
      data.fin = localInputToIso(fin) ?? undefined
      data.tiempo_max_min = Number(tiempo)
    }
    save.mutate(data, { onSuccess: onClose })
  }
  return (
    <Dialog open title={full ? 'Editar programación' : 'Editar lugar y mensaje'} onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        {!full && <p className="small muted">Con la sesión en curso solo se pueden cambiar el lugar y el mensaje.</p>}
        {full && (
          <div className="form-grid two">
            <TextField label="Inicio" type="datetime-local" value={inicio} onChange={(e) => setInicio(e.target.value)} required />
            <TextField label="Finalización" type="datetime-local" value={fin} onChange={(e) => setFin(e.target.value)} required />
            <TextField label="Tiempo máximo (min)" type="number" min={1} max={240} value={tiempo} onChange={(e) => setTiempo(e.target.value)} required />
          </div>
        )}
        <TextField label="Lugar o modalidad" maxLength={150} value={lugar} onChange={(e) => setLugar(e.target.value)} />
        <TextAreaField label="Mensaje para los estudiantes" maxLength={5000} value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
        <InlineError error={save.error} />
        <div className="dialog-actions">
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="primary" pending={save.isPending} pendingLabel="Guardando…">
            Guardar cambios
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
