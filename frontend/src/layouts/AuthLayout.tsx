import { Outlet } from 'react-router'
import { ReflectionMotif } from '../components/design-system/ReflectionMotif'
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
          <p className="eyebrow">Un espacio para comprender</p>
          <h1>Decidir con criterio.<br />Aprender con sentido.</h1>
          <p>Cada caso es una situación que se recorre escena a escena. Lo que importa es cómo razonas cada decisión.</p>
        </div>
        <div className="login-scene" aria-hidden="true">
          <ReflectionMotif />
        </div>
        <p className="login-caption">Psicología social <span aria-hidden="true">/</span> Experiencias de aprendizaje</p>
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
