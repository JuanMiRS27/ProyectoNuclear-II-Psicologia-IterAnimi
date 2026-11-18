import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { spacesApi } from '../../api/endpoints'
import type { Espacio } from '../../api/types'
import { Dialog } from '../../components/Dialog'
import { Status } from '../../components/Status'
import { Empty, ErrorState, InlineError, Loading } from '../../components/states'

function SpaceDialog({ space, onClose }: { space: Espacio | null; onClose: () => void }) {
  const qc = useQueryClient()
  const [nombre, setNombre] = useState(space?.nombre ?? '')
  const [periodo, setPeriodo] = useState(space?.periodo ?? '')
  const [err, setErr] = useState<string | null>(null)
  const m = useMutation({
    mutationFn: () =>
      space ? spacesApi.update(space.id, { nombre: nombre.trim(), periodo: periodo.trim() }) : spacesApi.create({ nombre: nombre.trim(), periodo: periodo.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['spaces'] })
      onClose()
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!nombre.trim()) return setErr('Escribe el nombre del aula.')
    if (!/^[A-Za-z0-9._-]{1,10}$/.test(periodo.trim())) return setErr('El periodo admite hasta 10 letras, números, puntos o guiones (por ejemplo, 2026-2).')
    setErr(null)
    m.mutate()
  }
  return (
    <Dialog open title={space ? 'Editar aula' : 'Crear aula'} onClose={onClose}>
      <form className="form-grid" onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="s-nombre">Nombre</label>
          <input id="s-nombre" maxLength={150} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Psicología Social, grupo 2" />
        </div>
        <div className="field">
          <label htmlFor="s-periodo">Periodo</label>
          <input id="s-periodo" maxLength={10} value={periodo} onChange={(e) => setPeriodo(e.target.value)} placeholder="2026-2" />
        </div>
        {err && <p className="field-error">{err}</p>}
        <InlineError error={m.error} />
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={m.isPending}>
            {m.isPending ? 'Guardando…' : space ? 'Guardar' : 'Crear aula'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

function SpaceRow({ e, onEdit }: { e: Espacio; onEdit: () => void }) {
  const qc = useQueryClient()
  const m = useMutation({ mutationFn: () => spacesApi.setStatus(e.id, !e.activo), onSuccess: () => qc.invalidateQueries({ queryKey: ['spaces'] }) })
  return (
    <li>
      <div className="row">
        <div>
          <div className="row-title">{e.nombre}</div>
          <div className="row-meta">
            <span>Periodo {e.periodo}</span>
            <Status fill={e.activo ? 'full' : 'empty'} tone={e.activo ? undefined : 'muted'}>
              {e.activo ? 'Activa' : 'Inactiva'}
            </Status>
          </div>
          <InlineError error={m.error} />
        </div>
        <div className="row-side">
          <button type="button" className="btn btn-sm btn-quiet" onClick={onEdit}>
            Editar
          </button>
          <button type="button" className="btn btn-sm" onClick={() => m.mutate()} disabled={m.isPending}>
            {e.activo ? 'Desactivar' : 'Activar'}
          </button>
        </div>
      </div>
    </li>
  )
}

export function AdminSpacesPage() {
  const q = useQuery({ queryKey: ['spaces', 'all'], queryFn: () => spacesApi.list() })
  const [editing, setEditing] = useState<Espacio | null | 'new'>(null)
  return (
    <main className="page" id="contenido">
      <div className="page-head">
        <div>
          <h1>Aulas</h1>
          <p className="lede">Las aulas (espacios académicos) son compartidas: cualquier docente puede asignar casos en un aula activa.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>
          Crear aula
        </button>
      </div>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.data.items.length === 0 ? (
        <Empty title="Aún no hay aulas">Crea la primera para que los docentes puedan programar sesiones.</Empty>
      ) : (
        <ul className="rows">
          {q.data.items.map((e) => (
            <SpaceRow key={e.id} e={e} onEdit={() => setEditing(e)} />
          ))}
        </ul>
      )}
      {editing && <SpaceDialog space={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </main>
  )
}
