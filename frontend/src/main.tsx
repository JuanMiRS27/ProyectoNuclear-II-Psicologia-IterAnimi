import './styles/fonts.css'
import './styles/tokens.css'
import './styles/app.css'
import './styles/serene.css'
import './styles/theme.css'
import './styles/library.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AppRouter } from './app/router'
import { AppProviders } from './providers/AppProviders'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <AppRouter />
    </AppProviders>
  </StrictMode>,
)
