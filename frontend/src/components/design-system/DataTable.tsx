// Tabla legible y accesible. En móvil cada fila se apila como bloque con etiquetas (data-label).
import type { ReactNode } from 'react'

export interface Column<T> {
  key: string
  header: string
  cell: (row: T) => ReactNode
  numeric?: boolean
  /** Oculta el encabezado visualmente (p. ej. columna de acciones). */
  srOnlyHeader?: boolean
}

export function DataTable<T>({ caption, columns, rows, rowKey, empty }: { caption: string; columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string; empty?: ReactNode }) {
  if (rows.length === 0 && empty) return <>{empty}</>
  return (
    <div className="table-wrap">
      <table className="table table-stack">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? 'num' : undefined}>
                {c.srOnlyHeader ? <span className="visually-hidden">{c.header}</span> : c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? 'num' : undefined} data-label={c.srOnlyHeader ? undefined : c.header}>
                  <div className="table-cell-content">{c.cell(r)}</div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
