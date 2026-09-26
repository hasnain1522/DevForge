import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import MissionBoard from './pages/MissionBoard'
import ExecutionView from './pages/ExecutionView'
import ImpactReport from './pages/ImpactReport'

function NavBar() {
  return (
    <nav className="border-b border-gray-200 bg-white px-6 py-3 flex items-center gap-6">
      <span className="font-semibold text-gray-900 mr-4">DevForge</span>
      <Link to="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
        Dashboard
      </Link>
      <Link to="/missions" className="text-sm text-gray-600 hover:text-gray-900">
        Missions
      </Link>
      <Link to="/execution" className="text-sm text-gray-600 hover:text-gray-900">
        Execution
      </Link>
      <Link to="/impact" className="text-sm text-gray-600 hover:text-gray-900">
        Impact Report
      </Link>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <NavBar />
        <main className="max-w-6xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/missions" element={<MissionBoard />} />
            <Route path="/execution" element={<ExecutionView />} />
            <Route path="/impact" element={<ImpactReport />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
