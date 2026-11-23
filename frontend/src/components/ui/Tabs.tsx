import { Link } from 'react-router'

/** Pestañas enlazadas a la URL (?tab=…): sobreviven al refresco y se pueden compartir. */
export function LinkTabs<T extends string>({ label, tabs, current, param = 'tab' }: { label: string; tabs: { id: T; label: string; count?: number }[]; current: T; param?: string }) {
  return (
    <nav className="tabs" aria-label={label}>
      {tabs.map((t) => (
        <Link key={t.id} to={`?${param}=${t.id}`} replace aria-current={current === t.id ? 'page' : undefined}>
          {t.label}
          {t.count !== undefined && <span className="tab-count">{t.count}</span>}
        </Link>
      ))}
    </nav>
  )
}
