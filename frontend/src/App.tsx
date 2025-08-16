import { Routes, Route, Navigate } from 'react-router-dom'
import PartsPage from './pages/PartsPage'
import BomPage from './pages/BomPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/ui/parts" replace />} />
      <Route path="/ui/parts" element={<PartsPage />} />
      <Route path="/ui/bom/:pn" element={<BomPage />} />
    </Routes>
  )
}
