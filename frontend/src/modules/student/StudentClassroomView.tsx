import { Link } from 'react-router'
import { Notice, Page, PageHeader } from '../../components/design-system/layout'
import { ErrorState, LoadingState } from '../../components/design-system/states'
import { formatRange } from '../../lib/format'
import { StudentStatus } from './StudentDashboardView'
import { useStudentPortal } from './use-student-portal'

/**
 * Mi aula: el aula de la sesión a la que fue convocado. No es una matrícula: el backend no registra
 * pertenencia formal a aulas, y el acceso por código solo cubre esta convocatoria.
 */
export function StudentClassroomView() {
  const portal = useStudentPortal()
  if (portal.isPending)
    return (
      <Page>
        <LoadingState label="Cargando tu aula…" />
      </Page>
    )
  if (!portal.view)
    return (
      <Page>
        <ErrorState error={portal.error} title="No se pudo cargar tu aula" onRetry={portal.refetch} />
      </Page>
    )
  const v = portal.view
  return (
    <Page>
      <PageHeader title={v.aula.nombre} meta={<span>Periodo {v.aula.periodo}</span>} description="Aula de la sesión a la que te convocaron." />
      <Notice tone="info">
        Ingresaste con el código de una convocatoria, así que aquí ves solo esa sesión. Si tienes otras convocatorias, entra con su propio
        código.
      </Notice>
      <section className="section" aria-labelledby="h-sesiones-aula">
        <h2 id="h-sesiones-aula">Tu sesión en esta aula</h2>
        <ul className="rows">
          <li>
            <div className="row">
              <div>
                <div className="row-title">
                  <Link to="/estudiante/sesion">{v.casoNombre}</Link>
                </div>
                <div className="row-meta">
                  <StudentStatus status={v.status} />
                  {v.inicio && v.fin && <span>{formatRange(v.inicio, v.fin)}</span>}
                  {v.lugar && <span>{v.lugar}</span>}
                </div>
              </div>
              <div className="row-side">
                <Link className="btn btn-secondary btn-sm" to={v.mode === 'results' ? '/estudiante/resultados' : '/estudiante/sesion'}>
                  {v.mode === 'results' ? 'Ver resultados' : 'Abrir sesión'}
                </Link>
              </div>
            </div>
          </li>
        </ul>
      </section>
    </Page>
  )
}
