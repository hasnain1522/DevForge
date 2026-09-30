import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import Dashboard from './pages/Dashboard'
import MissionBoard from './pages/MissionBoard'
import ExecutionView from './pages/ExecutionView'
import ImpactReport from './pages/ImpactReport'
import Landing from './pages/Landing'
import AuthPage from './pages/AuthPage'
import Overview from './pages/Overview'
import { useEffect } from 'react'
import { useState } from 'react'
import { listEvidence, listExecutions } from './api/client'
import type { EvidenceRecord } from './types'

function Protected() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="p-10 text-slate-500">Loading DevForge…</div>
  return user ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} />
}

function NavBar() {
  const { user, logout } = useAuth()
  return (
    <header className="border-b border-slate-800 bg-slate-950 text-slate-100">
      <nav className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-4">
        <Link to="/overview" className="mr-auto flex items-center gap-2 font-semibold"><span className="text-cyan-400">◆</span> DevForge</Link>
        <Link to="/overview" className="text-sm text-slate-300 hover:text-white">Overview</Link>
        <Link to="/analyze" className="text-sm text-slate-300 hover:text-white">Analyze</Link>
        <Link to="/missions" className="text-sm text-slate-300 hover:text-white">Missions</Link>
        <Link to="/executions" className="text-sm text-slate-300 hover:text-white">Executions</Link>
        <Link to="/evidence" className="text-sm text-slate-300 hover:text-white">Evidence</Link>
        <Link to="/impact" className="text-sm text-slate-300 hover:text-white">Reports</Link>
        <span className="hidden text-xs text-slate-400 md:block">{user?.email}</span>
        <button onClick={() => void logout()} className="text-sm text-cyan-300 hover:text-white">Log out</button>
      </nav>
    </header>
  )
}

function Workspace() {
  return <><NavBar /><main className="mx-auto max-w-7xl px-6 py-8"><Outlet /></main></>
}

function AuthRoutes() {
  const { user } = useAuth()
  return <Routes>
    <Route path="/" element={<Landing />} />
    <Route path="/login" element={user ? <Navigate to="/overview" replace /> : <AuthPage mode="login" />} />
    <Route path="/register" element={user ? <Navigate to="/overview" replace /> : <AuthPage mode="register" />} />
    <Route element={<Protected />}><Route element={<Workspace />}>
      <Route path="/workspace" element={<Navigate to="/overview" replace />} />
      <Route path="/overview" element={<Overview />} />
      <Route path="/analyze" element={<Dashboard />} />
      <Route path="/missions" element={<MissionBoard />} />
      <Route path="/execution/:runId" element={<ExecutionView />} />
      <Route path="/executions" element={<ExecutionList />} />
      <Route path="/evidence" element={<EvidencePage />} />
      <Route path="/impact" element={<ImpactReport />} />
    </Route></Route>
    <Route path="*" element={<Navigate to={user ? '/overview' : '/'} replace />} />
  </Routes>
}

function ExecutionList() {
  const [items, setItems] = useState<Array<{id:string;mission_title:string;status:string;started_at:string}>>([])
  const [error, setError] = useState('')
  useEffect(() => { listExecutions().then(setItems).catch(e => setError(String(e))) }, [])
  return <section><h1 className="mb-5 text-2xl font-semibold">Executions</h1>{error && <p>{error}</p>}{items.length ? <div className="space-y-3">{items.map(item => <Link key={item.id} to={`/execution/${item.id}`} className="block rounded-lg border border-slate-200 bg-white p-4"><div className="flex justify-between"><strong>{item.mission_title}</strong><span>{item.status}</span></div><small>{new Date(item.started_at).toLocaleString()}</small></Link>)}</div> : <p className="text-slate-500">Executions will appear here after a mission starts.</p>}</section>
}

function EvidencePage() {
  const [items, setItems] = useState<EvidenceRecord[]>([])
  const [error, setError] = useState('')
  useEffect(() => { listEvidence().then(setItems).catch(e => setError(String(e))) }, [])
  return <section>
    <h1 className="mb-2 text-2xl font-semibold">Evidence</h1>
    <p className="mb-5 text-sm text-slate-500">Records generated from repository analysis and mission execution.</p>
    {error && <p className="text-red-600">{error}</p>}
    {items.length ? <div className="space-y-3">{items.map(item => (
      <article key={item.id} className="rounded-lg border border-slate-200 bg-white p-4 text-slate-900 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <strong className="text-sm font-semibold text-slate-900">{item.title}</strong>
          <span className="text-xs font-semibold text-cyan-700">{item.type}</span>
        </div>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{item.description || 'No description recorded.'}</p>
        <time className="mt-2 block text-xs text-slate-400">{new Date(item.timestamp).toLocaleString()}</time>
        {Object.keys(item.payload).length > 0 && (
          <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-3 text-xs text-slate-100">{JSON.stringify(item.payload, null, 2)}</pre>
        )}
      </article>
    ))}</div> : !error && <p className="rounded border border-dashed p-8 text-center text-slate-500">No evidence yet. Analyze a repository or execute a mission.</p>}
  </section>
}

export default function App() {
  return (
    <AuthProvider><BrowserRouter><div className="min-h-screen bg-slate-50"><AuthRoutes /></div></BrowserRouter></AuthProvider>
  )
}
