import { useState, type FormEvent } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { CaseStatus } from '../../components/design-system/domain-status'
import { Notice, Page, PageHeader, Section } from '../../components/design-system/layout'
import { ErrorState, InlineError, LoadingState } from '../../components/design-system/states'
import { Button } from '../../components/ui/Button'
import { ConfirmDialog, Dialog } from '../../components/ui/Dialog'
import { TextAreaField, TextField } from '../../components/ui/Field'
import { LinkTabs } from '../../components/ui/Tabs'
import { useCase, useCaseEditor, useCaseLifecycle } from '../../hooks/use-cases'
import { useSession } from '../../hooks/use-session'
import { ApiError } from '../../services/http-client'
import type { CasoDetalle, ErrorValidacion } from '../../types/api'
import { CaseContent } from './CaseContent'
import { RubricEditor } from './editor/RubricEditor'
import { ScenarioList } from './editor/ScenarioEditor'
import { VisualEditor } from './visual/VisualEditor'

export function CaseDetailView() {
  const { caseId = '' } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { session } = useSession()
  const canEdit = session?.kind === 'staff' && session.user.puede_crear_casos
  const q = useCase(caseId)
  const life = useCaseLifecycle(caseId)
  const editor = useCaseEditor(caseId)
  const [errores, setErrores] = useState<ErrorValidacion[] | null>(null)
  const [validOk, setValidOk] = useState(false)
  const [dialog, setDialog] = useState<'info' | 'archive' | 'delete' | null>(null)
  const vista = params.get('vista') === 'personaje' ? 'personaje' : 'contenido'

  if (q.isPending)
    return (
      <Page>
        <LoadingState label="Cargando caso…" />
      </Page>
    )
  if (q.isError)
    return (
      <Page>
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </Page>
    )

  const c = q.data
  const borrador = c.estado === 'BORRADOR'
  const editable = borrador && canEdit
  const decisiones = c.escenarios.reduce((n, e) => n + e.preguntas.length, 0)
  const publishError = life.publish.error instanceof ApiError && life.publish.error.status === 422 && errores ? null : life.publish.error

  const validate = () =>
    life.validate.mutate(undefined, {
      onSuccess: (r) => {
        setErrores(r.valido ? null : r.errores)
        setValidOk(r.valido)
      },
    })
  const publish = () =>
    life.publish.mutate(undefined, {
      onSuccess: () => {
        setErrores(null)
        setValidOk(false)
      },
      onError: (err) => {
        if (err instanceof ApiError && err.status === 422) {
          const body = err.body as { errores?: ErrorValidacion[] }
          if (body?.errores) setErrores(body.errores)
        }
      },
    })

  return (
    <Page width={vista === 'personaje' ? 'wide' : 'reading'}>
      <PageHeader
        crumbs={[{ label: 'Casos', to: '/docente/casos' }]}
        title={c.nombre}
        meta={
          <>
            <CaseStatus estado={c.estado} />
            {c.tiempo_estimado_min && <span>{c.tiempo_estimado_min} min estimados</span>}
            <span>
              {c.escenarios.length} {c.escenarios.length === 1 ? 'escena' : 'escenas'}, {decisiones} {decisiones === 1 ? 'decisión' : 'decisiones'}
            </span>
          </>
        }
        actions={
          <>
            <Button icon="download" onClick={() => life.exportDsl.mutate()} pending={life.exportDsl.isPending}>
              Exportar CaseDSL
            </Button>
            {editable && (
              <>
                <Button icon="check" onClick={validate} pending={life.validate.isPending} pendingLabel="Validando…">
                  Validar
                </Button>
                <Button variant="primary" onClick={publish} pending={life.publish.isPending} pendingLabel="Publicando…">
                  Publicar
                </Button>
              </>
            )}
            {c.estado === 'PUBLICADO' && canEdit && (
              <Button variant="danger" onClick={() => setDialog('archive')}>
                Archivar
              </Button>
            )}
          </>
        }
      />

      {params.get('creado') && borrador && (
        <Notice tone="ok" title="Borrador creado.">
          Completa escenas, decisiones, opciones y rúbrica; después valida y publica para poder programarlo.
        </Notice>
      )}
      {borrador && !canEdit && <Notice tone="info">Tu cuenta no tiene permiso para modificar casos. Puedes consultarlo y exportarlo.</Notice>}
      {validOk && <Notice tone="ok">El caso cumple todas las reglas y puede publicarse.</Notice>}
      {errores && errores.length > 0 && (
        <Notice tone="error" title={`El caso todavía no se puede publicar (${errores.length}).`}>
          <ul className="error-list">
            {errores.map((e, i) => (
              <li key={i}>{e.mensaje}</li>
            ))}
          </ul>
        </Notice>
      )}
      <InlineError error={life.validate.error} />
      <InlineError error={publishError} />
      <InlineError error={life.exportDsl.error} />
      <InlineError error={editor.error} />

      <LinkTabs
        label="Secciones del caso"
        param="vista"
        current={vista}
        tabs={[
          { id: 'contenido', label: 'Contenido académico' },
          { id: 'personaje', label: 'Personaje y reacciones' },
        ]}
      />

      {vista === 'personaje' ? (
        <VisualEditor caso={c} />
      ) : editable ? (
        <>
          <Section
            title="Información general"
            actions={
              <Button size="sm" icon="edit" onClick={() => setDialog('info')}>
                Editar
              </Button>
            }
          >
            <CaseContent caso={c} only="general" />
          </Section>
          <Section title="Escenas y decisiones" description="Cada decisión necesita al menos dos opciones, una correcta y una justificación por opción.">
            <ScenarioList escenarios={c.escenarios} ctx={{ run: editor.mutate, pending: editor.isPending, criterios: c.rubrica?.criterios ?? [] }} />
          </Section>
          <Section title="Rúbrica" description="Los pesos de los criterios deben sumar 100.">
            <RubricEditor rubrica={c.rubrica} ctx={{ run: editor.mutate, pending: editor.isPending }} />
          </Section>
          <div>
            <Button variant="danger" icon="trash" onClick={() => setDialog('delete')}>
              Eliminar borrador
            </Button>
          </div>
        </>
      ) : (
        <CaseContent caso={c} />
      )}

      {dialog === 'info' && <GeneralInfoDialog caso={c} onClose={() => setDialog(null)} save={life.update} />}
      <ConfirmDialog
        open={dialog === 'archive'}
        title="¿Archivar el caso?"
        confirmLabel="Archivar"
        danger
        pending={life.archive.isPending}
        error={<InlineError error={life.archive.error} />}
        onConfirm={() => life.archive.mutate(undefined, { onSuccess: () => setDialog(null) })}
        onClose={() => setDialog(null)}
      >
        <p>Ya no podrás programarlo en nuevas sesiones. Las sesiones existentes no cambian. No se puede revertir.</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={dialog === 'delete'}
        title="¿Eliminar este borrador?"
        confirmLabel="Eliminar"
        danger
        pending={life.remove.isPending}
        error={<InlineError error={life.remove.error} />}
        onConfirm={() => life.remove.mutate(undefined, { onSuccess: () => navigate('/docente/casos', { replace: true }) })}
        onClose={() => setDialog(null)}
      >
        <p>Se eliminará con todo su contenido. No se puede deshacer.</p>
      </ConfirmDialog>
    </Page>
  )
}

function GeneralInfoDialog({ caso, onClose, save }: { caso: CasoDetalle; onClose: () => void; save: ReturnType<typeof useCaseLifecycle>['update'] }) {
  const [nombre, setNombre] = useState(caso.nombre)
  const [tiempo, setTiempo] = useState(caso.tiempo_estimado_min ? String(caso.tiempo_estimado_min) : '')
  const [desarrollo, setDesarrollo] = useState(caso.desarrollo_situacional ?? '')
  const [historia, setHistoria] = useState(caso.historia ?? '')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(
      { nombre: nombre.trim(), tiempo_estimado_min: tiempo ? Number(tiempo) : null, desarrollo_situacional: desarrollo.trim() || null, historia: historia.trim() || null },
      { onSuccess: onClose },
    )
  }
  return (
    <Dialog open title="Editar información general" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} required />
        <TextField label="Tiempo estimado (minutos, 1 a 240)" type="number" min={1} max={240} value={tiempo} onChange={(e) => setTiempo(e.target.value)} />
        <TextAreaField label="Desarrollo situacional" value={desarrollo} onChange={(e) => setDesarrollo(e.target.value)} />
        <TextAreaField label="Historia" value={historia} onChange={(e) => setHistoria(e.target.value)} />
        <InlineError error={save.error} />
        <div className="dialog-actions">
          <Button onClick={onClose}>Cancelar</Button>
          <Button type="submit" variant="primary" pending={save.isPending} pendingLabel="Guardando…">
            Guardar
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
