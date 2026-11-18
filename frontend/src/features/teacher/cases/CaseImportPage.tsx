import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { casesApi } from '../../../api/endpoints'
import { InlineError } from '../../../components/states'

export function CaseImportPage() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const m = useMutation({
    mutationFn: (dsl: unknown) => casesApi.importDsl(dsl),
    onSuccess: (c) => navigate(`/casos/${c.id}?importado=1`, { replace: true }),
  })

  const onFile = async (file: File | undefined) => {
    if (!file) return
    setText(await file.text())
    setParseError(null)
  }

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
    m.mutate(dsl)
  }

  return (
    <main className="page page-narrow" id="contenido">
      <div>
        <div className="crumbs">
          <Link to="/casos">Mis casos</Link>
        </div>
        <h1>Importar un caso</h1>
        <p className="lede muted" style={{ marginTop: '0.4rem' }}>
          Carga un documento CaseDSL 1.0 (JSON) con el caso, sus escenarios, preguntas, opciones y rúbrica. Siempre se crea como borrador
          para que lo revises y lo publiques. También puedes partir de un caso exportado desde aquí.
        </p>
      </div>
      <form className="form-grid" onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="dsl-file">Archivo .json</label>
          <input id="dsl-file" type="file" accept="application/json,.json" onChange={(e) => onFile(e.target.files?.[0])} />
        </div>
        <div className="field">
          <label htmlFor="dsl">Contenido CaseDSL</label>
          <textarea
            id="dsl"
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            style={{ minHeight: '18rem', fontFamily: 'ui-monospace, Consolas, monospace', fontSize: '0.85rem' }}
            aria-invalid={parseError ? true : undefined}
            aria-describedby="dsl-hint"
          />
          <span className="hint" id="dsl-hint">
            Debe incluir <code>"dslVersion": "1.0"</code>.
          </span>
          {parseError && <span className="field-error">{parseError}</span>}
        </div>
        <InlineError error={m.error} />
        <div className="btn-row">
          <button type="submit" className="btn btn-primary" disabled={!text.trim() || m.isPending}>
            {m.isPending ? 'Importando…' : 'Crear borrador'}
          </button>
          <Link className="btn btn-quiet" to="/casos">
            Cancelar
          </Link>
        </div>
      </form>
    </main>
  )
}
