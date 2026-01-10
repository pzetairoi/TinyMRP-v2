import { Outlet } from 'react-router-dom'
import './App.css'

export default function App() {
  return (
    <div className="container py-3">
      <Outlet />
    </div>
  )
}
