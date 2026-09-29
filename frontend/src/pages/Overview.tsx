import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listExecutions, listRepositories } from '../api/client'
import type { Repository } from '../types'

type ExecutionSummary = { id: string; mission_title: string; status: string; started_at: string }

export default function Overview() {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [executions, setExecutions] = useState<ExecutionSummary[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    Promise.all([listRepositories(), listExecutions()])
      .then(([repos, runs]) => { setRepositories(repos); setExecutions(runs) })
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load workspace'))
  }, [])
  return <section>
    <p className="text-xs font-semibold uppercase tracking-wider text-cyan-800">Workspace</p>
    <h1 className="mt-1 text-3xl font-semibold text-slate-950">Engineering overview</h1>
    <p className="mt-2 max-w-2xl text-slate-600">Analyze a Python repository, review its missions, then inspect the execution and evidence produced by real checks.</p>
    {error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}
    <div className="mt-7 grid gap-4 md:grid-cols-2">
      <article className="rounded-lg border border-slate-200 bg-white p-5"><h2 className="font-semibold">Repositories</h2><p className="mt-1 text-sm text-slate-500">{repositories.length} analyzed or registered</p><Link to="/analyze" className="mt-4 inline-block text-sm font-medium text-cyan-800">Analyze a repository →</Link></article>
      <article className="rounded-lg border border-slate-200 bg-white p-5"><h2 className="font-semibold">Recent executions</h2><p className="mt-1 text-sm text-slate-500">{executions.length} execution{executions.length === 1 ? '' : 's'} recorded</p><Link to="/executions" className="mt-4 inline-block text-sm font-medium text-cyan-800">View executions →</Link></article>
    </div>
    <div className="mt-7 rounded-lg border border-slate-200 bg-white p-5"><h2 className="font-semibold">Repositories</h2>{repositories.length ? <ul className="mt-3 divide-y">{repositories.map(repo => <li key={repo.id} className="flex justify-between py-3 text-sm"><span><span className="font-medium">{repo.name}</span>{repo.source_url && <span className="ml-2 text-xs text-slate-500">GitHub · {new URL(repo.source_url).pathname.replace(/^\//, '')}</span>}</span><span className="text-slate-500">{repo.status}</span></li>)}</ul> : <p className="mt-2 text-sm text-slate-500">No repositories yet. Start with Analyze.</p>}</div>
  </section>
}
