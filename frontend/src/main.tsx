import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App'
import RouteError from './components/RouteError'

import PartDetailPage from './pages/PartDetailPage'
import PartsPage from './pages/PartsPage'
import BomPage from './pages/BomPage'
import ApiTokensPage from './pages/ApiTokensPage'
import AdminAddinPage from './pages/AdminAddinPage'
import AdminFieldsPage from './pages/AdminFieldsPage'
import DashboardPage from './pages/DashboardPage'
import UploadPackPage from './pages/UploadPackPage'
import NotFoundPage from './pages/NotFoundPage'

// PrimeReact CSS
import 'primereact/resources/themes/lara-light-blue/theme.css'
import 'primereact/resources/primereact.min.css'
import 'primeicons/primeicons.css'

// Define routes once and USE RouterProvider (no BrowserRouter here)
const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,           // layout shell
    // Catches render errors in EVERY page below. Without it a thrown error
    // unmounts the tree and leaves a blank document with no message.
    errorElement: <RouteError />,
    children: [
      { path: '/ui/dashboard', element: <DashboardPage /> },
      { path: '/ui/parts', element: <PartsPage /> },
      { path: '/ui/bom', element: <BomPage /> },
      { path: '/ui/bom/:pn', element: <BomPage /> },
      { path: '/ui/part/:pn', element: <PartDetailPage /> },
      { path: '/share/part/:shareId/:token', element: <PartDetailPage /> },
      { path: '/ui/addin/tokens', element: <ApiTokensPage /> },
      { path: '/ui/admin/addin', element: <AdminAddinPage /> },
      { path: '/ui/admin/fields', element: <AdminFieldsPage /> },
      { path: '/ui/upload-pack', element: <UploadPackPage /> },
      // A real 404. Rendering PartsPage here made a dead link look like a
      // successful navigation, so broken links were never reported.
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
