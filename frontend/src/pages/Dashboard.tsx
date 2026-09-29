/**
 * Dashboard — repository analysis overview.
 * Phase 2: real repository analysis via POST /analyze
 */
import { useEffect, useState } from 'react'
import { analyzeRepository, listRepositories } from '../api/client'
import type { Repository, RepositorySnapshot } from '../types'

const SNAPSHOT_KEY = 'devforge_last_analysis_snapshot'
const REPOSITORY_KEY = 'devforge_last_analysis_repository'
const INPUT_KEY = 'devforge_last_analysis_input'

function MetricCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [repoPath, setRepoPath] = useState(() => localStorage.getItem(INPUT_KEY) ?? '')
  const [snapshot, setSnapshot] = useState<RepositorySnapshot | null>(() => {
    try {
      const value = localStorage.getItem(SNAPSHOT_KEY)
      return value ? JSON.parse(value) as RepositorySnapshot : null
    } catch { return null }
  })
  const [repository, setRepository] = useState<Repository | null>(() => {
    try {
      const value = localStorage.getItem(REPOSITORY_KEY)
      return value ? JSON.parse(value) as Repository : null
    } catch { return null }
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (repoPath) localStorage.setItem(INPUT_KEY, repoPath)
  }, [repoPath])

  async function handleAnalyze() {
    const input = repoPath.trim()
    if (!input) return
    setLoading(true)
    setError(null)
    try {
      const result = await analyzeRepository(input)
      const repos = await listRepositories()
      const matchedRepository = repos.find(repo => repo.id === result.repository_id) ?? null
      setSnapshot(result)
      setRepository(matchedRepository)
      localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(result))
      if (matchedRepository) localStorage.setItem(REPOSITORY_KEY, JSON.stringify(matchedRepository))
      localStorage.setItem(INPUT_KEY, input)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-2">Dashboard</h1>
      <p className="text-sm text-gray-500 mb-6">
        Analyze a local Python repository path or a public GitHub repository URL to detect issues and generate missions.
      </p>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 mb-6 shadow-sm">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Repository Path or GitHub URL
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            className="flex-1 border border-slate-300 rounded-xl bg-white px-4 py-3 text-sm font-medium text-slate-900 placeholder:text-slate-400 shadow-sm focus:outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            placeholder="/path/to/repo or https://github.com/owner/repo"
            value={repoPath}
            onChange={e => setRepoPath(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
            disabled={loading}
          />
          <button
            onClick={handleAnalyze}
            disabled={loading || !repoPath.trim()}
            className="rounded-xl bg-cyan-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-cyan-600/20 transition hover:-translate-y-0.5 hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {snapshot && (
        <div>
          <h2 className="text-lg font-medium text-gray-900 mb-4">Analysis Results</h2>
          {repository && <div className="mb-4">
            <h3 className="text-base font-semibold text-gray-900">{repository.name}</h3>
            {repository.source_url && <p className="text-xs text-gray-500">GitHub · {new URL(repository.source_url).pathname.replace(/^\//, '')}</p>}
          </div>}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 mb-6">
            <MetricCard label="Total Files" value={snapshot.file_count} />
            <MetricCard label="Test Files" value={snapshot.test_file_count} sub={`${snapshot.test_function_count} test functions`} />
            <MetricCard label="Lint Errors" value={snapshot.lint_error_count} />
            <MetricCard label="TODO / FIXME" value={snapshot.todo_count} />
            <MetricCard label="Doc Coverage" value={`${snapshot.documented_functions_pct.toFixed(1)}%`} />
            <MetricCard label="Languages" value={Object.keys(snapshot.languages).join(', ') || '—'} />
          </div>

          {snapshot.top_issues.length > 0 && (
            <div className="bg-white border border-gray-200 rounded p-4 mb-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Top Issues</h3>
              <ul className="space-y-1">
                {snapshot.top_issues.map((issue, i) => (
                  <li key={i} className="text-sm text-gray-600 flex gap-2"><span className="text-gray-400">•</span>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {snapshot.analysis_summary && (
            <div className="bg-white border border-gray-200 rounded p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Summary</h3>
              <p className="text-sm text-gray-600">{snapshot.analysis_summary}</p>
            </div>
          )}

          <p className="mt-4 text-xs text-gray-400">Repository ID: {snapshot.repository_id} · Snapshot: {snapshot.id}</p>
        </div>
      )}

      {!snapshot && !loading && !error && (
        <div className="rounded border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">
          Enter a repository path or public GitHub URL above to begin analysis.
        </div>
      )}
    </div>
  )
}
