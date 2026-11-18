import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { ApiError } from '../../api/client'
import { useAuth } from '../../auth/useAuth'
import { homePathFor, pathBelongsTo, type AppSession } from '../../auth/session'
import { BrandMark } from '../../components/AppShell'
import { SceneCharacter } from '../../components/SceneCharacter'
import { EMAIL_RE } from '../../lib/format'

type Method = 'password' | 'code'

interface Errors {
  correo?: string
  secreto?: string
}

function describeLoginError(err: unknown, method: Method): string {
  if (!(err instanceof ApiError)) return 'No se pudo iniciar sesión.'
  if (err.isNetwork) return err.message
  if (err.status === 401) {
    return method === 'password' ? 'El correo o la contraseña no son correctos.' : 'El correo o el código de acceso no son correctos.'
  }
  if (err.status === 429) {
    const min = err.retryAfterSeconds ? Math.ceil(err.retryAfterSeconds / 60) : null
    return min
      ? `Demasiados intentos fallidos. Vuelve a intentarlo en ${min} ${min === 1 ? 'minuto' : 'minutos'}.`
      : err.message
  }
  if (err.status === 422) return 'Revisa el formato del correo.'
  // 403: el servidor explica el motivo (cuenta desactivada, sesión no iniciada, plazo vencido...).
  return err.message
}

export function LoginPage() {
  const { session, notice, loginStaff, loginStudent, clearNotice } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [method, setMethod] = useState<Method>('password')
  const [correo, setCorreo] = useState('')
  const [secreto, setSecreto] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  if (session && !pending) return <Navigate to={homePathFor(session)} replace />

  const validate = () => {
    const e: Errors = {}
    if (!correo.trim()) e.correo = 'Escribe tu correo institucional.'
    else if (!EMAIL_RE.test(correo.trim())) e.correo = 'El correo no tiene un formato válido.'
    if (!secreto.trim()) e.secreto = method === 'password' ? 'Escribe tu contraseña.' : 'Escribe el código de acceso de tu convocatoria.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const onSubmit = async (ev: FormEvent) => {
    ev.preventDefault()
    setFormError(null)
    clearNotice()
    if (!validate()) return
    setPending(true)
    try {
      const next: AppSession =
        method === 'password' ? await loginStaff(correo.trim(), secreto) : await loginStudent(correo.trim(), secreto.trim())
      const from = (location.state as { from?: string } | null)?.from
      // Solo se vuelve a la ruta pedida si pertenece a la zona del rol que determinó el servidor.
      navigate(from && pathBelongsTo(next, from) ? from : homePathFor(next), { replace: true })
    } catch (err) {
      setFormError(describeLoginError(err, method))
      setPending(false)
    }
  }

  const switchMethod = (m: Method) => {
    setMethod(m)
    setSecreto('')
    setErrors({})
    setFormError(null)
  }

  return (
    <div className="login">
      <section className="login-intro" aria-label="Presentación">
        <span className="brand">
          <BrandMark size={26} />
          Iter Animi
        </span>
        <div>
          <h1>Casos de psicología social para decidir y reflexionar</h1>
          <p>Cada caso es una situación que se recorre escena a escena. Lo que importa es cómo razonas cada decisión.</p>
        </div>
        <SceneCharacter className="login-figure" />
      </section>

      <main className="login-main" id="contenido">
        <form className="login-form" onSubmit={onSubmit} noValidate aria-describedby={formError ? 'login-error' : undefined}>
          <div>
            <h2>Ingresar</h2>
            <p className="muted small" style={{ marginTop: '0.35rem' }}>
              Docentes y administración ingresan con su contraseña. Los estudiantes usan el código de acceso que recibieron con su
              convocatoria.
            </p>
          </div>

          {notice === 'expired' && (
            <div className="notice notice-info" role="status">
              <div>Tu sesión expiró. Vuelve a ingresar para continuar.</div>
            </div>
          )}

          <fieldset className="segmented" style={{ margin: 0 }}>
            <legend className="visually-hidden">Forma de ingreso</legend>
            <label>
              <input type="radio" name="metodo" checked={method === 'password'} onChange={() => switchMethod('password')} />
              Con contraseña
            </label>
            <label>
              <input type="radio" name="metodo" checked={method === 'code'} onChange={() => switchMethod('code')} />
              Con código de acceso
            </label>
          </fieldset>

          <div className="field">
            <label htmlFor="correo">Correo institucional</label>
            <input
              id="correo"
              type="email"
              autoComplete="username"
              inputMode="email"
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              aria-invalid={errors.correo ? true : undefined}
              aria-describedby={errors.correo ? 'correo-error' : undefined}
            />
            {errors.correo && (
              <span className="field-error" id="correo-error">
                {errors.correo}
              </span>
            )}
          </div>

          <div className="field">
            <label htmlFor="secreto">{method === 'password' ? 'Contraseña' : 'Código de acceso'}</label>
            <input
              id="secreto"
              type={method === 'password' ? 'password' : 'text'}
              autoComplete={method === 'password' ? 'current-password' : 'one-time-code'}
              autoCapitalize={method === 'code' ? 'characters' : undefined}
              spellCheck={false}
              value={secreto}
              onChange={(e) => setSecreto(e.target.value)}
              aria-invalid={errors.secreto ? true : undefined}
              aria-describedby={[errors.secreto ? 'secreto-error' : '', method === 'code' ? 'secreto-hint' : ''].join(' ').trim() || undefined}
            />
            {method === 'code' && (
              <span className="hint" id="secreto-hint">
                Son 12 caracteres. Puedes escribirlos con o sin guiones. Si la sesión ya terminó, este mismo código abre tus resultados.
              </span>
            )}
            {errors.secreto && (
              <span className="field-error" id="secreto-error">
                {errors.secreto}
              </span>
            )}
          </div>

          {formError && (
            <div className="notice notice-error" role="alert" id="login-error">
              <div>{formError}</div>
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={pending} aria-busy={pending}>
            {pending ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>
      </main>
    </div>
  )
}
