import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Page, PageHeader } from '../../components/design-system/layout'
import { InlineError } from '../../components/design-system/states'
import { Button, ButtonLink } from '../../components/ui/Button'
import { TextAreaField, TextField } from '../../components/ui/Field'
import { LinkTabs } from '../../components/ui/Tabs'
import { useCreateCase } from '../../hooks/use-cases'

type Mode = 'borrador' | 'importar'

/** Nuevo caso: borrador vacío para editar pieza a pieza (CU6) o importación CaseDSL (CU11). */
export function CaseCreateView() {
  const [params] = useSearchParams()
  const mode = (params.get('modo') === 'importar' ? 'importar' : 'borrador') as Mode
  return (
    <Page width="narrow">
      <PageHeader crumbs={[{ label: 'Casos', to: '/docente/casos' }]} title="Nuevo caso" description="Siempre se crea como borrador: lo completas, lo validas y lo publicas." />
      <LinkTabs
        label="Forma de crear el caso"
        param="modo"
        current={mode}
        tabs={[
          { id: 'borrador', label: 'Empezar en blanco' },
          { id: 'importar', label: 'Importar CaseDSL' },
        ]}
      />
      {mode === 'borrador' ? <BlankForm /> : <ImportForm />}
    </Page>
  )
}

function BlankForm() {
  const navigate = useNavigate()
  const { blank } = useCreateCase()
  const [nombre, setNombre] = useState('')
  const [tiempo, setTiempo] = useState('')
  const [desarrollo, setDesarrollo] = useState('')
  const [historia, setHistoria] = useState('')
  const [errors, setErrors] = useState<{ nombre?: string; tiempo?: string }>({})
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const next: typeof errors = {}
    if (!nombre.trim()) next.nombre = 'Escribe el nombre del caso.'
    const t = Number(tiempo)
    if (tiempo && (!Number.isInteger(t) || t < 1 || t > 240)) next.tiempo = 'Entre 1 y 240 minutos.'
    setErrors(next)
    if (Object.keys(next).length) return
    blank.mutate(
      {
        nombre: nombre.trim(),
        tiempo_estimado_min: tiempo ? t : null,
        desarrollo_situacional: desarrollo.trim() || null,
        historia: historia.trim() || null,
      },
      { onSuccess: (c) => navigate(`/docente/casos/${c.id}?creado=1`, { replace: true }) },
    )
  }
  return (
    <form className="form-grid" onSubmit={submit} noValidate>
      <TextField label="Nombre del caso" maxLength={200} value={nombre} onChange={(e) => setNombre(e.target.value)} error={errors.nombre} />
      <TextField label="Tiempo estimado (minutos)" type="number" min={1} max={240} value={tiempo} onChange={(e) => setTiempo(e.target.value)} error={errors.tiempo} hint="Opcional en el borrador; obligatorio para publicar." />
      <TextAreaField label="Desarrollo situacional" value={desarrollo} onChange={(e) => setDesarrollo(e.target.value)} hint="La situación que el estudiante lee antes de empezar." />
      <TextAreaField label="Historia" value={historia} onChange={(e) => setHistoria(e.target.value)} />
      <InlineError error={blank.error} />
      <div className="btn-row">
        <Button type="submit" variant="primary" pending={blank.isPending} pendingLabel="Creando…">
          Crear borrador
        </Button>
        <ButtonLink to="/docente/casos" variant="quiet">
          Cancelar
        </ButtonLink>
      </div>
    </form>
  )
}

function ImportForm() {
  const navigate = useNavigate()
  const { fromDsl } = useCreateCase()
  const [text, setText] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    let dsl: unknown
    try {
      dsl = JSON.parse(text)
    } catch {
      setParseError('El contenido no es un JSON válido. Revisa comas, comillas y llaves.')
      return
    }
    setParseError(null)
    fromDsl.mutate(dsl, { onSuccess: (c) => navigate(`/docente/casos/${c.id}?creado=1`, { replace: true }) })
  }
  return (
    <form className="form-grid" onSubmit={submit} noValidate>
      <p className="small muted">
        Carga un documento CaseDSL 1.0 con el caso, sus escenarios, preguntas, opciones y rúbrica. Puedes partir de un caso exportado desde aquí.
      </p>
      <TextField
        label="Archivo .json"
        type="file"
        accept="application/json,.json"
        onChange={async (e) => {
          const f = e.target.files?.[0]
          if (f) {
            setText(await f.text())
            setParseError(null)
          }
        }}
      />
      <TextAreaField label="Contenido CaseDSL" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} className="code-area" rows={14} error={parseError} hint='Debe incluir "dslVersion": "1.0".' />
      <InlineError error={fromDsl.error} />
      <div className="btn-row">
        <Button type="submit" variant="primary" icon="upload" disabled={!text.trim()} pending={fromDsl.isPending} pendingLabel="Importando…">
          Importar como borrador
        </Button>
        <ButtonLink to="/docente/casos" variant="quiet">
          Cancelar
        </ButtonLink>
      </div>
    </form>
  )
}
