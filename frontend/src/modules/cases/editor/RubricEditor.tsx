import { useState, type FormEvent } from 'react'
import { Notice } from '../../../components/design-system/layout'
import { Button } from '../../../components/ui/Button'
import { ConfirmDialog } from '../../../components/ui/Dialog'
import { TextField } from '../../../components/ui/Field'
import { Icon } from '../../../components/ui/Icon'
import { formatDecimal } from '../../../lib/format'
import { caseService } from '../../../services/case-service'
import type { CriterioRead, NivelInput, RubricaRead } from '../../../types/api'
import type { RunOp } from './ScenarioEditor'

interface Ctx {
  run: RunOp
  pending: boolean
}

/** Rúbrica (CU8): escala, criterios con peso y niveles. La suma mostrada es orientativa; la valida el servidor al publicar. */
export function RubricEditor({ rubrica, ctx }: { rubrica: RubricaRead | null; ctx: Ctx }) {
  const [escala, setEscala] = useState(rubrica?.escala_max ?? '5.00')
  if (!rubrica)
    return (
      <form
        className="editor-form"
        onSubmit={(e) => {
          e.preventDefault()
          ctx.run((cid) => caseService.createRubric(cid, escala))
        }}
      >
        <p className="small muted">Este borrador no tiene rúbrica. Sin ella no se puede publicar.</p>
        <TextField label="Escala máxima de la nota" type="number" step="0.01" min="0.01" max="99.99" value={escala} onChange={(e) => setEscala(e.target.value)} />
        <div>
          <Button type="submit" variant="primary" icon="plus" disabled={ctx.pending}>
            Crear rúbrica
          </Button>
        </div>
      </form>
    )

  const suma = rubrica.criterios.reduce((n, c) => n + Number(c.peso), 0)
  return (
    <div className="editor-stack">
      <form
        className="editor-inline"
        onSubmit={(e) => {
          e.preventDefault()
          ctx.run((cid) => caseService.updateRubric(cid, escala))
        }}
      >
        <TextField label="Escala máxima" type="number" step="0.01" min="0.01" max="99.99" value={escala} onChange={(e) => setEscala(e.target.value)} />
        <Button type="submit" size="sm" disabled={ctx.pending || escala === rubrica.escala_max}>
          Guardar escala
        </Button>
      </form>
      <p className={`weight-sum${Math.abs(suma - 100) < 0.001 ? ' ok' : ''}`}>
        <Icon name={Math.abs(suma - 100) < 0.001 ? 'check' : 'alert'} size={16} />
        Suma de pesos: {formatDecimal(String(suma))} de 100
      </p>
      {rubrica.criterios.map((c) => (
        <CriterionBlock key={c.id} criterio={c} ctx={ctx} />
      ))}
      <AddCriterion ctx={ctx} />
    </div>
  )
}

function LevelsEditor({ niveles, onChange }: { niveles: NivelInput[]; onChange: (n: NivelInput[]) => void }) {
  const set = (i: number, patch: Partial<NivelInput>) => onChange(niveles.map((n, j) => (j === i ? { ...n, ...patch } : n)))
  return (
    <fieldset className="levels">
      <legend>Niveles</legend>
      <p className="small muted">Para usar niveles en la nota, indica en todos el porcentaje mínimo de aciertos; si falta alguno se califica de forma lineal.</p>
      {niveles.map((n, i) => (
        <div key={i} className="level-row">
          <TextField label="Nombre" value={n.nombre} onChange={(e) => set(i, { nombre: e.target.value })} />
          <TextField label="Valor" type="number" step="0.01" min="0" value={n.valor} onChange={(e) => set(i, { valor: e.target.value })} />
          <TextField label="Desde % aciertos" type="number" step="0.01" min="0" max="100" value={n.min_aciertos_pct ?? ''} onChange={(e) => set(i, { min_aciertos_pct: e.target.value === '' ? null : e.target.value })} />
          <Button size="sm" variant="quiet" icon="trash" onClick={() => onChange(niveles.filter((_, j) => j !== i))} aria-label={`Quitar nivel ${i + 1}`}>
            {''}
          </Button>
        </div>
      ))}
      <Button size="sm" variant="quiet" icon="plus" onClick={() => onChange([...niveles, { nombre: '', valor: '', min_aciertos_pct: null }])}>
        Añadir nivel
      </Button>
    </fieldset>
  )
}

function cleanLevels(niveles: NivelInput[]): NivelInput[] {
  return niveles
    .filter((n) => n.nombre.trim() && n.valor !== '')
    .map((n) => ({ nombre: n.nombre.trim(), valor: n.valor, ...(n.min_aciertos_pct ? { min_aciertos_pct: n.min_aciertos_pct } : {}) }))
}

function CriterionForm({ initial, submitLabel, onSubmit, onCancel, pending }: { initial: { descripcion: string; peso: string; niveles: NivelInput[] }; submitLabel: string; onSubmit: (d: { descripcion: string; peso: string; niveles: NivelInput[] }) => void; onCancel?: () => void; pending: boolean }) {
  const [descripcion, setDescripcion] = useState(initial.descripcion)
  const [peso, setPeso] = useState(initial.peso)
  const [niveles, setNiveles] = useState<NivelInput[]>(initial.niveles)
  const [err, setErr] = useState<string | null>(null)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const p = Number(peso)
    if (!descripcion.trim()) return setErr('Describe el criterio.')
    if (!(p > 0 && p <= 100)) return setErr('El peso debe ser mayor que 0 y como máximo 100.')
    setErr(null)
    onSubmit({ descripcion: descripcion.trim(), peso, niveles: cleanLevels(niveles) })
  }
  return (
    <form className="editor-form" onSubmit={submit} noValidate>
      <TextField label="Descripción del criterio" maxLength={255} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
      <TextField label="Peso (%)" type="number" step="0.01" min="0.01" max="100" value={peso} onChange={(e) => setPeso(e.target.value)} error={err} />
      <LevelsEditor niveles={niveles} onChange={setNiveles} />
      <div className="btn-row">
        <Button type="submit" variant="primary" size="sm" disabled={pending}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button size="sm" variant="quiet" onClick={onCancel}>
            Cancelar
          </Button>
        )}
      </div>
    </form>
  )
}

function CriterionBlock({ criterio, ctx }: { criterio: CriterioRead; ctx: Ctx }) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  return (
    <article className="editor-block">
      <header className="editor-head">
        <div>
          <h4>{criterio.descripcion}</h4>
          <p className="small muted">
            Peso {formatDecimal(criterio.peso)} %.{' '}
            {criterio.niveles.length
              ? criterio.niveles
                  .map((n) => `${n.nombre}: ${formatDecimal(n.valor)}${n.min_aciertos_pct != null ? ` (desde ${formatDecimal(n.min_aciertos_pct, 0)} %)` : ''}`)
                  .join('; ')
              : 'Sin niveles.'}
          </p>
        </div>
        <div className="btn-row">
          <Button size="sm" variant="quiet" icon="edit" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Cerrar' : 'Editar'}
          </Button>
          <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmDelete(true)}>
            Eliminar
          </Button>
        </div>
      </header>
      {editing && (
        <CriterionForm
          initial={{
            descripcion: criterio.descripcion,
            peso: criterio.peso,
            niveles: criterio.niveles.map((n) => ({ nombre: n.nombre, valor: n.valor, min_aciertos_pct: n.min_aciertos_pct ?? null })),
          }}
          submitLabel="Guardar criterio"
          pending={ctx.pending}
          onCancel={() => setEditing(false)}
          onSubmit={(d) => {
            ctx.run((cid) => caseService.updateCriterion(cid, criterio.id, d))
            setEditing(false)
          }}
        />
      )}
      <ConfirmDialog
        open={confirmDelete}
        title="¿Eliminar este criterio?"
        confirmLabel="Eliminar"
        danger
        onConfirm={() => {
          ctx.run((cid) => caseService.removeCriterion(cid, criterio.id))
          setConfirmDelete(false)
        }}
        onClose={() => setConfirmDelete(false)}
      >
        <p>Las decisiones asociadas quedarán sin criterio y tendrás que asignarles otro antes de publicar.</p>
      </ConfirmDialog>
    </article>
  )
}

function AddCriterion({ ctx }: { ctx: Ctx }) {
  const [open, setOpen] = useState(false)
  if (!open)
    return (
      <div>
        <Button icon="plus" onClick={() => setOpen(true)}>
          Añadir criterio
        </Button>
      </div>
    )
  return (
    <>
      <Notice tone="info">Un criterio necesita al menos dos niveles para que el caso pueda publicarse.</Notice>
      <CriterionForm
        initial={{
          descripcion: '',
          peso: '',
          niveles: [
            { nombre: '', valor: '', min_aciertos_pct: null },
            { nombre: '', valor: '', min_aciertos_pct: null },
          ],
        }}
        submitLabel="Añadir criterio"
        pending={ctx.pending}
        onCancel={() => setOpen(false)}
        onSubmit={(d) => {
          ctx.run((cid) => caseService.addCriterion(cid, d))
          setOpen(false)
        }}
      />
    </>
  )
}
