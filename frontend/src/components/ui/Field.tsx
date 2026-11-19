import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'

interface FieldShellProps {
  label: string
  hint?: ReactNode
  error?: string | null
  hideLabel?: boolean
}

function describedBy(id: string, hint?: ReactNode, error?: string | null) {
  return [error ? `${id}-error` : '', hint ? `${id}-hint` : ''].filter(Boolean).join(' ') || undefined
}

function Shell({ id, label, hint, error, hideLabel, children }: FieldShellProps & { id: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id} className={hideLabel ? 'visually-hidden' : undefined}>
        {label}
      </label>
      {children}
      {hint && !error && (
        <span className="hint" id={`${id}-hint`}>
          {hint}
        </span>
      )}
      {error && (
        <span className="field-error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </div>
  )
}

export function TextField({ label, hint, error, hideLabel, id, ...rest }: FieldShellProps & InputHTMLAttributes<HTMLInputElement>) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <Shell id={fid} label={label} hint={hint} error={error} hideLabel={hideLabel}>
      <input id={fid} aria-invalid={error ? true : undefined} aria-describedby={describedBy(fid, hint, error)} {...rest} />
    </Shell>
  )
}

export function TextAreaField({ label, hint, error, hideLabel, id, ...rest }: FieldShellProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <Shell id={fid} label={label} hint={hint} error={error} hideLabel={hideLabel}>
      <textarea id={fid} aria-invalid={error ? true : undefined} aria-describedby={describedBy(fid, hint, error)} {...rest} />
    </Shell>
  )
}

export function SelectField({
  label,
  hint,
  error,
  hideLabel,
  id,
  children,
  ...rest
}: FieldShellProps & SelectHTMLAttributes<HTMLSelectElement> & { children: ReactNode }) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <Shell id={fid} label={label} hint={hint} error={error} hideLabel={hideLabel}>
      <select id={fid} aria-invalid={error ? true : undefined} aria-describedby={describedBy(fid, hint, error)} {...rest}>
        {children}
      </select>
    </Shell>
  )
}

export function CheckboxField({ label, id, ...rest }: { label: string } & InputHTMLAttributes<HTMLInputElement>) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <label className="check" htmlFor={fid}>
      <input id={fid} type="checkbox" {...rest} />
      {label}
    </label>
  )
}

/** Búsqueda de texto para listados (filtra en el cliente sobre datos ya cargados). */
export function SearchField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  const id = useId()
  return (
    <div className="search-field">
      <label htmlFor={id} className="visually-hidden">
        {label}
      </label>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
        <path d="M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4" strokeLinecap="round" />
      </svg>
      <input id={id} type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  )
}
