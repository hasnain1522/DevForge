import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listExecutions, listRepositories } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { Repository } from '../types'

type ExecutionSummary = { id: string; mission_title: string; status: string; started_at: string }

export default function Overview() {
  const { user } = useAuth()
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [executions, setExecutions] = useState<ExecutionSummary[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([listRepositories(), listExecutions()])
      .then(([repos, runs]) => { setRepositories(repos); setExecutions(runs) })
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load workspace'))
  }, [])

  return (
    <section className="devforge-reveal">
      <div className="rounded-3xl border border-cyan-300/10 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950/40 p-7 text-white shadow-xl sm:p-9">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">Command center</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Welcome back{user?.email ? ', ' + user.email.split('@')[0] : ''}.</h1>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">DevForge is ready. Analyze a repository, turn the evidence into engineering missions, and follow every change through verification.</p>
        <div className="mt-6 flex flex-wrap gap-3"><Link to="/analyze" className="rounded-xl bg-cyan-300 px-4 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-cyan-200">Analyze repository →</Link><Link to="/missions" className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition hover:bg-white/10">Open missions</Link></div>
      </div>
      {error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <article className="devforge-card rounded-2xl border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase tracking-wider text-cyan-800">Repositories</p><p className="mt-2 text-3xl font-semibold text-slate-950">{repositories.length}</p><p className="mt-1 text-sm text-slate-500">Analyzed or registered repositories</p><Link to="/analyze" className="mt-4 inline-block text-sm font-semibold text-cyan-800">Analyze a repository →</Link></article>
        <article className="devforge-card rounded-2xl border border-slate-200 bg-white p-5"><p className="text-xs font-semibold uppercase tracking-wider text-indigo-700">Executions</p><p className="mt-2 text-3xl font-semibold text-slate-950">{executions.length}</p><p className="mt-1 text-sm text-slate-500">Execution runs recorded in your workspace</p><Link to="/executions" className="mt-4 inline-block text-sm font-semibold text-cyan-800">View executions →</Link></article>
      </div>
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between gap-4"><div><h2 className="font-semibold text-slate-950">Your repositories</h2><p className="mt-1 text-sm text-slate-500">Workspace sources and their current status.</p></div><Link to="/analyze" className="text-sm font-semibold text-cyan-800">+ Analyze</Link></div>
        {repositories.length ? <ul className="mt-4 divide-y">{repositories.map(repo => <li key={repo.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><span><span className="font-medium text-slate-900">{repo.name}</span>{repo.source_url && <span className="ml-2 text-xs text-slate-500">GitHub · {new URL(repo.source_url).pathname.replace(/^\//, '')}</span>}</span><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500">{repo.status}</span></li>)}</ul> : <p className="mt-5 rounded-xl border border-dashed border-slate-200 p-7 text-center text-sm text-slate-500">No repositories yet. Start with Analyze.</p>}
      </div>
    </section>
  )
}
