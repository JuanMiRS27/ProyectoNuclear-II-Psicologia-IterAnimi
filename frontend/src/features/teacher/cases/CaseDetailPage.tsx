import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { ApiError } from '../../../api/client'
import { casesApi } from '../../../api/endpoints'
import type { CasoDetalle, ErrorValidacion } from '../../../api/types'
import { useAuth } from '../../../auth/useAuth'
import { ConfirmDialog, Dialog } from '../../../components/Dialog'
import { CaseStatus } from '../../../components/domainStatus'
import { ErrorState, InlineError, Loading } from '../../../components/states'
import { formatDecimal, optionLetter } from '../../../lib/format'

function Text({ value }: { value: string | null }) {
  if (!value) return <p className="muted">Sin contenido.</p>
  return (
    <div className="reading">
      {value
        .split(/\n+/)
        .filter((p) => p.trim())
        .map((p, i) => (
          <p key={i}>{p}</p>
        ))}
    </div>
  )
}

function ValidationList({ errores }: { errores: ErrorValidacion[] }) {
  return (
    <div className="notice notice-error" role="alert">
      <div>
        <strong>El caso todavía no se puede publicar ({errores.length}).</strong>
        <ul style={{ margin: '0.4rem 0 0', paddingLeft: '1.1rem' }}>
          {errores.map((e, i) => (
            <li key={i}>{e.mensaje}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function EditGeneral({ c, onClose }: { c: CasoDetalle; onClose: () => void }) {
  const qc = useQueryClient()
  const [nombre, setNombre] = useState(c.nombre)
  const [tiempo, setTiempo] = useState(c.tiempo_estimado_min ? String(c.tiempo_estimado_min) : '')
  const [desarrollo, setDesarrollo] = useState(c.desarrollo_situacional ?? '')
  const [historia, setHistoria] = useState(c.historia ?? '')
  const m = useMutation({
    mutationFn: () =>
      casesApi.update(c.id, {
        nombre: nombre.trim(),
        tiempo_estimado_min: tiempo ? Number(tiempo) : null,
        desarrollo_situacional: desarrollo.trim() || null,
        historia: historia.trim() || null,
      }),
    onSuccess: (data) => {
      qc.setQueryData(['case', c.id], data)
      qc.invalidateQueries({ queryKey: ['cases'] })
      onClose()
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    m.mutate()
  }
  return (
    <Dialog open title="Editar información general" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <div className="field">
          <label htmlFor="c-nombre">Nombre</label>
          <input id="c-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="c-tiempo">Tiempo estimado (minutos, 1 a 240)</label>
          <input id="c-tiempo" type="number" min={1} max={240} value={tiempo} onChange={(e) => setTiempo(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="c-desarrollo">Desarrollo situacional</label>
          <textarea id="c-desarrollo" value={desarrollo} onChange={(e) => setDesarrollo(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="c-historia">Historia</label>
          <textarea id="c-historia" value={historia} onChange={(e) => setHistoria(e.target.value)} />
        </div>
        <InlineError error={m.error} />
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={m.isPending}>
            {m.isPending ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

export function CaseDetailPage() {
  const { caseId = '' } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { session } = useAuth()
  const puedeEditar = session?.kind === 'staff' && session.user.puede_crear_casos
  const q = useQuery({ queryKey: ['case', caseId], queryFn: () => casesApi.get(caseId) })
  const [errores, setErrores] = useState<ErrorValidacion[] | null>(null)
  const [validOk, setValidOk] = useState(false)
  const [dialog, setDialog] = useState<'edit' | 'archive' | 'delete' | null>(null)

  const after = (data?: CasoDetalle) => {
    if (data) qc.setQueryData(['case', caseId], data)
    qc.invalidateQueries({ queryKey: ['cases'] })
  }
  const validate = useMutation({
    mutationFn: () => casesApi.validate(caseId),
    onSuccess: (r) => {
      setErrores(r.valido ? null : r.errores)
      setValidOk(r.valido)
    },
  })
  const publish = useMutation({
    mutationFn: () => casesApi.publish(caseId),
    onSuccess: (data) => {
      setErrores(null)
      setValidOk(false)
      after(data)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) {
        const body = err.body as { errores?: ErrorValidacion[] }
        if (body?.errores) setErrores(body.errores)
      }
    },
  })
  const archive = useMutation({
    mutationFn: () => casesApi.archive(caseId),
    onSuccess: (data) => {
      setDialog(null)
      after(data)
    },
  })
  const remove = useMutation({
    mutationFn: () => casesApi.remove(caseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cases'] })
      navigate('/casos', { replace: true })
    },
  })
  const exportDsl = useMutation({ mutationFn: () => casesApi.exportDsl(caseId) })

  if (q.isPending) return <main className="page" id="contenido"><Loading /></main>
  if (q.isError)
    return (
      <main className="page" id="contenido">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </main>
    )
  const c = q.data
  const borrador = c.estado === 'BORRADOR'
  const criterios = new Map((c.rubrica?.criterios ?? []).map((cr) => [cr.id, cr.descripcion]))
  const publishError = publish.error instanceof ApiError && publish.error.status === 422 && errores ? null : publish.error

  return (
    <main className="page" id="contenido" style={{ maxWidth: '60rem' }}>
      <div className="page-head">
        <div>
          <div className="crumbs">
            <Link to="/casos">Mis casos</Link>
          </div>
          <h1>{c.nombre}</h1>
          <div className="row-meta" style={{ marginTop: '0.5rem' }}>
            <CaseStatus estado={c.estado} />
            {c.tiempo_estimado_min && <span>{c.tiempo_estimado_min} min estimados</span>}
            <span>
              {c.escenarios.length} {c.escenarios.length === 1 ? 'escenario' : 'escenarios'},{' '}
              {c.escenarios.reduce((n, e) => n + e.preguntas.length, 0)} decisiones
            </span>
          </div>
        </div>
        <div className="btn-row">
          <button type="button" className="btn" onClick={() => exportDsl.mutate()} disabled={exportDsl.isPending}>
            Exportar CaseDSL
          </button>
          {borrador && puedeEditar && (
            <>
              <button type="button" className="btn" onClick={() => setDialog('edit')}>
                Editar información
              </button>
              <button type="button" className="btn" onClick={() => validate.mutate()} disabled={validate.isPending}>
                {validate.isPending ? 'Validando…' : 'Validar'}
              </button>
              <button type="button" className="btn btn-primary" onClick={() => publish.mutate()} disabled={publish.isPending}>
                {publish.isPending ? 'Publicando…' : 'Publicar'}
              </button>
            </>
          )}
          {c.estado === 'PUBLICADO' && puedeEditar && (
            <button type="button" className="btn btn-danger" onClick={() => setDialog('archive')}>
              Archivar
            </button>
          )}
        </div>
      </div>

      {params.get('importado') && borrador && (
        <div className="notice notice-ok" role="status">
          <div>
            <strong>Borrador creado.</strong> Revisa el contenido, valida y publícalo para poder asignarlo a un aula.
          </div>
        </div>
      )}
      {borrador && !puedeEditar && (
        <div className="notice notice-info">
          <div>Tu cuenta no tiene permiso para modificar casos. Puedes consultarlo y exportarlo.</div>
        </div>
      )}
      {validOk && (
        <div className="notice notice-ok" role="status">
          <div>El caso cumple todas las reglas y puede publicarse.</div>
        </div>
      )}
      {errores && errores.length > 0 && <ValidationList errores={errores} />}
      <InlineError error={validate.error} />
      <InlineError error={publishError} />
      <InlineError error={exportDsl.error} />
      {borrador && (
        <p className="small muted">
          El contenido de escenarios, preguntas y rúbrica se carga con CaseDSL. Para cambiarlo, exporta el caso, edítalo e impórtalo como
          un borrador nuevo.
        </p>
      )}

      <section className="section" aria-labelledby="h-situacion">
        <h2 id="h-situacion">Desarrollo situacional</h2>
        <Text value={c.desarrollo_situacional} />
      </section>
      <section className="section" aria-labelledby="h-historia">
        <h2 id="h-historia">Historia</h2>
        <Text value={c.historia} />
      </section>

      <section className="section" aria-labelledby="h-escenarios">
        <h2 id="h-escenarios">Escenarios y decisiones</h2>
        <p className="small muted">Las opciones marcadas son las correctas. Esta información nunca se muestra al estudiante durante el caso.</p>
        {c.escenarios.length === 0 && <p className="muted">Este caso no tiene escenarios.</p>}
        {c.escenarios.map((e) => (
          <article key={e.id} className="scenario">
            <h3>
              Escena {e.orden}. {e.titulo}
            </h3>
            <Text value={e.contexto} />
            {e.preguntas.map((p) => (
              <div key={p.id} className="question-block">
                <strong>{p.enunciado}</strong>
                {p.criterio_id && <span className="small muted">Criterio: {criterios.get(p.criterio_id) ?? 'sin criterio'}</span>}
                <ol className="option-list">
                  {p.opciones.map((o, i) => (
                    <li key={o.id} className={o.es_correcta ? 'option-correct' : undefined}>
                      <span className="option-letter" aria-hidden="true">
                        {optionLetter(i)}
                      </span>
                      <span>
                        {o.texto}
                        {o.es_correcta && <strong> (correcta)</strong>}
                        {o.justificacion && <span className="muted"> {o.justificacion}</span>}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </article>
        ))}
      </section>

      <section className="section" aria-labelledby="h-rubrica">
        <h2 id="h-rubrica">Rúbrica</h2>
        {!c.rubrica ? (
          <p className="muted">Sin rúbrica.</p>
        ) : (
          <>
            <p className="small muted">Escala máxima: {formatDecimal(c.rubrica.escala_max)}</p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Criterio</th>
                    <th className="num">Peso</th>
                    <th>Niveles</th>
                  </tr>
                </thead>
                <tbody>
                  {c.rubrica.criterios.map((cr) => (
                    <tr key={cr.id}>
                      <td>{cr.descripcion}</td>
                      <td className="num">{formatDecimal(cr.peso)} %</td>
                      <td>
                        {cr.niveles.length === 0
                          ? '—'
                          : cr.niveles
                              .map(
                                (n) =>
                                  `${n.nombre}: ${formatDecimal(n.valor)}${n.min_aciertos_pct !== undefined && n.min_aciertos_pct !== null ? ` (desde ${formatDecimal(n.min_aciertos_pct, 0)} %)` : ''}`,
                              )
                              .join('; ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {borrador && puedeEditar && (
        <div>
          <button type="button" className="btn btn-danger" onClick={() => setDialog('delete')}>
            Eliminar borrador
          </button>
        </div>
      )}

      {dialog === 'edit' && <EditGeneral c={c} onClose={() => setDialog(null)} />}
      <ConfirmDialog
        open={dialog === 'archive'}
        title="¿Archivar el caso?"
        confirmLabel="Archivar"
        danger
        pending={archive.isPending}
        error={<InlineError error={archive.error} />}
        onConfirm={() => archive.mutate()}
        onClose={() => setDialog(null)}
      >
        <p>Ya no podrás asignarlo a nuevas sesiones. Las sesiones existentes no cambian. El archivado no se puede revertir.</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={dialog === 'delete'}
        title="¿Eliminar este borrador?"
        confirmLabel="Eliminar"
        danger
        pending={remove.isPending}
        error={<InlineError error={remove.error} />}
        onConfirm={() => remove.mutate()}
        onClose={() => setDialog(null)}
      >
        <p>Se eliminará con todo su contenido. Esta acción no se puede deshacer.</p>
      </ConfirmDialog>
    </main>
  )
}
