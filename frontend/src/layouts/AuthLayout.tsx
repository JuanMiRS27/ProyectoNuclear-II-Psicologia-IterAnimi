import { Outlet } from 'react-router'
import { SceneCharacter } from '../modules/simulator/SceneCharacter'
import { ThemeSwitcher } from '../components/ui/ThemeSwitcher'
import { BrandMark } from './BrandMark'

/** Acceso público (equivalente a (auth) de Ágora): presentación a la izquierda, formulario a la derecha. */
export function AuthLayout() {
  return (
    <div className="login">
      <section className="login-intro" aria-label="Presentación">
        <span className="brand brand-light">
          <BrandMark size={28} />
          <span>Iter Animi</span>
        </span>
        <div className="login-copy">
          <h1>Casos de psicología social para decidir y reflexionar</h1>
          <p>Cada caso es una situación que se recorre escena a escena. Lo que importa es cómo razonas cada decisión.</p>
        </div>
        <div className="login-scene" aria-hidden="true">
          <SceneCharacter className="login-figure" decorative />
        </div>
      </section>
      <main className="login-main" id="contenido">
        <div className="login-theme">
          <ThemeSwitcher compact />
        </div>
        <Outlet />
      </main>
    </div>
  )
}
