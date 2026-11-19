import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Definitions, Notice, Page, PageHeader, Panel, Section } from '../../components/design-system/layout'
import { InlineError } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { TextField } from '../../components/ui/Field'
import { useSession } from '../../hooks/use-session'
import { ROL } from '../../lib/labels'
import { authService } from '../../services/auth-service'

/** Mi cuenta del personal: datos del perfil (del servidor) y cambio de contraseña (CU3). */
export function AccountView() {
  const { session, logout } = useSession()
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')
  const [errors, setErrors] = useState<{ actual?: string; nueva?: string; repetida?: string }>({})

  const change = useMutation({
    mutationFn: () => authService.changePassword(actual, nueva),
    // El servidor invalida todos los tokens, incluido este: se cierra la sesión y se explica por qué.
    onSuccess: () => logout('password-changed'),
  })

  if (session?.kind !== 'staff') return null
  const u = session.user

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const next: typeof errors = {}
    if (!actual) next.actual = 'Escribe tu contraseña actual.'
    if (nueva.length < 8 || nueva.length > 128) next.nueva = 'La nueva contraseña debe tener entre 8 y 128 caracteres.'
    else if (nueva === actual) next.nueva = 'La nueva contraseña debe ser distinta de la actual.'
    if (repetida !== nueva) next.repetida = 'Las contraseñas no coinciden.'
    setErrors(next)
    if (Object.keys(next).length === 0) change.mutate()
  }

  return (
    <Page width="narrow">
      <PageHeader title="Mi cuenta" description="Tus datos los gestiona la administración del simulador." />
      <Panel>
        <Definitions
          items={[
            { term: 'Nombre', value: u.nombre_completo },
            { term: 'Correo', value: u.correo },
            { term: 'Rol', value: ROL[u.rol] },
            ...(u.rol === 'DOCENTE' ? [{ term: 'Casos', value: u.puede_crear_casos ? 'Puede crear y editar casos' : 'Solo lectura de sus casos' }] : []),
            ...(u.codigo_institucional ? [{ term: 'Código institucional', value: u.codigo_institucional }] : []),
          ]}
        />
      </Panel>
      <Section title="Cambiar contraseña" description="Al cambiarla se cierran todas tus sesiones abiertas, también en otros equipos.">
        <form className="panel form-grid" onSubmit={submit} noValidate>
          <TextField label="Contraseña actual" type="password" autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} error={errors.actual} />
          <TextField
            label="Nueva contraseña"
            type="password"
            autoComplete="new-password"
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            error={errors.nueva}
            hint="Entre 8 y 128 caracteres."
          />
          <TextField label="Repite la nueva contraseña" type="password" autoComplete="new-password" value={repetida} onChange={(e) => setRepetida(e.target.value)} error={errors.repetida} />
          {change.error && <InlineError error={change.error} />}
          {change.isSuccess && <Notice tone="ok">Contraseña actualizada.</Notice>}
          <div>
            <Button type="submit" variant="primary" pending={change.isPending} pendingLabel="Guardando…">
              Cambiar contraseña
            </Button>
          </div>
        </form>
      </Section>
    </Page>
  )
}
