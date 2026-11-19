import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { DataTable } from '../../components/design-system/DataTable'
import { Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, InlineError, QueryBoundary } from '../../components/design-system/states'
import { Status } from '../../components/design-system/Status'
import { Button } from '../../components/ui/Button'
import { Dialog } from '../../components/ui/Dialog'
import { SearchField, SelectField, TextField } from '../../components/ui/Field'
import { LinkTabs } from '../../components/ui/Tabs'
import { useUserMutations, useUsers } from '../../hooks/use-academic'
import { useSession } from '../../hooks/use-session'
import { EMAIL_RE } from '../../lib/format'
import { ROL } from '../../lib/labels'
import type { Rol, Usuario } from '../../types/api'

type RoleFilter = 'todos' | Rol
const TABS: { id: RoleFilter; label: string }[] = [
  { id: 'todos', label: 'Todos' },
  { id: 'DOCENTE', label: 'Docentes' },
  { id: 'ESTUDIANTE', label: 'Estudiantes' },
  { id: 'ADMINISTRADOR', label: 'Administración' },
]

type DialogState = { kind: 'create'; rol: 'DOCENTE' | 'ESTUDIANTE' } | { kind: 'edit'; user: Usuario } | null

/** Usuarios (CU2, CU4): listado con búsqueda y filtros, alta, edición, estado y permiso de casos. El rol no se cambia. */
export function UsersView() {
  const { session } = useSession()
  const selfId = session?.kind === 'staff' ? session.user.id : ''
  const [params, setParams] = useSearchParams()
  const rol = (TABS.find((t) => t.id === params.get('rol'))?.id ?? 'todos') as RoleFilter
  const [estado, setEstado] = useState<'todos' | 'activos' | 'inactivos'>('todos')
  const [search, setSearch] = useState('')
  const nuevo = params.get('nuevo')
  const [dialog, setDialog] = useState<DialogState>(nuevo === 'DOCENTE' || nuevo === 'ESTUDIANTE' ? { kind: 'create', rol: nuevo } : null)
  const q = useUsers({ rol: rol === 'todos' ? undefined : rol, activo: estado === 'todos' ? undefined : estado === 'activos' })
  const m = useUserMutations()

  const closeDialog = () => {
    setDialog(null)
    if (nuevo) {
      params.delete('nuevo')
      setParams(params, { replace: true })
    }
  }

  return (
    <Page>
      <PageHeader
        title="Usuarios"
        description="Los roles no se cambian después de crear la cuenta. Los estudiantes no tienen contraseña: entran con el código de cada convocatoria."
        actions={
          <>
            <Button icon="plus" onClick={() => setDialog({ kind: 'create', rol: 'ESTUDIANTE' })}>
              Crear estudiante
            </Button>
            <Button icon="plus" variant="primary" onClick={() => setDialog({ kind: 'create', rol: 'DOCENTE' })}>
              Crear docente
            </Button>
          </>
        }
      />
      <div className="toolbar">
        <LinkTabs label="Filtrar por rol" tabs={TABS} current={rol} param="rol" />
        <div className="toolbar-filters">
          <SelectField label="Estado" hideLabel value={estado} onChange={(e) => setEstado(e.target.value as typeof estado)}>
            <option value="todos">Todos los estados</option>
            <option value="activos">Activas</option>
            <option value="inactivos">Desactivadas</option>
          </SelectField>
          <SearchField label="Buscar usuarios" value={search} onChange={setSearch} placeholder="Nombre, correo o código" />
        </div>
      </div>
      <InlineError error={m.setStatus.error ?? m.setCasePermission.error} />
      <QueryBoundary query={q} loading="Cargando usuarios…" errorTitle="No se pudieron cargar los usuarios">
        {(page) => {
          const term = search.trim().toLowerCase()
          const rows = page.items.filter((u) => !term || `${u.nombre_completo} ${u.correo} ${u.codigo_institucional ?? ''}`.toLowerCase().includes(term))
          return (
            <>
              <DataTable
                caption="Usuarios"
                rows={rows}
                rowKey={(u) => u.id}
                empty={<EmptyState icon="users" title="Ningún usuario coincide">Prueba con otro filtro o término de búsqueda.</EmptyState>}
                columns={[
                  {
                    key: 'n',
                    header: 'Nombre',
                    cell: (u) => (
                      <>
                        <span className="cell-title">{u.nombre_completo}</span>
                        <div className="small muted">{u.correo}</div>
                      </>
                    ),
                  },
                  { key: 'r', header: 'Rol', cell: (u) => ROL[u.rol] },
                  {
                    key: 'e',
                    header: 'Estado',
                    cell: (u) => (
                      <Status fill={u.activo ? 'full' : 'empty'} tone={u.activo ? undefined : 'muted'}>
                        {u.activo ? 'Activa' : 'Desactivada'}
                      </Status>
                    ),
                  },
                  {
                    key: 'p',
                    header: 'Casos',
                    cell: (u) => (u.rol === 'DOCENTE' ? (u.puede_crear_casos ? 'Puede crear' : 'Sin permiso') : '—'),
                  },
                  {
                    key: 'a',
                    header: 'Acciones',
                    srOnlyHeader: true,
                    cell: (u) => (
                      <div className="btn-row">
                        {u.rol !== 'ADMINISTRADOR' && (
                          <Button size="sm" variant="quiet" icon="edit" onClick={() => setDialog({ kind: 'edit', user: u })}>
                            Editar
                          </Button>
                        )}
                        {u.rol === 'DOCENTE' && (
                          <Button size="sm" variant="quiet" onClick={() => m.setCasePermission.mutate({ id: u.id, value: !u.puede_crear_casos })} disabled={m.setCasePermission.isPending}>
                            {u.puede_crear_casos ? 'Quitar permiso de casos' : 'Permitir crear casos'}
                          </Button>
                        )}
                        {u.id !== selfId && u.rol !== 'ADMINISTRADOR' && (
                          <Button size="sm" variant={u.activo ? 'danger' : 'secondary'} onClick={() => m.setStatus.mutate({ id: u.id, activo: !u.activo })} disabled={m.setStatus.isPending}>
                            {u.activo ? 'Desactivar' : 'Activar'}
                          </Button>
                        )}
                      </div>
                    ),
                  },
                ]}
              />
              {page.total > page.items.length && (
                <p className="small muted">
                  Se muestran {page.items.length} de {page.total}. Filtra por rol o estado para acotar.
                </p>
              )}
            </>
          )
        }}
      </QueryBoundary>
      {dialog && <UserFormDialog state={dialog} onClose={closeDialog} />}
    </Page>
  )
}

function UserFormDialog({ state, onClose }: { state: NonNullable<DialogState>; onClose: () => void }) {
  const m = useUserMutations()
  const editing = state.kind === 'edit' ? state.user : null
  const rol = editing ? editing.rol : state.kind === 'create' ? state.rol : 'ESTUDIANTE'
  const [nombre, setNombre] = useState(editing?.nombre_completo ?? '')
  const [correo, setCorreo] = useState(editing?.correo ?? '')
  const [clave, setClave] = useState('')
  const [codigo, setCodigo] = useState(editing?.codigo_institucional ?? '')
  const [err, setErr] = useState<string | null>(null)
  const pending = m.createTeacher.isPending || m.createStudent.isPending || m.update.isPending
  const error = m.createTeacher.error ?? m.createStudent.error ?? m.update.error

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!nombre.trim()) return setErr('Escribe el nombre completo.')
    if (!EMAIL_RE.test(correo.trim())) return setErr('El correo no tiene un formato válido.')
    if (!editing && rol === 'DOCENTE' && (clave.length < 8 || clave.length > 128)) return setErr('La contraseña debe tener entre 8 y 128 caracteres.')
    setErr(null)
    const base = { nombre_completo: nombre.trim(), correo: correo.trim(), codigo_institucional: codigo.trim() || null }
    if (editing) m.update.mutate({ id: editing.id, data: base }, { onSuccess: onClose })
    else if (rol === 'DOCENTE') m.createTeacher.mutate({ ...base, clave }, { onSuccess: onClose })
    else m.createStudent.mutate(base, { onSuccess: onClose })
  }

  return (
    <Dialog open title={editing ? `Editar ${ROL[rol].toLowerCase()}` : rol === 'DOCENTE' ? 'Crear docente' : 'Crear estudiante'} onClose={onClose}>
      <form className="form-grid" onSubmit={submit} noValidate>
        {rol === 'ESTUDIANTE' && !editing && <p className="small muted">Los estudiantes no tienen contraseña: entran con el código de cada convocatoria.</p>}
        <TextField label="Nombre completo" maxLength={150} value={nombre} onChange={(e) => setNombre(e.target.value)} />
        <TextField label="Correo institucional" type="email" maxLength={150} value={correo} onChange={(e) => setCorreo(e.target.value)} />
        {!editing && rol === 'DOCENTE' && (
          <TextField label="Contraseña inicial" type="password" autoComplete="new-password" value={clave} onChange={(e) => setClave(e.target.value)} hint="Entre 8 y 128 caracteres. El docente puede cambiarla desde Mi cuenta." />
        )}
        <TextField label="Código institucional (opcional)" maxLength={30} value={codigo} onChange={(e) => setCodigo(e.target.value)} />
        {err && <p className="field-error">{err}</p>}
        <InlineError error={error} />
        <div className="dialog-actions">
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="primary" pending={pending} pendingLabel="Guardando…">
            {editing ? 'Guardar cambios' : 'Crear cuenta'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
