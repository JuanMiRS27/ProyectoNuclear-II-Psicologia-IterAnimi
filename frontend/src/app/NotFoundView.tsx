import { Page } from '../components/design-system/layout'
import { EmptyState } from '../components/design-system/states'
import { ButtonLink } from '../components/ui/Button'

export function NotFoundView() {
  return (
    <Page width="narrow">
      <EmptyState
        icon="search"
        title="Esta página no existe"
        action={
          <ButtonLink to="/" icon="home">
            Ir al inicio
          </ButtonLink>
        }
      >
        Revisa la dirección o vuelve a tu inicio.
      </EmptyState>
    </Page>
  )
}
