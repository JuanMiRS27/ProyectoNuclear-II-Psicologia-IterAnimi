import { useState, type FormEvent, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import { Notice } from '../../components/design-system/layout'
import { EmptyState, InlineError, LoadingState, QueryBoundary } from '../../components/design-system/states'
import { Status } from '../../components/design-system/Status'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog, Dialog } from '../../components/ui/Dialog'
import { TextAreaField, TextField } from '../../components/ui/Field'
import { useConvocationCode, useConvocationMutations, useConvocations, useStudentsReport } from '../../hooks/use-academic'
import { EMAIL_RE, parseEmails } from '../../lib/format'
import { CONDICION_CONVOCADO } from '../../lib/labels'
import type { Convocatoria, Sesion } from '../../types/api'

type Action = { kind: 'code' | 'regenerate' | 'attempts' | 'revoke'; conv: Convocatoria } | null

const pretty = (code: string) => code.replace(/(.{4})(?=.)/g, '$1-')

function CodeDialog({ sesionId, conv, onClose }: { sesionId: string; conv: Convocatoria; onClose: () => void }) {
  const q = useConvocationCode(sesionId, conv.id)
  const [copied, setCopied] = useState(false)
  const code = q.data?.codigo_autorizacion
  return (
    <Dialog open title={`Código de ${conv.estudiante.nombre_completo}`} onClose={onClose}>
      <p className="small muted">
        Entrégalo solo a {conv.estudiante.correo}. Con este código y su correo, el estudiante entra a la sesión y, cuando termine, a sus resultados.
      </p>
      {q.isPending && <LoadingState label="Consultando código…" />}
      <InlineError error={q.error} />
      {code && (
        <>
          <div className="code-display" aria-label={`Código ${code.split('').join(' ')}`}>
            {pretty(code)}
          </div>
          <div className="dialog-actions">
            <Button
              icon="copy"
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
            </Button>
            <Button variant="primary" onClick={onClose}>
              Listo
            </Button>
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
  result?: ReactNode
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
            <TextField label="Intentos autorizados en total" type="number" min={(minNumber ?? 0) + 1} max={100} value={numero} onChange={(e) => setNumero(e.target.value)} />
          )}
          <TextAreaField label="Motivo" maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)} error={err} hint="Queda registrado como justificación." />
          <InlineError error={error} />
          <div className="dialog-actions">
            <Button onClick={onClose}>Cancelar</Button>
            <Button type="submit" variant="primary" pending={pending} pendingLabel="Guardando…">
              {confirmLabel}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}

/** Convocados: alta por correo y gestión de cada convocatoria (código, intentos, retiro) mientras no esté finalizada. */
export function ConvocationsPanel({ sesion }: { sesion: Sesion }) {
  const [params] = useSearchParams()
  const editable = sesion.estado !== 'FINALIZADO'
  const convs = useConvocations(sesion.id)
  const report = useStudentsReport(sesion.id)
  const m = useConvocationMutations(sesion.id)
  const [action, setAction] = useState<Action>(null)
  const [newCode, setNewCode] = useState<string | null>(null)
  const [correos, setCorreos] = useState('')
  const [addErr, setAddErr] = useState<string | null>(null)

  const close = () => {
    setAction(null)
    setNewCode(null)
    m.regenerate.reset()
    m.attempts.reset()
    m.revoke.reset()
  }

  const onAdd = (e: FormEvent) => {
    e.preventDefault()
    const emails = parseEmails(correos)
    if (!emails.length) return setAddErr('Escribe al menos un correo.')
    const malos = emails.filter((x) => !EMAIL_RE.test(x))
    if (malos.length) return setAddErr(`Revisa estos correos: ${malos.join(', ')}`)
    setAddErr(null)
    m.convoke.mutate(emails, { onSuccess: () => setCorreos('') })
  }

  const porConv = new Map((report.data?.items ?? []).map((r) => [r.convocatoria_id, r]))

  return (
    <div className="section">
      {params.get('nueva') && (
        <Notice tone="ok" title="Sesión creada.">
          Cada estudiante necesita su código para entrar. Si el envío por correo no está activo en el servidor, usa «Ver código» para entregárselo.
        </Notice>
      )}

      {editable && (
        <form className="panel form-grid inline-form" onSubmit={onAdd} noValidate>
          <TextAreaField
            label="Convocar estudiantes"
            value={correos}
            onChange={(e) => setCorreos(e.target.value)}
            placeholder="Correos institucionales separados por comas o saltos de línea"
            error={addErr}
            rows={2}
          />
          <InlineError error={m.convoke.error} />
          <div>
            <Button type="submit" icon="plus" pending={m.convoke.isPending} pendingLabel="Convocando…">
              Convocar
            </Button>
          </div>
        </form>
      )}

      <QueryBoundary query={convs} loading="Cargando convocados…">
        {(list) => {
          const sorted = [...list].sort((a, b) => Number(b.activa) - Number(a.activa) || a.estudiante.nombre_completo.localeCompare(b.estudiante.nombre_completo))
          if (sorted.length === 0)
            return <EmptyState icon="users" title="Nadie convocado todavía">Convoca estudiantes por su correo institucional para que puedan resolver el caso.</EmptyState>
          return (
            <ul className="rows" aria-label="Estudiantes convocados">
              {sorted.map((c) => {
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
                          <Button size="sm" icon="eye" onClick={() => setAction({ kind: 'code', conv: c })}>
                            Ver código
                          </Button>
                          <Button size="sm" variant="quiet" onClick={() => setAction({ kind: 'attempts', conv: c })}>
                            Más intentos
                          </Button>
                          <Button size="sm" variant="quiet" icon="refresh" onClick={() => setAction({ kind: 'regenerate', conv: c })}>
                            Regenerar código
                          </Button>
                          <Button size="sm" variant="danger" onClick={() => setAction({ kind: 'revoke', conv: c })}>
                            Retirar
                          </Button>
                        </div>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
          )
        }}
      </QueryBoundary>

      {action?.kind === 'code' && <CodeDialog sesionId={sesion.id} conv={action.conv} onClose={close} />}
      {action?.kind === 'regenerate' && (
        <ReasonDialog
          title="Regenerar código"
          intro={`El código actual de ${action.conv.estudiante.nombre_completo} deja de funcionar de inmediato, también si ya entró con él.`}
          confirmLabel="Regenerar"
          pending={m.regenerate.isPending}
          error={m.regenerate.error}
          onClose={close}
          onSubmit={(motivo) => m.regenerate.mutate({ cid: action.conv.id, motivo }, { onSuccess: (r) => setNewCode(r.codigo_autorizacion) })}
          result={
            newCode ? (
              <>
                <p className="small muted">Nuevo código para {action.conv.estudiante.correo}:</p>
                <div className="code-display">{pretty(newCode)}</div>
                <div className="dialog-actions">
                  <Button variant="primary" onClick={close}>
                    Listo
                  </Button>
                </div>
              </>
            ) : undefined
          }
        />
      )}
      {action?.kind === 'attempts' && (
        <ReasonDialog
          title="Autorizar más intentos"
          intro={`Ahora tiene ${action.conv.intentos_autorizados} ${action.conv.intentos_autorizados === 1 ? 'intento autorizado' : 'intentos autorizados'}. Solo se puede aumentar.`}
          withNumber
          minNumber={action.conv.intentos_autorizados}
          confirmLabel="Guardar"
          pending={m.attempts.isPending}
          error={m.attempts.error}
          onClose={close}
          onSubmit={(motivo, n) => m.attempts.mutate({ cid: action.conv.id, n, motivo }, { onSuccess: close })}
        />
      )}
      <ConfirmDialog
        open={action?.kind === 'revoke'}
        title="¿Retirar de la sesión?"
        confirmLabel="Retirar"
        danger
        pending={m.revoke.isPending}
        error={<InlineError error={m.revoke.error} />}
        onConfirm={() => action && m.revoke.mutate(action.conv.id, { onSuccess: close })}
        onClose={close}
      >
        <p>
          {action?.conv.estudiante.nombre_completo} pierde el acceso de inmediato. Si está resolviendo el caso, su intento se cierra con lo que haya
          guardado.
        </p>
        <p>Su historial se conserva y puedes volver a convocarle.</p>
      </ConfirmDialog>
    </div>
  )
}
