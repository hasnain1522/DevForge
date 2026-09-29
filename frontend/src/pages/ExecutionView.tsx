import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { downloadExecutionArtifact, getExecution, retryExecution, type ExecutionState } from '../api/client'
import type { SubtaskLogEvent } from '../types'

export default function ExecutionView() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const [state, setState] = useState<ExecutionState | null>(null)
  const [events, setEvents] = useState<SubtaskLogEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    if (!runId) return
    let active = true
    let source: EventSource | undefined
    const refresh = async () => {
      try {
        const current = await getExecution(runId)
        if (active) {
          setState(current)
          setEvents(previous => {
            const keys = new Set(previous.map(event => `${event.timestamp}|${event.agent_type}|${event.message}`))
            return [...previous, ...current.events.filter(event => !keys.has(`${event.timestamp}|${event.agent_type}|${event.message}`))]
              .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
          })
          if (current.status !== 'running') source?.close()
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load execution')
      }
    }
    void refresh()
    source = new EventSource(`/api/execute/${encodeURIComponent(runId)}/stream`)
    source.onmessage = event => {
      const item = JSON.parse(event.data) as SubtaskLogEvent
      if (active) setEvents(previous => previous.some(old => old.timestamp === item.timestamp && old.message === item.message) ? previous : [...previous, item])
    }
    source.onerror = () => { void refresh() }
    const poll = window.setInterval(() => { void refresh() }, 2500)
    return () => { active = false; source?.close(); window.clearInterval(poll) }
  }, [runId])

  if (!runId) return <div><h1 className="text-2xl font-semibold text-gray-900 mb-2">Execution</h1><p className="text-sm text-gray-500">Start a mission from the Mission Board to view its live execution.</p></div>

  const statusColor = state?.status === 'completed' ? 'text-green-700 bg-green-50' : state?.status === 'failed' ? 'text-red-700 bg-red-50' : 'text-blue-700 bg-blue-50'
  const skippedFiles = new Set(events.filter(event => event.event_type === 'file_skipped').map(event => event.target_file).filter(Boolean))

  async function handleRetry() {
    if (!runId) return
    setRetrying(true)
    setError(null)
    try {
      const retry = await retryExecution(runId)
      navigate(`/execution/${retry.run_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not retry execution')
    } finally {
      setRetrying(false)
    }
  }
  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div><h1 className="text-2xl font-semibold text-gray-900 mb-1">Execution</h1><p className="text-xs text-gray-500 font-mono">Run {runId}</p></div>
        <span className={`rounded px-3 py-1 text-sm font-medium ${statusColor}`}>{state?.status ?? 'Loading'}</span>
      </div>
      {error && <p className="mb-4 text-sm text-red-700">{error}</p>}
      {state?.status === 'failed' && state.retry_available && <button
        className="mb-5 rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
        disabled={retrying}
        onClick={() => void handleRetry()}
      >{retrying ? 'Starting retry…' : '↻ Retry Failed Step'}</button>}
      {state?.checkpoints.length ? <section className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold">Mission file checkpoints</h2>
        <ul className="space-y-2">{state.checkpoints.map(checkpoint => {
          const skipped = skippedFiles.has(checkpoint.filename)
          const started = checkpoint.status === 'started' && state.status === 'running'
          const icon = checkpoint.status === 'completed' ? '✓' : checkpoint.status === 'failed' ? '✕' : started ? '↻' : '○'
          const label = skipped ? 'Skipped — already completed' : started ? `Retrying ${checkpoint.filename}` : checkpoint.status
          return <li key={checkpoint.filename} className="text-sm">
            <span className={checkpoint.status === 'failed' ? 'text-red-700' : checkpoint.status === 'completed' ? 'text-emerald-700' : 'text-slate-600'}>{icon} {checkpoint.filename} — {label}</span>
            {checkpoint.failure_reason && <p className="ml-5 text-xs text-red-600">{checkpoint.failure_reason}</p>}
          </li>
        })}</ul>
      </section> : null}
      {state?.parent_execution_run_id && state.status === 'completed' && <p className="mb-4 text-sm font-medium text-emerald-700">✓ Retry completed · ✓ Verification passed</p>}
      {state?.artifact && <section className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Polished repository</h2>
            <p className="mt-1 text-sm text-gray-600">Artifact status: {state.artifact.status}</p>
            {state.artifact.filename && <p className="mt-1 text-xs text-gray-500">
              {state.artifact.filename} · {(state.artifact.size_bytes / 1024).toFixed(1)} KB
              {state.artifact.created_at && ` · Created ${new Date(state.artifact.created_at).toLocaleString()}`}
            </p>}
            <p className="mt-1 text-xs text-gray-400">Execution {state.artifact.execution_id}</p>
          </div>
          {state.artifact.status === 'ready' && state.artifact.filename && <button
            className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
            onClick={() => void downloadExecutionArtifact(runId, state.artifact!.filename!).catch(err => setError(err instanceof Error ? err.message : 'Download failed'))}
          >Download Polished Repository</button>}
        </div>
      </section>}
      <div className="grid gap-4 md:grid-cols-2 mb-6">
        <section className="bg-white border border-gray-200 rounded p-4">
          <h2 className="text-sm font-semibold mb-3">Agent activity</h2>
          <div className="space-y-3 max-h-96 overflow-auto">
            {events.length === 0 && <p className="text-sm text-gray-400">Waiting for execution events…</p>}
            {events.map((event, index) => <div key={`${event.timestamp}-${index}`} className="border-l-2 border-blue-200 pl-3">
              <div className="flex justify-between gap-2"><span className="text-xs font-medium text-gray-800">{event.agent_type} · {event.event_type}</span><time className="text-xs text-gray-400">{new Date(event.timestamp).toLocaleTimeString()}</time></div>
              <p className="text-sm text-gray-600">{event.message}</p>{event.target_file && <code className="text-xs text-gray-500">{event.target_file}</code>}
            </div>)}
          </div>
        </section>
        <section className="bg-white border border-gray-200 rounded p-4">
          <h2 className="text-sm font-semibold mb-3">Verification results</h2>
          {state?.failure && <div role="alert" className="mb-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <p className="font-medium">{state.failure.stage} failed · {state.failure.category}</p>
            <p className="mt-1">{state.failure.reason}</p>
            {state.failure.command && <p className="mt-1">Check: <code>{state.failure.command}</code>{state.failure.exit_code !== null && ` · exit code ${state.failure.exit_code}`}</p>}
          </div>}
          {state?.verification ? <>
            <p className={`text-sm font-medium ${state.verification.passed ? 'text-green-700' : 'text-red-700'}`}>{state.verification.passed ? 'Passed' : 'Failed'}</p>
            <p className="text-sm text-gray-600 mt-1">{state.verification.pass_count} passed · {state.verification.fail_count} failed · {state.verification.lint_errors} ruff findings</p>
            {state.verification.coverage_pct !== null && <p className="text-sm text-gray-600">Coverage: {state.verification.coverage_pct}%</p>}
            <pre className="mt-3 max-h-64 overflow-auto rounded bg-gray-50 p-3 text-xs text-gray-700 whitespace-pre-wrap">{state.verification.raw_output}</pre>
          </> : <p className="text-sm text-gray-400">{state?.status === 'failed' ? 'No verification result was produced.' : 'Verification has not finished.'}</p>}
          <h3 className="text-sm font-semibold mt-5 mb-2">Changed files</h3>
          {state?.changed_files.length ? <ul className="list-disc pl-5 text-sm text-gray-600">{state.changed_files.map(file => <li key={file}><code>{file}</code></li>)}</ul> : <p className="text-sm text-gray-400">No files recorded as changed yet.</p>}
        </section>
      </div>
    </div>
  )
}
