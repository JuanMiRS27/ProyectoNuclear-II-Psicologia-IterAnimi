import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { reportsApi, sessionsApi } from '../../../api/endpoints'
import type { Sesion, SesionUpdate } from '../../../api/types'
import { ConfirmDialog, Dialog } from '../../../components/Dialog'
import { SessionStatus } from '../../../components/domainStatus'
import { ErrorState, InlineError, Loading } from '../../../components/states'
import { formatDateTime, formatRange, localInputToIso, toLocalInput } from '../../../lib/format'
import { canOpenNow } from '../../../lib/sessionRules'
import { ConvocationsTab } from './ConvocationsTab'
import { ResultsTab } from './ResultsTab'
import { TrackingTab } from './TrackingTab'

type Tab = 'convocados' | 'resultados' | 'seguimiento'
const TABS: { id: Tab; label: string }[] = [
  { id: 'convocados', label: 'Convocados' },
  { id: 'resultados', label: 'Resultados' },
  { id: 'seguimiento', label: 'Seguimiento' },
]

function EditDialog({ s, open, onClose }: { s: Sesion; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const full = s.estado === 'SIN_INICIAR'
  const [inicio, setInicio] = useState(() => toLocalInput(new Date(s.inicio)))
  const [fin, setFin] = useState(() => toLocalInput(new Date(s.fin)))
  const [tiempo, setTiempo] = useState(String(s.tiempo_max_min))
  const [lugar, setLugar] = useState(s.lugar ?? '')
  const [mensaje, setMensaje] = useState(s.mensaje ?? '')
  const m = useMutation({
    mutationFn: (data: SesionUpdate) => sessionsApi.update(s.id, data),
    onSuccess: () => {
      qc.invalidateQueries()
      onClose()
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const data: SesionUpdate = { lugar: lugar.trim() || null, mensaje: mensaje.trim() || null }
    if (full) {
      data.inicio = localInputToIso(inicio) ?? undefined
      data.fin = localInputToIso(fin) ?? undefined
      data.tiempo_max_min = Number(tiempo)
    }
    m.mutate(data)
  }
  return (
    <Dialog open={open} title={full ? 'Editar programación' : 'Editar lugar y mensaje'} onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        {!full && <p className="small muted">Con la sesión en curso solo se pueden cambiar el lugar y el mensaje.</p>}
        {full && (
          <div className="form-grid two">
            <div className="field">
              <label htmlFor="e-inicio">Inicio</label>
              <input id="e-inicio" type="datetime-local" value={inicio} onChange={(e) => setInicio(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="e-fin">Finalización</label>
              <input id="e-fin" type="datetime-local" value={fin} onChange={(e) => setFin(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="e-tiempo">Tiempo máximo (min)</label>
              <input id="e-tiempo" type="number" min={1} max={240} value={tiempo} onChange={(e) => setTiempo(e.target.value)} required />
            </div>
          </div>
        )}
        <div className="field">
          <label htmlFor="e-lugar">Lugar o modalidad</label>
          <input id="e-lugar" maxLength={150} value={lugar} onChange={(e) => setLugar(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="e-mensaje">Mensaje para los estudiantes</label>
          <textarea id="e-mensaje" maxLength={5000} value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
        </div>
        <InlineError error={m.error} />
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={m.isPending}>
            {m.isPending ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

export function SessionDetailPage() {
  const { sessionId = '' } = useParams()
  const [params] = useSearchParams()
  const tab: Tab = (TABS.find((t) => t.id === params.get('tab'))?.id ?? 'convocados') as Tab
  const qc = useQueryClient()
  const sesion = useQuery({ queryKey: ['session', sessionId], queryFn: () => sessionsApi.get(sessionId) })
  const summary = useQuery({ queryKey: ['session-summary', sessionId], queryFn: () => reportsApi.summary(sessionId) })
  const [editing, setEditing] = useState(false)
  const [confirmFinish, setConfirmFinish] = useState(false)
  const [now] = useState(() => Date.now())

  const start = useMutation({ mutationFn: () => sessionsApi.start(sessionId), onSuccess: () => qc.invalidateQueries() })
  const finish = useMutation({
    mutationFn: () => sessionsApi.finish(sessionId),
    onSuccess: () => {
      setConfirmFinish(false)
      qc.invalidateQueries()
    },
  })

  if (sesion.isPending) return <main className="page" id="contenido"><Loading /></main>
  if (sesion.isError)
    return (
      <main className="page" id="contenido">
        <ErrorState error={sesion.error} onRetry={() => sesion.refetch()} />
      </main>
    )

  const s = sesion.data
  const info = summary.data?.sesion
  const openable = canOpenNow(s, now)

  return (
    <main className="page" id="contenido">
      <div className="page-head">
        <div>
          {info && (
            <div className="crumbs">
              <Link to={`/aulas/${info.espacio_academico.id}`}>
                {info.espacio_academico.nombre} ({info.espacio_academico.periodo})
              </Link>
            </div>
          )}
          <h1>{info?.caso.nombre ?? 'Sesión'}</h1>
          <div className="row-meta" style={{ marginTop: '0.5rem' }}>
            <SessionStatus estado={s.estado} />
            <span>{formatRange(s.inicio, s.fin)}</span>
            <span>{s.tiempo_max_min} min por intento</span>
            {s.lugar && <span>{s.lugar}</span>}
          </div>
        </div>
        <div className="btn-row">
          {s.estado !== 'FINALIZADO' && (
            <button type="button" className="btn" onClick={() => setEditing(true)}>
              {s.estado === 'SIN_INICIAR' ? 'Editar programación' : 'Editar lugar y mensaje'}
            </button>
          )}
          {s.estado === 'SIN_INICIAR' && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => start.mutate()}
              disabled={!openable || start.isPending}
              aria-describedby={!openable ? 'open-hint' : undefined}
            >
              {start.isPending ? 'Abriendo…' : 'Abrir sesión'}
            </button>
          )}
          {s.estado === 'EN_CURSO' && (
            <button type="button" className="btn btn-danger" onClick={() => setConfirmFinish(true)}>
              Finalizar sesión
            </button>
          )}
        </div>
      </div>

      {s.estado === 'SIN_INICIAR' && !openable && (
        <p id="open-hint" className="small muted" style={{ marginTop: '-1rem' }}>
          {new Date(s.inicio).getTime() > now
            ? `Podrás abrirla a partir del ${formatDateTime(s.inicio)}.`
            : 'La ventana programada ya terminó; el cierre automático la finalizará.'}
        </p>
      )}
      <InlineError error={start.error} />

      {s.estado === 'EN_CURSO' && (
        <div className="notice notice-info">
          <div>
            Los estudiantes pueden ingresar con su código hasta el <strong style={{ display: 'inline' }}>{formatDateTime(s.limite_ingreso)}</strong>;
            quien ya empezó puede terminar su intento dentro de su tiempo.
          </div>
        </div>
      )}
      {s.mensaje && (
        <p className="small">
          <span className="muted">Mensaje para los estudiantes: </span>
          {s.mensaje}
        </p>
      )}

      <nav className="tabs" aria-label="Secciones de la sesión">
        {TABS.map((t) => (
          <Link key={t.id} to={`?tab=${t.id}`} replace aria-current={tab === t.id ? 'page' : undefined}>
            {t.label}
          </Link>
        ))}
      </nav>

      {tab === 'convocados' && <ConvocationsTab sesion={s} />}
      {tab === 'resultados' && <ResultsTab sesion={s} />}
      {tab === 'seguimiento' && <TrackingTab sesion={s} />}

      {editing && <EditDialog s={s} open={editing} onClose={() => setEditing(false)} />}
      <ConfirmDialog
        open={confirmFinish}
        title="¿Finalizar la sesión?"
        confirmLabel="Finalizar sesión"
        danger
        pending={finish.isPending}
        error={<InlineError error={finish.error} />}
        onConfirm={() => finish.mutate()}
        onClose={() => setConfirmFinish(false)}
      >
        <p>Nadie podrá ingresar ni seguir respondiendo. Los intentos que estén en curso se cerrarán con las respuestas que tengan guardadas.</p>
        <p>Esta acción no se puede deshacer. Después podrás evaluar los intentos y los estudiantes podrán consultar sus resultados.</p>
      </ConfirmDialog>
    </main>
  )
}
