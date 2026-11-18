import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { usersApi } from '../../api/endpoints'
import type { Rol, Usuario } from '../../api/types'
import { useAuth } from '../../auth/useAuth'
import { Dialog } from '../../components/Dialog'
import { Status } from '../../components/Status'
import { Empty, ErrorState, InlineError, Loading } from '../../components/states'
import { EMAIL_RE } from '../../lib/format'
import { ROL } from '../../lib/labels'

const FILTROS: { id: Rol | ''; label: string }[] = [
  { id: '', label: 'Todos' },
  { id: 'DOCENTE', label: 'Docentes' },
  { id: 'ESTUDIANTE', label: 'Estudiantes' },
  { id: 'ADMINISTRADOR', label: 'Administración' },
]

function CreateUserDialog({ kind, onClose }: { kind: 'DOCENTE' | 'ESTUDIANTE'; onClose: () => void }) {
  const qc = useQueryClient()
  const [nombre, setNombre] = useState('')
  const [correo, setCorreo] = useState('')
  const [clave, setClave] = useState('')
  const [codigo, setCodigo] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const m = useMutation({
    mutationFn: () =>
      kind === 'DOCENTE'
        ? usersApi.createTeacher({ nombre_completo: nombre.trim(), correo: correo.trim(), clave, codigo_institucional: codigo.trim() || null })
        : usersApi.createStudent({ nombre_completo: nombre.trim(), correo: correo.trim(), codigo_institucional: codigo.trim() || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!nombre.trim()) return setErr('Escribe el nombre completo.')
    if (!EMAIL_RE.test(correo.trim())) return setErr('El correo no tiene un formato válido.')
    if (kind === 'DOCENTE' && (clave.length < 8 || clave.length > 128)) return setErr('La contraseña debe tener entre 8 y 128 caracteres.')
    setErr(null)
    m.mutate()
  }
  return (
    <Dialog open title={kind === 'DOCENTE' ? 'Crear docente' : 'Crear estudiante'} onClose={onClose}>
      <form className="form-grid" onSubmit={submit} noValidate>
        {kind === 'ESTUDIANTE' && (
          <p className="small muted">Los estudiantes no tienen contraseña: ingresan con el código de cada convocatoria.</p>
        )}
        <div className="field">
          <label htmlFor="u-nombre">Nombre completo</label>
          <input id="u-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="u-correo">Correo institucional</label>
          <input id="u-correo" type="email" value={correo} onChange={(e) => setCorreo(e.target.value)} />
        </div>
        {kind === 'DOCENTE' && (
          <div className="field">
            <label htmlFor="u-clave">Contraseña inicial</label>
            <input id="u-clave" type="password" autoComplete="new-password" value={clave} onChange={(e) => setClave(e.target.value)} />
            <span className="hint">Entre 8 y 128 caracteres.</span>
          </div>
        )}
        <div className="field">
          <label htmlFor="u-codigo">Código institucional (opcional)</label>
          <input id="u-codigo" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
        </div>
        {err && <p className="field-error">{err}</p>}
        <InlineError error={m.error} />
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={m.isPending}>
            {m.isPending ? 'Creando…' : 'Crear'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}

function UserRow({ u, selfId }: { u: Usuario; selfId: string }) {
  const qc = useQueryClient()
  const done = () => qc.invalidateQueries({ queryKey: ['users'] })
  const status = useMutation({ mutationFn: () => usersApi.setStatus(u.id, !u.activo), onSuccess: done })
  const perm = useMutation({ mutationFn: () => usersApi.setCasePermission(u.id, !u.puede_crear_casos), onSuccess: done })
  const isSelf = u.id === selfId
  return (
    <li>
      <div className="row">
        <div>
          <div className="row-title">{u.nombre_completo}</div>
          <div className="row-meta">
            <span>{u.correo}</span>
            <span>{ROL[u.rol]}</span>
            <Status fill={u.activo ? 'full' : 'empty'} tone={u.activo ? undefined : 'muted'}>
              {u.activo ? 'Activa' : 'Desactivada'}
            </Status>
            {u.rol === 'DOCENTE' && <span>{u.puede_crear_casos ? 'Puede crear casos' : 'Sin permiso para crear casos'}</span>}
          </div>
          <InlineError error={status.error ?? perm.error} />
        </div>
        <div className="row-side">
          {u.rol === 'DOCENTE' && (
            <button type="button" className="btn btn-sm btn-quiet" onClick={() => perm.mutate()} disabled={perm.isPending}>
              {u.puede_crear_casos ? 'Quitar permiso de casos' : 'Permitir crear casos'}
            </button>
          )}
          {!isSelf && (
            <button type="button" className={`btn btn-sm${u.activo ? ' btn-danger' : ''}`} onClick={() => status.mutate()} disabled={status.isPending}>
              {u.activo ? 'Desactivar' : 'Activar'}
            </button>
          )}
        </div>
      </div>
    </li>
  )
}

export function UsersPage() {
  const { session } = useAuth()
  const [params] = useSearchParams()
  const rol = (FILTROS.find((f) => f.id === params.get('rol'))?.id ?? '') as Rol | ''
  const [creating, setCreating] = useState<'DOCENTE' | 'ESTUDIANTE' | null>(null)
  const q = useQuery({ queryKey: ['users', rol], queryFn: () => usersApi.list({ rol: rol || undefined, limit: 100 }) })
  const selfId = session?.kind === 'staff' ? session.user.id : ''

  return (
    <main className="page" id="contenido">
      <div className="page-head">
        <div>
          <h1>Usuarios</h1>
          <p className="lede">Crea cuentas de docentes y estudiantes. Los roles no se cambian después de crear la cuenta.</p>
        </div>
        <div className="btn-row">
          <button type="button" className="btn" onClick={() => setCreating('ESTUDIANTE')}>
            Crear estudiante
          </button>
          <button type="button" className="btn btn-primary" onClick={() => setCreating('DOCENTE')}>
            Crear docente
          </button>
        </div>
      </div>
      <nav className="tabs" aria-label="Filtrar por rol">
        {FILTROS.map((f) => (
          <Link key={f.id} to={f.id ? `?rol=${f.id}` : '?'} replace aria-current={rol === f.id ? 'page' : undefined}>
            {f.label}
          </Link>
        ))}
      </nav>
      {q.isPending ? (
        <Loading label="Cargando usuarios…" />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : q.data.items.length === 0 ? (
        <Empty title="No hay usuarios con este filtro" />
      ) : (
        <>
          <ul className="rows">
            {q.data.items.map((u) => (
              <UserRow key={u.id} u={u} selfId={selfId} />
            ))}
          </ul>
          {q.data.total > q.data.items.length && (
            <p className="small muted">
              Se muestran {q.data.items.length} de {q.data.total}. Filtra por rol para acotar la lista.
            </p>
          )}
        </>
      )}
      {creating && <CreateUserDialog kind={creating} onClose={() => setCreating(null)} />}
    </main>
  )
}
