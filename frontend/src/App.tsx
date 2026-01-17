import { NavLink, Outlet } from 'react-router-dom'
import './App.css'

export default function App() {
  return (
    <div>
      <nav className="navbar navbar-expand-sm navbar-light bg-white border-bottom">
        <div className="container">
          <div className="navbar-nav gap-2">
            <NavLink to="/ui/dashboard" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Dashboard</NavLink>
            <NavLink to="/ui/parts" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Parts</NavLink>
            <NavLink to="/ui/bom" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>BOM</NavLink>
            <NavLink to="/ui/admin/addin" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Addin Admin</NavLink>
            <NavLink to="/ui/addin/tokens" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Tokens</NavLink>
          </div>
        </div>
      </nav>
      <main className="container py-3">
        <Outlet />
      </main>
    </div>
  )
}
