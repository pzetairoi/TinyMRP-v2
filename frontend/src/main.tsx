import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App'

import PartDetailPage from './pages/PartDetailPage'
import PartsPage from './pages/PartsPage'
import BomPage from './pages/BomPage'
import ApiTokensPage from './pages/ApiTokensPage'
import AdminAddinPage from './pages/AdminAddinPage'
import AdminFieldsPage from './pages/AdminFieldsPage'
import DashboardPage from './pages/DashboardPage'
import UploadPackPage from './pages/UploadPackPage'

// PrimeReact CSS
import 'primereact/resources/themes/lara-light-blue/theme.css'
import 'primereact/resources/primereact.min.css'
import 'primeicons/primeicons.css'

// Define routes once and USE RouterProvider (no BrowserRouter here)
const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,           // layout shell
    children: [
      { path: '/ui/dashboard', element: <DashboardPage /> },
      { path: '/ui/parts', element: <PartsPage /> },
      { path: '/ui/bom', element: <BomPage /> },
      { path: '/ui/bom/:pn', element: <BomPage /> },
      { path: '/ui/part/:pn', element: <PartDetailPage /> },
      { path: '/ui/addin/tokens', element: <ApiTokensPage /> },
      { path: '/ui/admin/addin', element: <AdminAddinPage /> },
      { path: '/ui/admin/fields', element: <AdminFieldsPage /> },
      { path: '/ui/upload-pack', element: <UploadPackPage /> },
      // fallback: send unknown paths to Parts
      { path: '*', element: <PartsPage /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
