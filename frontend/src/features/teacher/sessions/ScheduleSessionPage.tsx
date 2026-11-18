import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { casesApi, sessionsApi, spacesApi } from '../../../api/endpoints'
import { ErrorState, InlineError, Loading } from '../../../components/states'
import { EMAIL_RE, localInputToIso, parseEmails, toLocalInput } from '../../../lib/format'

interface Errors {
  caso?: string
  inicio?: string
  fin?: string
  tiempo?: string
  estudiantes?: string
}

/** Por defecto la sesión empieza ahora (minuto actual): así puede abrirse de inmediato. */
function defaultStart() {
  const d = new Date()
  d.setSeconds(0, 0)
  return d
}

export function ScheduleSessionPage() {
  const { spaceId = '' } = useParams()
  const navigate = useNavigate()
  const space = useQuery({ queryKey: ['space', spaceId], queryFn: () => spacesApi.get(spaceId) })
  const cases = useQuery({ queryKey: ['cases', 'PUBLICADO'], queryFn: () => casesApi.list({ estado: 'PUBLICADO' }) })

  const [start] = useState(defaultStart)
  const [casoId, setCasoId] = useState('')
  const [inicio, setInicio] = useState(() => toLocalInput(start))
  const [fin, setFin] = useState(() => toLocalInput(new Date(start.getTime() + 2 * 3600_000)))
  const [tiempo, setTiempo] = useState('')
  const [lugar, setLugar] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [correos, setCorreos] = useState('')
  const [errors, setErrors] = useState<Errors>({})

  const caso = useMemo(() => cases.data?.items.find((c) => c.id === casoId), [cases.data, casoId])
  const maxTiempo = Math.min(240, caso?.tiempo_estimado_min ?? 240)
  const emails = parseEmails(correos)

  const create = useMutation({
    mutationFn: () =>
      sessionsApi.create({
        caso_id: casoId,
        espacio_academico_id: spaceId,
        inicio: localInputToIso(inicio)!,
        fin: localInputToIso(fin)!,
        tiempo_max_min: Number(tiempo),
        lugar: lugar.trim() || null,
        mensaje: mensaje.trim() || null,
        estudiantes: emails,
      }),
    onSuccess: (s) => navigate(`/sesiones/${s.id}?tab=convocados&nueva=1`, { replace: true }),
  })

  const validate = () => {
    const e: Errors = {}
    if (!casoId) e.caso = 'Elige el caso que resolverán los estudiantes.'
    const a = localInputToIso(inicio)
    const b = localInputToIso(fin)
    if (!a) e.inicio = 'Indica la fecha y hora de inicio.'
    if (!b) e.fin = 'Indica la fecha y hora de finalización.'
    if (a && b && new Date(a) >= new Date(b)) e.fin = 'La finalización debe ser posterior al inicio.'
    else if (b && new Date(b) <= new Date()) e.fin = 'La finalización debe ser una hora futura.'
    const t = Number(tiempo)
    if (!tiempo || !Number.isInteger(t) || t < 1) e.tiempo = 'Indica un tiempo máximo en minutos.'
    else if (t > maxTiempo)
      e.tiempo = caso?.tiempo_estimado_min
        ? `No puede superar el tiempo estimado del caso (${caso.tiempo_estimado_min} min).`
        : 'El máximo es 240 minutos.'
    const malos = emails.filter((m) => !EMAIL_RE.test(m))
    if (malos.length) e.estudiantes = `Revisa estos correos: ${malos.slice(0, 5).join(', ')}${malos.length > 5 ? '…' : ''}`
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const onSubmit = (ev: FormEvent) => {
    ev.preventDefault()
    if (validate()) create.mutate()
  }

  if (space.isPending || cases.isPending) return <main className="page page-narrow" id="contenido"><Loading /></main>
  if (space.isError) return <main className="page page-narrow" id="contenido"><ErrorState error={space.error} /></main>
  if (cases.isError)
    return (
      <main className="page page-narrow" id="contenido">
        <ErrorState error={cases.error} title="No se pudieron cargar tus casos" onRetry={() => cases.refetch()} />
      </main>
    )

  const publicados = cases.data.items

  return (
    <main className="page page-narrow" id="contenido">
      <div>
        <div className="crumbs">
          <Link to={`/aulas/${spaceId}`}>{space.data.nombre}</Link>
        </div>
        <h1>Asignar un caso</h1>
        <p className="lede muted" style={{ marginTop: '0.4rem' }}>
          Se creará una sesión en {space.data.nombre} ({space.data.periodo}). Cada estudiante convocado recibe un código de acceso
          personal.
        </p>
      </div>

      {publicados.length === 0 ? (
        <div className="notice notice-info">
          <div>
            <strong>No tienes casos publicados.</strong>
            Solo los casos publicados pueden asignarse. <Link to="/casos">Revisa tus casos</Link> para publicar uno.
          </div>
        </div>
      ) : (
        <form className="form-grid" onSubmit={onSubmit} noValidate>
          <div className="field">
            <label htmlFor="caso">Caso</label>
            <select
              id="caso"
              value={casoId}
              onChange={(e) => {
                setCasoId(e.target.value)
                const c = publicados.find((x) => x.id === e.target.value)
                if (c?.tiempo_estimado_min && !tiempo) setTiempo(String(c.tiempo_estimado_min))
              }}
              aria-invalid={errors.caso ? true : undefined}
              aria-describedby={errors.caso ? 'caso-err' : undefined}
            >
              <option value="">Elige un caso publicado</option>
              {publicados.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                  {c.tiempo_estimado_min ? ` (${c.tiempo_estimado_min} min)` : ''}
                </option>
              ))}
            </select>
            {errors.caso && <span className="field-error" id="caso-err">{errors.caso}</span>}
          </div>

          <div className="form-grid two">
            <div className="field">
              <label htmlFor="inicio">Inicio</label>
              <input id="inicio" type="datetime-local" value={inicio} onChange={(e) => setInicio(e.target.value)} aria-invalid={errors.inicio ? true : undefined} aria-describedby={errors.inicio ? 'inicio-err' : undefined} />
              {errors.inicio && <span className="field-error" id="inicio-err">{errors.inicio}</span>}
            </div>
            <div className="field">
              <label htmlFor="fin">Finalización</label>
              <input id="fin" type="datetime-local" value={fin} onChange={(e) => setFin(e.target.value)} aria-invalid={errors.fin ? true : undefined} aria-describedby={errors.fin ? 'fin-err' : undefined} />
              {errors.fin && <span className="field-error" id="fin-err">{errors.fin}</span>}
            </div>
          </div>
          <p className="small muted" style={{ marginTop: '-0.5rem' }}>
            Hora local de tu equipo. La sesión no se abre sola: deberás abrirla tú a partir de la hora de inicio. Los estudiantes pueden
            ingresar hasta un límite dentro de esa ventana, que el sistema calcula y te mostrará.
          </p>

          <div className="field">
            <label htmlFor="tiempo">Tiempo máximo por intento (minutos)</label>
            <input
              id="tiempo"
              type="number"
              min={1}
              max={maxTiempo}
              inputMode="numeric"
              value={tiempo}
              onChange={(e) => setTiempo(e.target.value)}
              aria-invalid={errors.tiempo ? true : undefined}
              aria-describedby="tiempo-hint"
            />
            <span className="hint" id="tiempo-hint">
              {errors.tiempo ? (
                <span className="field-error">{errors.tiempo}</span>
              ) : caso?.tiempo_estimado_min ? (
                `Hasta ${caso.tiempo_estimado_min} minutos, el tiempo estimado del caso.`
              ) : (
                'Cuenta desde que cada estudiante empieza su intento.'
              )}
            </span>
          </div>

          <div className="field">
            <label htmlFor="lugar">Lugar o modalidad (opcional)</label>
            <input id="lugar" maxLength={150} value={lugar} onChange={(e) => setLugar(e.target.value)} placeholder="Salón 204 o En línea" />
          </div>

          <div className="field">
            <label htmlFor="mensaje">Mensaje para los estudiantes (opcional)</label>
            <textarea id="mensaje" maxLength={5000} value={mensaje} onChange={(e) => setMensaje(e.target.value)} />
          </div>

          <div className="field">
            <label htmlFor="estudiantes">Estudiantes convocados</label>
            <textarea
              id="estudiantes"
              value={correos}
              onChange={(e) => setCorreos(e.target.value)}
              placeholder="Un correo institucional por línea, o separados por comas"
              aria-invalid={errors.estudiantes ? true : undefined}
              aria-describedby="estudiantes-hint"
            />
            <span className="hint" id="estudiantes-hint">
              {errors.estudiantes ? (
                <span className="field-error">{errors.estudiantes}</span>
              ) : (
                `${emails.length} ${emails.length === 1 ? 'correo' : 'correos'}. Deben ser cuentas de estudiante activas. También puedes convocar después.`
              )}
            </span>
          </div>

          <InlineError error={create.error} />

          <div className="btn-row">
            <button type="submit" className="btn btn-primary" disabled={create.isPending} aria-busy={create.isPending}>
              {create.isPending ? 'Creando sesión…' : 'Crear sesión'}
            </button>
            <Link className="btn btn-quiet" to={`/aulas/${spaceId}`}>
              Cancelar
            </Link>
          </div>
        </form>
      )}
    </main>
  )
}
