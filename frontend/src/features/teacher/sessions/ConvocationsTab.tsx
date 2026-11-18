import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { reportsApi, sessionsApi } from '../../../api/endpoints'
import type { Convocatoria, Sesion } from '../../../api/types'
import { ConfirmDialog, Dialog } from '../../../components/Dialog'
import { Status } from '../../../components/Status'
import { Empty, ErrorState, InlineError, Loading } from '../../../components/states'
import { EMAIL_RE, parseEmails } from '../../../lib/format'
import { CONDICION_CONVOCADO } from '../../../lib/labels'

type Action = { kind: 'code' | 'regenerate' | 'attempts' | 'revoke'; conv: Convocatoria } | null

function CodeDialog({ sesionId, conv, onClose }: { sesionId: string; conv: Convocatoria; onClose: () => void }) {
  const q = useQuery({
    queryKey: ['code', conv.id],
    queryFn: () => sessionsApi.code(sesionId, conv.id),
    gcTime: 0,
    staleTime: 0,
  })
  const [copied, setCopied] = useState(false)
  const code = q.data?.codigo_autorizacion
  return (
    <Dialog open title={`Código de ${conv.estudiante.nombre_completo}`} onClose={onClose}>
      <p className="small muted">
        Entrégalo solo a {conv.estudiante.correo}. Con este código y su correo, el estudiante ingresa a la sesión y, cuando termine, a sus
        resultados.
      </p>
      {q.isPending && <Loading label="Consultando código…" />}
      {q.isError && <InlineError error={q.error} />}
      {code && (
        <>
          <div className="code-display" aria-label={`Código ${code.split('').join(' ')}`}>
            {code.replace(/(.{4})(?=.)/g, '$1-')}
          </div>
          <div className="dialog-actions">
            <button
              type="button"
              className="btn"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(code)
                  setCopied(true)
                } catch {
                  setCopied(false)
                }
              }}
            >
              {copied ? 'Código copiado' : 'Copiar código'}
            </button>
            <button type="button" className="btn btn-primary" onClick={onClose}>
              Listo
            </button>
          </div>
        </>
      )}
    </Dialog>
  )
}

function ReasonDialog({
  title,
  intro,
  withNumber,
  minNumber,
  confirmLabel,
  onSubmit,
  onClose,
  pending,
  error,
  result,
}: {
  title: string
  intro: string
  withNumber?: boolean
  minNumber?: number
  confirmLabel: string
  onSubmit: (motivo: string, numero: number) => void
  onClose: () => void
  pending: boolean
  error: unknown
  result?: React.ReactNode
}) {
  const [motivo, setMotivo] = useState('')
  const [numero, setNumero] = useState(String((minNumber ?? 1) + 1))
  const [err, setErr] = useState<string | null>(null)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (motivo.trim().length < 5) return setErr('Describe el motivo (al menos 5 caracteres).')
    if (withNumber && !(Number(numero) > (minNumber ?? 0))) return setErr(`Debe ser mayor que ${minNumber}.`)
    setErr(null)
    onSubmit(motivo.trim(), Number(numero))
  }
  return (
    <Dialog open title={title} onClose={onClose}>
      {result ?? (
        <form className="form-grid" onSubmit={submit} noValidate>
          <p className="small muted">{intro}</p>
          {withNumber && (
            <div className="field">
              <label htmlFor="r-num">Intentos autorizados en total</label>
              <input id="r-num" type="number" min={(minNumber ?? 0) + 1} max={100} value={numero} onChange={(e) => setNumero(e.target.value)} />
            </div>
          )}
          <div className="field">
            <label htmlFor="r-motivo">Motivo</label>
            <textarea id="r-motivo" maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)} aria-invalid={err ? true : undefined} />
            <span className="hint">Queda registrado como justificación de la operación.</span>
          </div>
          {err && <p className="field-error">{err}</p>}
          <InlineError error={error} />
          <div className="dialog-actions">
            <button type="button" className="btn" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={pending}>
              {pending ? 'Guardando…' : confirmLabel}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  )
}

export function ConvocationsTab({ sesion }: { sesion: Sesion }) {
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const editable = sesion.estado !== 'FINALIZADO'
  const convs = useQuery({ queryKey: ['convocations', sesion.id], queryFn: () => sessionsApi.convocations(sesion.id, true) })
  const report = useQuery({ queryKey: ['students-report', sesion.id], queryFn: () => reportsApi.students(sesion.id) })
  const [action, setAction] = useState<Action>(null)
  const [newCode, setNewCode] = useState<string | null>(null)
  const [correos, setCorreos] = useState('')
  const [addErr, setAddErr] = useState<string | null>(null)

  const close = () => {
    setAction(null)
    setNewCode(null)
    regenerate.reset()
    attempts.reset()
    revoke.reset()
  }
  const refresh = () => qc.invalidateQueries()

  const add = useMutation({
    mutationFn: (emails: string[]) => sessionsApi.addConvocations(sesion.id, emails),
    onSuccess: () => {
      setCorreos('')
      refresh()
    },
  })
  const regenerate = useMutation({
    mutationFn: ({ cid, motivo }: { cid: string; motivo: string }) => sessionsApi.regenerateCode(sesion.id, cid, motivo),
    onSuccess: (r) => {
      setNewCode(r.codigo_autorizacion)
      refresh()
    },
  })
  const attempts = useMutation({
    mutationFn: ({ cid, n, motivo }: { cid: string; n: number; motivo: string }) => sessionsApi.setAttempts(sesion.id, cid, n, motivo),
    onSuccess: () => {
      refresh()
      close()
    },
  })
  const revoke = useMutation({
    mutationFn: (cid: string) => sessionsApi.revoke(sesion.id, cid),
    onSuccess: () => {
      refresh()
      close()
    },
  })

  const onAdd = (e: FormEvent) => {
    e.preventDefault()
    const emails = parseEmails(correos)
    if (!emails.length) return setAddErr('Escribe al menos un correo.')
    const malos = emails.filter((m) => !EMAIL_RE.test(m))
    if (malos.length) return setAddErr(`Revisa estos correos: ${malos.join(', ')}`)
    setAddErr(null)
    add.mutate(emails)
  }

  if (convs.isPending) return <Loading label="Cargando convocados…" />
  if (convs.isError) return <ErrorState error={convs.error} onRetry={() => convs.refetch()} />

  const porConv = new Map((report.data?.items ?? []).map((r) => [r.convocatoria_id, r]))
  const list = [...convs.data].sort((a, b) => Number(b.activa) - Number(a.activa) || a.estudiante.nombre_completo.localeCompare(b.estudiante.nombre_completo))

  return (
    <div className="section">
      {params.get('nueva') && (
        <div className="notice notice-ok" role="status">
          <div>
            <strong>Sesión creada.</strong>
            Cada estudiante necesita su código para ingresar. Si el envío por correo no está activo en el servidor, usa «Ver código» para
            entregárselo.
          </div>
        </div>
      )}

      {editable && (
        <form className="panel form-grid" onSubmit={onAdd} noValidate>
          <div className="field">
            <label htmlFor="add-correos">Convocar estudiantes</label>
            <textarea
              id="add-correos"
              style={{ minHeight: '4.5rem' }}
              value={correos}
              onChange={(e) => setCorreos(e.target.value)}
              placeholder="Correos institucionales separados por comas o saltos de línea"
              aria-invalid={addErr ? true : undefined}
            />
            {addErr && <span className="field-error">{addErr}</span>}
          </div>
          <InlineError error={add.error} />
          <div>
            <button type="submit" className="btn" disabled={add.isPending}>
              {add.isPending ? 'Convocando…' : 'Convocar'}
            </button>
          </div>
        </form>
      )}

      {list.length === 0 ? (
        <Empty title="Nadie convocado todavía">Convoca estudiantes por su correo institucional para que puedan resolver el caso.</Empty>
      ) : (
        <ul className="rows" aria-label="Estudiantes convocados">
          {list.map((c) => {
            const r = porConv.get(c.id)
            const cond = r?.condicion ?? (c.activa ? null : 'REVOCADA')
            return (
              <li key={c.id}>
                <div className="row">
                  <div>
                    <div className="row-title">{c.estudiante.nombre_completo}</div>
                    <div className="row-meta">
                      <span>{c.estudiante.correo}</span>
                      {cond && (
                        <Status
                          fill={cond === 'PARTICIPO' ? (r?.intento_activo ? 'half' : 'full') : cond === 'REVOCADA' ? 'alert' : 'empty'}
                          tone={cond === 'REVOCADA' || cond === 'AUSENTE' ? 'muted' : undefined}
                        >
                          {r?.intento_activo ? 'Resolviendo ahora' : CONDICION_CONVOCADO[cond]}
                        </Status>
                      )}
                      <span>
                        {r ? `${r.intentos_utilizados} de ${c.intentos_autorizados}` : `${c.intentos_autorizados}`}{' '}
                        {c.intentos_autorizados === 1 ? 'intento' : 'intentos'}
                      </span>
                    </div>
                  </div>
                  {editable && c.activa && (
                    <div className="row-side">
                      <button type="button" className="btn btn-sm" onClick={() => setAction({ kind: 'code', conv: c })}>
                        Ver código
                      </button>
                      <button type="button" className="btn btn-sm btn-quiet" onClick={() => setAction({ kind: 'attempts', conv: c })}>
                        Más intentos
                      </button>
                      <button type="button" className="btn btn-sm btn-quiet" onClick={() => setAction({ kind: 'regenerate', conv: c })}>
                        Regenerar código
                      </button>
                      <button type="button" className="btn btn-sm btn-danger" onClick={() => setAction({ kind: 'revoke', conv: c })}>
                        Retirar
                      </button>
                    </div>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {action?.kind === 'code' && <CodeDialog sesionId={sesion.id} conv={action.conv} onClose={close} />}
      {action?.kind === 'regenerate' && (
        <ReasonDialog
          title="Regenerar código"
          intro={`El código actual de ${action.conv.estudiante.nombre_completo} dejará de funcionar de inmediato, también si ya ingresó con él.`}
          confirmLabel="Regenerar"
          pending={regenerate.isPending}
          error={regenerate.error}
          onClose={close}
          onSubmit={(motivo) => regenerate.mutate({ cid: action.conv.id, motivo })}
          result={
            newCode ? (
              <>
                <p className="small muted">Nuevo código para {action.conv.estudiante.correo}:</p>
                <div className="code-display">{newCode.replace(/(.{4})(?=.)/g, '$1-')}</div>
                <div className="dialog-actions">
                  <button type="button" className="btn btn-primary" onClick={close}>
                    Listo
                  </button>
                </div>
              </>
            ) : undefined
          }
        />
      )}
      {action?.kind === 'attempts' && (
        <ReasonDialog
          title="Autorizar más intentos"
          intro={`Actualmente ${action.conv.estudiante.nombre_completo} tiene ${action.conv.intentos_autorizados} ${action.conv.intentos_autorizados === 1 ? 'intento autorizado' : 'intentos autorizados'}. Solo se puede aumentar.`}
          withNumber
          minNumber={action.conv.intentos_autorizados}
          confirmLabel="Guardar"
          pending={attempts.isPending}
          error={attempts.error}
          onClose={close}
          onSubmit={(motivo, n) => attempts.mutate({ cid: action.conv.id, n, motivo })}
        />
      )}
      <ConfirmDialog
        open={action?.kind === 'revoke'}
        title="¿Retirar de la sesión?"
        confirmLabel="Retirar"
        danger
        pending={revoke.isPending}
        error={<InlineError error={revoke.error} />}
        onConfirm={() => action && revoke.mutate(action.conv.id)}
        onClose={close}
      >
        <p>
          {action?.conv.estudiante.nombre_completo} perderá el acceso de inmediato. Si está resolviendo el caso, su intento se cerrará con lo
          que haya guardado.
        </p>
        <p>Su historial se conserva. Puedes volver a convocarle más adelante.</p>
      </ConfirmDialog>
    </div>
  )
}
