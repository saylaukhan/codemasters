import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import { applyDocumentLanguage } from './lib/locale'
import './styles/tokens.css'

// index.html ships with lang="ru"; the document follows the chosen language (DESIGN.md §9.4).
applyDocumentLanguage()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
