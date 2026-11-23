import { useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui/Button'
import { ConfirmDialog } from '../../../components/ui/Dialog'
import { CheckboxField, SelectField, TextAreaField, TextField } from '../../../components/ui/Field'
import { optionLetter } from '../../../lib/format'
import { caseService } from '../../../services/case-service'
import type { CriterioRead, EscenarioRead, OpcionRead, PreguntaRead, UUID } from '../../../types/api'

export type RunOp = (op: (caseId: UUID) => Promise<unknown>) => void

interface EditorCtx {
  run: RunOp
  pending: boolean
  criterios: CriterioRead[]
}

/** Mueve un elemento en una lista de ids y devuelve el nuevo orden completo (el backend exige la lista entera). */
function moved(ids: UUID[], index: number, delta: -1 | 1) {
  const next = [...ids]
  const [it] = next.splice(index, 1)
  next.splice(index + delta, 0, it!)
  return next
}

export function ScenarioList({ escenarios, ctx }: { escenarios: EscenarioRead[]; ctx: EditorCtx }) {
  const ordered = [...escenarios].sort((a, b) => a.orden - b.orden)
  const ids = ordered.map((e) => e.id)
  return (
    <div className="editor-stack">
      {ordered.map((e, i) => (
        <ScenarioBlock
          key={e.id}
          escenario={e}
          ctx={ctx}
          onMove={(d) => ctx.run((cid) => caseService.reorderScenarios(cid, moved(ids, i, d)))}
          canUp={i > 0}
          canDown={i < ordered.length - 1}
        />
      ))}
      <AddScenarioForm ctx={ctx} />
    </div>
  )
}

function AddScenarioForm({ ctx }: { ctx: EditorCtx }) {
  const [open, setOpen] = useState(false)
  const [titulo, setTitulo] = useState('')
  const [contexto, setContexto] = useState('')
  if (!open)
    return (
      <Button icon="plus" onClick={() => setOpen(true)}>
        Añadir escena
      </Button>
    )
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!titulo.trim()) return
    ctx.run((cid) => caseService.addScenario(cid, { titulo: titulo.trim(), contexto: contexto.trim() || null }))
    setTitulo('')
    setContexto('')
    setOpen(false)
  }
  return (
    <form className="editor-form" onSubmit={submit}>
      <TextField label="Título de la escena" maxLength={200} value={titulo} onChange={(e) => setTitulo(e.target.value)} required />
      <TextAreaField label="Contexto o narración" value={contexto} onChange={(e) => setContexto(e.target.value)} rows={4} />
      <div className="btn-row">
        <Button type="submit" variant="primary" disabled={!titulo.trim() || ctx.pending}>
          Añadir escena
        </Button>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}

function ScenarioBlock({ escenario, ctx, onMove, canUp, canDown }: { escenario: EscenarioRead; ctx: EditorCtx; onMove: (d: -1 | 1) => void; canUp: boolean; canDown: boolean }) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [titulo, setTitulo] = useState(escenario.titulo)
  const [contexto, setContexto] = useState(escenario.contexto ?? '')
  const preguntas = [...escenario.preguntas].sort((a, b) => a.orden - b.orden)
  const qids = preguntas.map((p) => p.id)

  return (
    <article className="editor-block" aria-labelledby={`esc-${escenario.id}`}>
      <header className="editor-head">
        <h3 id={`esc-${escenario.id}`}>
          <span className="editor-order">Escena {escenario.orden}</span> {escenario.titulo}
        </h3>
        <div className="btn-row">
          <Button size="sm" variant="quiet" icon="arrowUp" onClick={() => onMove(-1)} disabled={!canUp || ctx.pending} aria-label="Subir escena">
            Subir
          </Button>
          <Button size="sm" variant="quiet" icon="arrowDown" onClick={() => onMove(1)} disabled={!canDown || ctx.pending} aria-label="Bajar escena">
            Bajar
          </Button>
          <Button size="sm" variant="quiet" icon="edit" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Cerrar' : 'Editar'}
          </Button>
          <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmDelete(true)}>
            Eliminar
          </Button>
        </div>
      </header>

      {editing ? (
        <form
          className="editor-form"
          onSubmit={(e) => {
            e.preventDefault()
            ctx.run((cid) => caseService.updateScenario(cid, escenario.id, { titulo: titulo.trim(), contexto: contexto.trim() || null }))
            setEditing(false)
          }}
        >
          <TextField label="Título" maxLength={200} value={titulo} onChange={(e) => setTitulo(e.target.value)} required />
          <TextAreaField label="Contexto o narración" value={contexto} onChange={(e) => setContexto(e.target.value)} rows={5} />
          <div>
            <Button type="submit" variant="primary" disabled={!titulo.trim() || ctx.pending}>
              Guardar escena
            </Button>
          </div>
        </form>
      ) : (
        escenario.contexto && <p className="editor-context">{escenario.contexto}</p>
      )}

      <div className="editor-questions">
        {preguntas.map((p, i) => (
          <QuestionBlock
            key={p.id}
            pregunta={p}
            ctx={ctx}
            canUp={i > 0}
            canDown={i < preguntas.length - 1}
            onMove={(d) => ctx.run((cid) => caseService.reorderQuestions(cid, escenario.id, moved(qids, i, d)))}
          />
        ))}
        <AddQuestionForm escenarioId={escenario.id} ctx={ctx} />
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="¿Eliminar esta escena?"
        confirmLabel="Eliminar"
        danger
        onConfirm={() => {
          ctx.run((cid) => caseService.removeScenario(cid, escenario.id))
          setConfirmDelete(false)
        }}
        onClose={() => setConfirmDelete(false)}
      >
        <p>Se eliminarán también sus {escenario.preguntas.length} preguntas con sus opciones. Las demás escenas se renumeran.</p>
      </ConfirmDialog>
    </article>
  )
}

function CriterionSelect({ value, onChange, criterios, label = 'Criterio de la rúbrica' }: { value: string; onChange: (v: string) => void; criterios: CriterioRead[]; label?: string }) {
  return (
    <SelectField label={label} value={value} onChange={(e) => onChange(e.target.value)} hint={criterios.length === 0 ? 'Crea primero los criterios en la rúbrica.' : undefined}>
      <option value="">Sin criterio</option>
      {criterios.map((c) => (
        <option key={c.id} value={c.id}>
          {c.descripcion}
        </option>
      ))}
    </SelectField>
  )
}

function AddQuestionForm({ escenarioId, ctx }: { escenarioId: UUID; ctx: EditorCtx }) {
  const [open, setOpen] = useState(false)
  const [enunciado, setEnunciado] = useState('')
  const [criterio, setCriterio] = useState('')
  if (!open)
    return (
      <Button size="sm" icon="plus" onClick={() => setOpen(true)}>
        Añadir decisión
      </Button>
    )
  return (
    <form
      className="editor-form"
      onSubmit={(e) => {
        e.preventDefault()
        if (!enunciado.trim()) return
        ctx.run((cid) => caseService.addQuestion(cid, escenarioId, { enunciado: enunciado.trim(), criterio_id: criterio || null }))
        setEnunciado('')
        setCriterio('')
        setOpen(false)
      }}
    >
      <TextAreaField label="Enunciado de la decisión" value={enunciado} onChange={(e) => setEnunciado(e.target.value)} rows={2} required />
      <CriterionSelect value={criterio} onChange={setCriterio} criterios={ctx.criterios} />
      <div className="btn-row">
        <Button type="submit" variant="primary" disabled={!enunciado.trim() || ctx.pending}>
          Añadir decisión
        </Button>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}

function QuestionBlock({ pregunta, ctx, onMove, canUp, canDown }: { pregunta: PreguntaRead; ctx: EditorCtx; onMove: (d: -1 | 1) => void; canUp: boolean; canDown: boolean }) {
  const [editing, setEditing] = useState(false)
  const [enunciado, setEnunciado] = useState(pregunta.enunciado)
  const [criterio, setCriterio] = useState(pregunta.criterio_id ?? '')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const opciones = [...pregunta.opciones].sort((a, b) => a.orden - b.orden)
  const criterioNombre = ctx.criterios.find((c) => c.id === pregunta.criterio_id)?.descripcion

  return (
    <div className="question-edit">
      <div className="editor-head">
        <div>
          <span className="editor-order">Decisión {pregunta.orden}</span>
          <p className="question-text">{pregunta.enunciado}</p>
          <p className="small muted">{criterioNombre ? `Criterio: ${criterioNombre}` : 'Sin criterio asignado'}</p>
        </div>
        <div className="btn-row">
          <Button size="sm" variant="quiet" icon="arrowUp" onClick={() => onMove(-1)} disabled={!canUp || ctx.pending} aria-label="Subir decisión">
            {''}
          </Button>
          <Button size="sm" variant="quiet" icon="arrowDown" onClick={() => onMove(1)} disabled={!canDown || ctx.pending} aria-label="Bajar decisión">
            {''}
          </Button>
          <Button size="sm" variant="quiet" icon="edit" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Cerrar' : 'Editar'}
          </Button>
          <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmDelete(true)} aria-label="Eliminar decisión">
            {''}
          </Button>
        </div>
      </div>
      {editing && (
        <form
          className="editor-form"
          onSubmit={(e) => {
            e.preventDefault()
            ctx.run((cid) => caseService.updateQuestion(cid, pregunta.id, { enunciado: enunciado.trim(), criterio_id: criterio || null }))
            setEditing(false)
          }}
        >
          <TextAreaField label="Enunciado" value={enunciado} onChange={(e) => setEnunciado(e.target.value)} rows={2} required />
          <CriterionSelect value={criterio} onChange={setCriterio} criterios={ctx.criterios} />
          <div>
            <Button type="submit" variant="primary" disabled={!enunciado.trim() || ctx.pending}>
              Guardar decisión
            </Button>
          </div>
        </form>
      )}
      <ol className="option-edit-list">
        {opciones.map((o, i) => (
          <OptionRow key={o.id} opcion={o} letter={optionLetter(i)} preguntaId={pregunta.id} ctx={ctx} />
        ))}
      </ol>
      <AddOptionForm preguntaId={pregunta.id} ctx={ctx} />
      <ConfirmDialog
        open={confirmDelete}
        title="¿Eliminar esta decisión?"
        confirmLabel="Eliminar"
        danger
        onConfirm={() => {
          ctx.run((cid) => caseService.removeQuestion(cid, pregunta.id))
          setConfirmDelete(false)
        }}
        onClose={() => setConfirmDelete(false)}
      >
        <p>Se eliminarán sus {pregunta.opciones.length} opciones.</p>
      </ConfirmDialog>
    </div>
  )
}

function OptionRow({ opcion, letter, preguntaId, ctx }: { opcion: OpcionRead; letter: string; preguntaId: UUID; ctx: EditorCtx }) {
  const [editing, setEditing] = useState(false)
  const [texto, setTexto] = useState(opcion.texto)
  const [correcta, setCorrecta] = useState(opcion.es_correcta)
  const [justificacion, setJustificacion] = useState(opcion.justificacion ?? '')
  return (
    <li className={opcion.es_correcta ? 'option-correct' : undefined}>
      <span className="option-letter" aria-hidden="true">
        {letter}
      </span>
      {editing ? (
        <form
          className="editor-form"
          onSubmit={(e) => {
            e.preventDefault()
            ctx.run((cid) => caseService.updateOption(cid, preguntaId, opcion.id, { texto: texto.trim(), es_correcta: correcta, justificacion: justificacion.trim() || null }))
            setEditing(false)
          }}
        >
          <TextAreaField label={`Texto de la opción ${letter}`} value={texto} onChange={(e) => setTexto(e.target.value)} rows={2} required />
          <CheckboxField label="Es una respuesta correcta" checked={correcta} onChange={(e) => setCorrecta(e.target.checked)} />
          <TextAreaField label="Justificación" value={justificacion} onChange={(e) => setJustificacion(e.target.value)} rows={2} hint="El estudiante la verá en su retroalimentación." />
          <div className="btn-row">
            <Button type="submit" size="sm" variant="primary" disabled={!texto.trim() || ctx.pending}>
              Guardar opción
            </Button>
            <Button size="sm" variant="quiet" onClick={() => setEditing(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      ) : (
        <div className="option-view">
          <span>
            {opcion.texto}
            {opcion.es_correcta && <strong className="correct-mark"> (correcta)</strong>}
            {opcion.justificacion ? <span className="muted"> {opcion.justificacion}</span> : <span className="tag tag-warn">Sin justificación</span>}
          </span>
          <span className="btn-row">
            <Button size="sm" variant="quiet" icon="edit" onClick={() => setEditing(true)} aria-label={`Editar opción ${letter}`}>
              {''}
            </Button>
            <Button size="sm" variant="quiet" icon="trash" onClick={() => ctx.run((cid) => caseService.removeOption(cid, preguntaId, opcion.id))} disabled={ctx.pending} aria-label={`Eliminar opción ${letter}`}>
              {''}
            </Button>
          </span>
        </div>
      )}
    </li>
  )
}

function AddOptionForm({ preguntaId, ctx }: { preguntaId: UUID; ctx: EditorCtx }) {
  const [texto, setTexto] = useState('')
  const [correcta, setCorrecta] = useState(false)
  const [justificacion, setJustificacion] = useState('')
  const [open, setOpen] = useState(false)
  if (!open)
    return (
      <Button size="sm" variant="quiet" icon="plus" onClick={() => setOpen(true)}>
        Añadir opción
      </Button>
    )
  return (
    <form
      className="editor-form"
      onSubmit={(e) => {
        e.preventDefault()
        if (!texto.trim()) return
        ctx.run((cid) => caseService.addOption(cid, preguntaId, { texto: texto.trim(), es_correcta: correcta, justificacion: justificacion.trim() || null }))
        setTexto('')
        setCorrecta(false)
        setJustificacion('')
        setOpen(false)
      }}
    >
      <TextAreaField label="Texto de la opción" value={texto} onChange={(e) => setTexto(e.target.value)} rows={2} required />
      <CheckboxField label="Es una respuesta correcta" checked={correcta} onChange={(e) => setCorrecta(e.target.checked)} />
      <TextAreaField label="Justificación" value={justificacion} onChange={(e) => setJustificacion(e.target.value)} rows={2} />
      <div className="btn-row">
        <Button type="submit" size="sm" variant="primary" disabled={!texto.trim() || ctx.pending}>
          Añadir opción
        </Button>
        <Button size="sm" variant="quiet" onClick={() => setOpen(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}
