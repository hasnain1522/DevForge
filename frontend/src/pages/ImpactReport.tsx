import { useEffect, useState } from 'react'
import { downloadExecutionArtifact, getImpactReport, listArtifactFiles, listRepositories, openArtifactFile } from '../api/client'
import type { ImpactReport as Report, Repository } from '../types'

export default function ImpactReport() {
  const [repos, setRepos] = useState<Repository[]>([])
  const [repoId, setRepoId] = useState('')
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [artifactFiles, setArtifactFiles] = useState<Array<{ path: string; size_bytes: number }>>([])
  const [openedFile, setOpenedFile] = useState<{ path: string; content: string } | null>(null)
  const [artifactLoading, setArtifactLoading] = useState(false)
  useEffect(() => { listRepositories().then(setRepos).catch(e => setError(String(e))) }, [])
  async function load(id: string) {
    setRepoId(id); setReport(null); setError('')
    if (!id) return
    setLoading(true)
    try { setReport(await getImpactReport(id)) } catch (e) { setError(e instanceof Error ? e.message : 'No report available yet') }
    finally { setLoading(false) }
  }
  async function loadArtifactFiles() {
    if (!report?.execution.id) return
    setArtifactLoading(true)
    setError('')
    try {
      const result = await listArtifactFiles(report.execution.id)
      setArtifactFiles(result.files)
      const readme = result.files.find(file => /(^|\/)README\.md$/i.test(file.path))
      if (readme) setOpenedFile(await openArtifactFile(report.execution.id, readme.path))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open artifact files')
    } finally {
      setArtifactLoading(false)
    }
  }

  async function openArtifactFilePreview(path: string) {
    if (!report?.execution.id) return
    try {
      setOpenedFile(await openArtifactFile(report.execution.id, path))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open file')
    }
  }

  return <section>
    <h1 className="mb-2 text-2xl font-semibold">Impact reports</h1>
    <p className="mb-5 text-sm text-slate-500">Measured repository changes from completed missions.</p>
    <label className="mb-6 block max-w-xl text-sm font-medium">Repository
      <select className="mt-2 block w-full rounded border border-slate-300 bg-white px-3 py-2" value={repoId} onChange={e => void load(e.target.value)}>
        <option value="">Choose a repository</option>{repos.map(repo => <option key={repo.id} value={repo.id}>{repo.name}{repo.source_url ? ` · GitHub • ${new URL(repo.source_url).pathname.replace(/^\//, '')}` : ''}</option>)}
      </select>
    </label>
    {loading && <p className="text-slate-500">Loading report…</p>}
    {error && !loading && <p className="mb-4 rounded bg-amber-50 p-3 text-sm text-amber-800">{error.includes('404') ? 'No mission report is available for this repository yet.' : error}</p>}
    {report && <>
      <div className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-slate-500">Mission outcome</p><h2 className="text-lg font-semibold">{report.mission.title}</h2></div><span className={`rounded-full px-3 py-1 text-sm ${report.execution.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>{report.execution.status}</span></div>
        <p className="mt-2 text-sm text-slate-600">{report.mission.problem}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">{[
          { label: 'Tests', value: report.delta_tests_added },
          { label: 'Lint errors', value: report.delta_lint_errors },
          { label: 'TODO/FIXME', value: report.delta_todo_count },
          { label: 'Doc coverage', value: `${report.delta_doc_coverage_pct > 0 ? '+' : ''}${report.delta_doc_coverage_pct}%` },
        ].map(metric => <div key={metric.label} className="rounded bg-slate-50 p-3"><div className="text-xs text-slate-500">{metric.label}</div><div className="text-xl font-semibold">{metric.value}</div></div>)}</div>
      </div>
      {report.artifact && <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-white p-4">
        <div>
          <h3 className="font-semibold">Polished repository</h3>
          <p className="text-sm text-slate-600">Artifact status: {report.artifact.status}</p>
          {report.artifact.filename && <p className="text-xs text-slate-500">
            {report.artifact.filename} · {(report.artifact.size_bytes / 1024).toFixed(1)} KB
            {report.artifact.created_at && ` · Created ${new Date(report.artifact.created_at).toLocaleString()}`}
          </p>}
          <p className="text-xs text-slate-400">Execution {report.artifact.execution_id}</p>
        </div>
        {report.artifact.status === 'ready' && report.artifact.filename && <div className="flex gap-2">
          <button
            className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
            onClick={() => void downloadExecutionArtifact(report.execution.id, report.artifact!.filename!).catch(e => setError(e instanceof Error ? e.message : 'Download failed'))}
          >Download Polished Repository</button>
          <button
            className="rounded border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            disabled={artifactLoading}
            onClick={() => void loadArtifactFiles()}
          >{artifactLoading ? 'Opening…' : 'Open Files'}</button>
        </div>
      </div>}
      {artifactFiles.length > 0 && <div className="mb-5 rounded-lg border bg-white p-4">
        <h3 className="mb-3 font-semibold">Polished repository files</h3>
        <div className="grid gap-4 md:grid-cols-[240px_1fr]">
          <div className="max-h-72 overflow-auto border-r pr-3">
            {artifactFiles.map(file => <button key={file.path} onClick={() => void openArtifactFilePreview(file.path)} className="block w-full truncate rounded px-2 py-1.5 text-left text-xs text-slate-700 hover:bg-slate-100">{file.path}</button>)}
          </div>
          <div>
            {openedFile ? <><div className="mb-2 text-xs font-medium text-slate-500">{openedFile.path}</div><pre className="max-h-96 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100 whitespace-pre-wrap">{openedFile.content}</pre></> : <p className="text-sm text-slate-400">Select a text file to preview it.</p>}
          </div>
        </div>
      </div>}
      <div className="mb-5 grid gap-4 md:grid-cols-2">{[
        { label: 'Before', snapshot: report.before_snapshot },
        { label: 'After', snapshot: report.after_snapshot },
      ].map(({ label, snapshot }) => <article key={label} className="rounded-lg border bg-white p-4"><h3 className="mb-3 font-semibold">{label} snapshot</h3><p className="text-sm">Files: {snapshot.file_count} · Tests: {snapshot.test_function_count} · Lint: {snapshot.lint_error_count} · TODOs: {snapshot.todo_count}</p><p className="text-sm">Documentation coverage: {snapshot.documented_functions_pct.toFixed(1)}%</p></article>)}</div>
      <div className="mb-5 rounded-lg border bg-white p-4"><h3 className="mb-3 font-semibold">Changed files</h3>{report.changed_files.length ? report.changed_files.map(file => <div key={file.path} className="border-t py-2 text-sm"><strong>{file.path}</strong><span className="ml-2 text-slate-500">+{file.lines_added} / −{file.lines_deleted} lines</span></div>) : <p className="text-sm text-slate-500">No file changes recorded.</p>}</div>
      <div className="mb-5 rounded-lg border bg-white p-4"><h3 className="mb-3 font-semibold">Verification</h3>{report.verification ? <><p className={report.verification.passed ? 'text-emerald-700' : 'text-rose-700'}>{report.verification.passed ? 'Passed' : 'Failed'} · pytest {report.verification.pass_count} passed, {report.verification.fail_count} failed · Ruff {report.verification.lint_errors} issues</p><pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-3 text-xs text-slate-100">{report.verification.raw_output}</pre></> : <p className="text-sm text-slate-500">No verification result was persisted.</p>}</div>
      <div className="mb-5 rounded-lg border bg-white p-4"><h3 className="mb-3 font-semibold">Execution event log</h3><div className="space-y-2">{report.agent_actions.map((action, i) => <div key={`${action.timestamp}-${i}`} className="text-sm"><span className="font-medium capitalize">{action.agent_type}</span><span className="ml-2 text-slate-500">{action.event_type} · {action.message}</span></div>)}</div></div>
      <div className="rounded-lg border bg-white p-4"><h3 className="mb-3 font-semibold">Evidence records ({report.evidence.length})</h3><div className="space-y-2">{report.evidence.map(item => <div key={item.id} className="border-t pt-2"><span className="text-xs font-semibold text-cyan-800">{item.type}</span><p className="text-sm">{item.title}</p></div>)}</div></div>
    </>}
  </section>
}
