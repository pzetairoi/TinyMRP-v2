import { Outlet, Link } from 'react-router-dom'

export default function App() {
  return (
    <div>
      <nav className="p-2 border-bottom">
        <a className="me-3" href="/app">Home</a>
        <Link className="me-3" to="/ui/parts">Parts</Link>
      </nav>
      <div className="container py-3">
        <Outlet />
      </div>
    </div>
  )
}
