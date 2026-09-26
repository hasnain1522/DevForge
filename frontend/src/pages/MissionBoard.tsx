/**
 * MissionBoard — displays persisted missions for a repository.
 * Phase 2: real missions retrieved from GET /missions?repository_id=...
 */
import { useState } from 'react'
import { listMissions, updateMissionStatus } from '../api/client'
import type { Mission, MissionPriority, MissionType } from '../types'

const PRIORITY_BADGE: Record<MissionPriority, string> = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-gray-100 text-gray-600',
}

const TYPE_LABEL: Record<MissionType, string> = {
  test_coverage: 'Test Coverage',
  bug_fix: 'Bug Fix',
  documentation: 'Documentation',
  refactor: 'Refactor',
  dependency_update: 'Dependencies',
}

function MissionCard({ mission, onDismiss }: { mission: Mission; onDismiss: (id: string) => void }) {
  const [dismissing, setDismissing] = useState(false)

  async function handleDismiss() {
    setDismissing(true)
    try {
      await updateMissionStatus(mission.id, 'dismissed')
      onDismiss(mission.id)
    } catch {
      setDismissing(false)
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${PRIORITY_BADGE[mission.priority as MissionPriority] ?? 'bg-gray-100 text-gray-600'}`}>
            {mission.priority}
          </span>
          <span className="text-xs text-gray-500 border border-gray-200 px-2 py-0.5 rounded">
            {TYPE_LABEL[mission.mission_type as MissionType] ?? mission.mission_type}
          </span>
        </div>
        <button
          onClick={handleDismiss}
          disabled={dismissing}
          className="text-xs text-gray-400 hover:text-gray-600 disabled:opacity-50 shrink-0"
        >
          Dismiss
        </button>
      </div>

      <h3 className="text-sm font-medium text-gray-900 mb-1">{mission.title}</h3>
      <p className="text-sm text-gray-600 mb-3">{mission.problem}</p>

      {mission.affected_files.length > 0 && (
        <div className="mb-2">
          <span className="text-xs text-gray-500">Affected: </span>
          <span className="text-xs text-gray-600">{mission.affected_files.join(', ')}</span>
        </div>
      )}

      {/* Informational only — LLM-generated text, not measurements */}
      {mission.expected_impact && (
        <p className="text-xs text-gray-400 italic">Impact: {mission.expected_impact}</p>
      )}
    </div>
  )
}

export default function MissionBoard() {
  const [repositoryId, setRepositoryId] = useState('')
  const [inputId, setInputId] = useState('')
  const [missions, setMissions] = useState<Mission[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadMissions(repoId: string) {
    if (!repoId.trim()) return
    setLoading(true)
    setError(null)
    try {
      const results = await listMissions(repoId.trim())
      setMissions(results)
      setRepositoryId(repoId.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load missions')
    } finally {
      setLoading(false)
    }
  }

  function handleDismiss(id: string) {
    setMissions(prev => prev.filter(m => m.id !== id))
  }

  const active = missions.filter(m => m.status !== 'dismissed')

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-2">Mission Board</h1>
      <p className="text-sm text-gray-500 mb-6">
        Prioritized engineering missions generated from repository analysis.
      </p>

      {/* Repository ID input */}
      <div className="bg-white border border-gray-200 rounded p-4 mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Repository ID
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            placeholder="Paste repository ID from Dashboard"
            value={inputId}
            onChange={e => setInputId(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && loadMissions(inputId)}
          />
          <button
            onClick={() => loadMissions(inputId)}
            disabled={loading || !inputId.trim()}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Loading…' : 'Load Missions'}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {/* Mission list */}
      {repositoryId && !loading && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-700">
              {active.length} mission{active.length !== 1 ? 's' : ''} pending
            </h2>
          </div>

          {active.length === 0 ? (
            <div className="rounded border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">
              No pending missions for this repository.
            </div>
          ) : (
            <div className="space-y-3">
              {active.map(mission => (
                <MissionCard key={mission.id} mission={mission} onDismiss={handleDismiss} />
              ))}
            </div>
          )}
        </div>
      )}

      {!repositoryId && !loading && (
        <div className="rounded border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-400">
          Run analysis on the Dashboard first, then paste the Repository ID here.
        </div>
      )}
    </div>
  )
}
