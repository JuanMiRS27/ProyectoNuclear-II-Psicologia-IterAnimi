import { useEffect, useId, useRef, type ReactNode } from 'react'

/** Diálogo modal nativo (<dialog>): foco atrapado, Escape y retorno del foco los gestiona el navegador. */
export function Dialog({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby={titleId}
      onClose={onClose}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
    >
      {open && (
        <div className="dialog-body">
          <h2 id={titleId}>{title}</h2>
          {children}
        </div>
      )}
    </dialog>
  )
}

/** Confirmación de una acción con consecuencias. */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  danger,
  pending,
  error,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  children: ReactNode
  confirmLabel: string
  danger?: boolean
  pending?: boolean
  error?: ReactNode
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Dialog open={open} title={title} onClose={onClose}>
      <div className="small" style={{ display: 'grid', gap: '0.6rem' }}>
        {children}
      </div>
      {error}
      <div className="dialog-actions">
        <button type="button" className="btn" onClick={onClose} disabled={pending}>
          Cancelar
        </button>
        <button
          type="button"
          className={`btn ${danger ? 'btn-danger-solid' : 'btn-primary'}`}
          onClick={onConfirm}
          disabled={pending}
          aria-busy={pending}
        >
          {pending ? 'Procesando…' : confirmLabel}
        </button>
      </div>
    </Dialog>
  )
}
