// Contenedores y cabeceras de página (equivalentes a page-container y section-header de Ágora).
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Icon, type IconName } from '../ui/Icon'
import { ReflectionMotif } from './ReflectionMotif'

export function Page({ children, width = 'wide', className = '' }: { children: ReactNode; width?: 'wide' | 'narrow' | 'reading'; className?: string }) {
  return (
    <main className={`page page-${width} ${className}`} id="contenido" tabIndex={-1}>
      {children}
    </main>
  )
}

/** Cabecera de inicio por rol; el motivo decorativo nunca sustituye información académica. */
export function DashboardIntro({ eyebrow, title, description, actions }: { eyebrow: string; title: ReactNode; description: ReactNode; actions?: ReactNode }) {
  return (
    <header className="dashboard-intro">
      <div className="dashboard-intro-copy">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="lede">{description}</p>
        {actions && <div className="btn-row">{actions}</div>}
      </div>
      <ReflectionMotif />
    </header>
  )
}

export function PageHeader({
  title,
  description,
  crumbs,
  actions,
  meta,
}: {
  title: ReactNode
  description?: ReactNode
  crumbs?: { label: string; to: string }[]
  actions?: ReactNode
  meta?: ReactNode
}) {
  return (
    <header className="page-head">
      <div className="page-head-text">
        {crumbs && crumbs.length > 0 && (
          <nav className="crumbs" aria-label="Ruta de navegación">
            {crumbs.map((c, i) => (
              <span key={c.to}>
                {i > 0 && <Icon name="chevronRight" size={14} />}
                <Link to={c.to}>{c.label}</Link>
              </span>
            ))}
          </nav>
        )}
        <h1>{title}</h1>
        {meta && <div className="row-meta page-meta">{meta}</div>}
        {description && <p className="lede">{description}</p>}
      </div>
      {actions && <div className="btn-row page-actions">{actions}</div>}
    </header>
  )
}

export function Section({ title, description, actions, children, id }: { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode; id?: string }) {
  const hid = id ?? `s-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <section className="section" aria-labelledby={hid}>
      <div className="section-head">
        <div>
          <h2 id={hid}>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {actions && <div className="btn-row">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

export function Panel({ children, tone = 'plain', className }: { children: ReactNode; tone?: 'plain' | 'mist' | 'ink'; className?: string }) {
  return <div className={`panel panel-${tone}${className ? ` ${className}` : ''}`}>{children}</div>
}

export function Notice({ tone = 'info', title, children, icon }: { tone?: 'info' | 'ok' | 'error' | 'warn'; title?: ReactNode; children?: ReactNode; icon?: IconName }) {
  const defaultIcon: Record<string, IconName> = { info: 'flag', ok: 'check', error: 'alert', warn: 'clock' }
  return (
    <div className={`notice notice-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon name={icon ?? defaultIcon[tone]!} size={18} />
      <div>
        {title && <strong>{title}</strong>}
        {children}
      </div>
    </div>
  )
}

/** Cifras con etiqueta, en línea (no tarjetas idénticas). */
export function Figures({ items }: { items: { label: string; value: ReactNode; hint?: string; icon?: IconName }[] }) {
  return (
    <dl className="figures">
      {items.map((it) => (
        <div key={it.label}>
          <dt>
            {it.icon && <span className="figure-icon"><Icon name={it.icon} size={17} /></span>}
            {it.label}
            {it.hint && <span className="small"> {it.hint}</span>}
          </dt>
          <dd>{it.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Definitions({ items }: { items: { term: string; value: ReactNode }[] }) {
  return (
    <dl className="defs">
      {items.map((it) => (
        <div key={it.term} className="defs-row">
          <dt>{it.term}</dt>
          <dd>{it.value}</dd>
        </div>
      ))}
    </dl>
  )
}
