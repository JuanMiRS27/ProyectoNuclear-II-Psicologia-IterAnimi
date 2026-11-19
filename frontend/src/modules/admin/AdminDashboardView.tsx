import { Link } from 'react-router'
import { DataTable } from '../../components/design-system/DataTable'
import { Page, PageHeader, Section } from '../../components/design-system/layout'
import { InlineError, LoadingState } from '../../components/design-system/states'
import { ButtonLink } from '../../components/ui/Button'
import { Icon } from '../../components/ui/Icon'
import { useDeliveries } from '../../hooks/use-admin'
import { useSpaces, useUsers } from '../../hooks/use-academic'
import { formatDateTime } from '../../lib/format'
import { TIPO_NOTIFICACION } from '../../lib/labels'

function Count({ q, label }: { q: { isPending: boolean; isError: boolean; data?: { total: number } }; label: string }) {
  return (
    <div className="count-cell">
      <span className="count-value">{q.isPending ? '…' : q.isError ? '—' : q.data?.total}</span>
      <span className="count-label">{label}</span>
    </div>
  )
}

/** Inicio de administración: qué gestionar (cuentas, aulas y correos con problemas). */
export function AdminDashboardView() {
  const docentes = useUsers({ rol: 'DOCENTE' })
  const estudiantes = useUsers({ rol: 'ESTUDIANTE' })
  const inactivos = useUsers({ activo: false })
  const aulas = useSpaces({ activo: true })
  const fallidas = useDeliveries('FALLIDA')

  return (
    <Page>
      <PageHeader
        title="Administración"
        description="Cuentas, aulas y el estado de los correos del simulador. La administración no accede a casos, sesiones ni notas."
        actions={
          <>
            <ButtonLink to="/admin/usuarios?nuevo=DOCENTE" icon="plus" variant="primary">
              Crear docente
            </ButtonLink>
            <ButtonLink to="/admin/usuarios?nuevo=ESTUDIANTE" icon="plus">
              Crear estudiante
            </ButtonLink>
          </>
        }
      />

      <div className="count-strip">
        <Count q={docentes} label="docentes" />
        <Count q={estudiantes} label="estudiantes" />
        <Count q={inactivos} label="cuentas desactivadas" />
        <Count q={aulas} label="aulas activas" />
        <Count q={fallidas} label="correos fallidos" />
      </div>

      <div className="two-col">
        <Section title="Gestionar">
          <ul className="manage-list">
            <li>
              <Link to="/admin/usuarios">
                <Icon name="users" />
                <span>
                  <strong>Usuarios</strong>
                  <span className="small muted">Altas, datos, estado de la cuenta y permiso para crear casos.</span>
                </span>
              </Link>
            </li>
            <li>
              <Link to="/admin/aulas">
                <Icon name="classroom" />
                <span>
                  <strong>Aulas</strong>
                  <span className="small muted">Espacios académicos donde los docentes programan sesiones.</span>
                </span>
              </Link>
            </li>
            <li>
              <Link to="/admin/entregas">
                <Icon name="mail" />
                <span>
                  <strong>Entregas de correo</strong>
                  <span className="small muted">Reintentar correos que no se pudieron enviar.</span>
                </span>
              </Link>
            </li>
          </ul>
        </Section>

        <Section title="Correos con fallo" actions={<Link to="/admin/entregas?estado=FALLIDA">Ver todos</Link>}>
          {fallidas.isPending ? (
            <LoadingState />
          ) : fallidas.isError ? (
            <InlineError error={fallidas.error} />
          ) : fallidas.data.items.length === 0 ? (
            <p className="muted">No hay entregas fallidas.</p>
          ) : (
            <DataTable
              caption="Entregas fallidas recientes"
              rows={fallidas.data.items.slice(0, 5)}
              rowKey={(d) => d.id}
              columns={[
                { key: 't', header: 'Aviso', cell: (d) => TIPO_NOTIFICACION[d.tipo] },
                { key: 'i', header: 'Intentos', numeric: true, cell: (d) => d.intentos },
                { key: 'u', header: 'Último intento', cell: (d) => (d.ultimo_intento_en ? formatDateTime(d.ultimo_intento_en) : '—') },
              ]}
            />
          )}
        </Section>
      </div>
    </Page>
  )
}
