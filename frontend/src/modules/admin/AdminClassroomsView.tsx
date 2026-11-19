import { useState, type FormEvent } from 'react'
import { DataTable } from '../../components/design-system/DataTable'
import { Page, PageHeader } from '../../components/design-system/layout'
import { EmptyState, InlineError, QueryBoundary } from '../../components/design-system/states'
import { Status } from '../../components/design-system/Status'
import { Button } from '../../components/ui/Button'
import { Dialog } from '../../components/ui/Dialog'
import { SearchField, TextField } from '../../components/ui/Field'
import { useSaveSpace, useSetSpaceStatus, useSpaces } from '../../hooks/use-academic'
import { formatDate } from '../../lib/format'
import type { Espacio } from '../../types/api'

/** Aulas (CU5): crear, renombrar y activar o desactivar espacios académicos. */
export function AdminClassroomsView() {
  const q = useSpaces()
  const status = useSetSpaceStatus()
  const [editing, setEditing] = useState<Espacio | 'new' | null>(null)
  const [search, setSearch] = useState('')
  return (
    <Page>
      <PageHeader
        title="Aulas"
        description="Las aulas son compartidas: cualquier docente puede programar sesiones en un aula activa, y solo ve las suyas."
        actions={
          <Button variant="primary" icon="plus" onClick={() => setEditing('new')}>
            Crear aula
          </Button>
        }
      />
      <SearchField label="Buscar aulas" value={search} onChange={setSearch} placeholder="Buscar por nombre o periodo" />
      <InlineError error={status.error} />
      <QueryBoundary query={q} loading="Cargando aulas…" errorTitle="No se pudieron cargar las aulas">
        {(page) => {
          const term = search.trim().toLowerCase()
          const rows = page.items.filter((e) => !term || `${e.nombre} ${e.periodo}`.toLowerCase().includes(term))
          return (
            <DataTable
              caption="Aulas"
              rows={rows}
              rowKey={(e) => e.id}
              empty={
                <EmptyState icon="classroom" title={page.items.length === 0 ? 'Aún no hay aulas' : 'Ningún aula coincide'}>
                  {page.items.length === 0 ? 'Crea la primera para que los docentes puedan programar sesiones.' : undefined}
                </EmptyState>
              }
              columns={[
                { key: 'n', header: 'Aula', cell: (e) => <span className="cell-title">{e.nombre}</span> },
                { key: 'p', header: 'Periodo', cell: (e) => e.periodo },
                {
                  key: 's',
                  header: 'Estado',
                  cell: (e) => (
                    <Status fill={e.activo ? 'full' : 'empty'} tone={e.activo ? undefined : 'muted'}>
                      {e.activo ? 'Activa' : 'Inactiva'}
                    </Status>
                  ),
                },
                { key: 'c', header: 'Creada', cell: (e) => formatDate(e.creado_en) },
                {
                  key: 'a',
                  header: 'Acciones',
                  srOnlyHeader: true,
                  cell: (e) => (
                    <div className="btn-row">
                      <Button size="sm" variant="quiet" icon="edit" onClick={() => setEditing(e)}>
                        Editar
                      </Button>
                      <Button size="sm" variant={e.activo ? 'danger' : 'secondary'} onClick={() => status.mutate({ id: e.id, activo: !e.activo })} disabled={status.isPending}>
                        {e.activo ? 'Desactivar' : 'Activar'}
                      </Button>
                    </div>
                  ),
                },
              ]}
            />
          )
        }}
      </QueryBoundary>
      {editing && <SpaceDialog space={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </Page>
  )
}

function SpaceDialog({ space, onClose }: { space: Espacio | null; onClose: () => void }) {
  const save = useSaveSpace()
  const [nombre, setNombre] = useState(space?.nombre ?? '')
  const [periodo, setPeriodo] = useState(space?.periodo ?? '')
  const [err, setErr] = useState<string | null>(null)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!nombre.trim()) return setErr('Escribe el nombre del aula.')
    if (!/^[A-Za-z0-9._-]{1,10}$/.test(periodo.trim())) return setErr('El periodo admite hasta 10 letras, números, puntos o guiones (por ejemplo, 2026-2).')
    setErr(null)
    save.mutate({ id: space?.id, data: { nombre: nombre.trim(), periodo: periodo.trim() } }, { onSuccess: onClose })
  }
  return (
    <Dialog open title={space ? 'Editar aula' : 'Crear aula'} onClose={onClose}>
      <form className="form-grid" onSubmit={submit} noValidate>
        <TextField label="Nombre" maxLength={150} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Psicología Social, grupo 2" />
        <TextField label="Periodo" maxLength={10} value={periodo} onChange={(e) => setPeriodo(e.target.value)} placeholder="2026-2" />
        {err && <p className="field-error">{err}</p>}
        <InlineError error={save.error} />
        <div className="dialog-actions">
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="primary" pending={save.isPending} pendingLabel="Guardando…">
            {space ? 'Guardar' : 'Crear aula'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
