import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'

import PartDetailPage from "./pages/PartDetailPage"
import PartsPage from "./pages/PartsPage"
import BomPage from "./pages/BomPage"

// PrimeReact CSS
import 'primereact/resources/themes/lara-light-blue/theme.css'
import 'primereact/resources/primereact.min.css'
import 'primeicons/primeicons.css'

const router = createBrowserRouter([
  { path: "/ui/parts", element: <PartsPage /> },
  { path: "/ui/bom/:pn", element: <BomPage /> },
  { path: "/ui/part/:pn", element: <PartDetailPage /> },   // <-- add this
  // ...
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename="/">
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
