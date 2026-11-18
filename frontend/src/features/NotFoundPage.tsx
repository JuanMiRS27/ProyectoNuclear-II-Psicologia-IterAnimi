import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <main className="page page-narrow" id="contenido">
      <div className="state">
        <h1>Esta página no existe</h1>
        <p>Revisa la dirección o vuelve al inicio.</p>
        <Link className="btn" to="/">
          Ir al inicio
        </Link>
      </div>
    </main>
  )
}
