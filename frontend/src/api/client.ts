/**
 * Same-origin API calls use the HttpOnly session cookie set by the backend.
 */
import type {
  AuthUser,
  EvidenceRecord,
  ExecutionArtifact,
  ImpactReport,
  Mission,
  Repository,
  RepositorySnapshot,
} from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...options,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`API error ${response.status}: ${text}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function register(email: string, password: string): Promise<AuthUser> {
  return request<AuthUser>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export async function login(email: string, password: string): Promise<AuthUser> {
  return request<AuthUser>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export async function logout(): Promise<void> {
  await request<void>('/auth/logout', { method: 'POST' })
}

export async function getCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>('/auth/me')
}

// --- Analyze ---

export async function analyzeRepository(repoPath: string): Promise<RepositorySnapshot> {
  return request<RepositorySnapshot>('/analyze', {
    method: 'POST',
    body: JSON.stringify({ repo_path: repoPath }),
  })
}

// --- Missions ---

export async function listMissions(repositoryId: string): Promise<Mission[]> {
  return request<Mission[]>(`/missions?repository_id=${encodeURIComponent(repositoryId)}`)
}

export async function updateMissionStatus(
  missionId: string,
  status: Mission['status'],
): Promise<Mission> {
  return request<Mission>(`/missions/${missionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

// --- Execute ---

export interface ExecutionState {
  id: string
  mission_id: string
  status: 'running' | 'completed' | 'failed'
  parent_execution_run_id: string | null
  retry_available: boolean
  retry_run_id: string | null
  checkpoints: Array<{
    filename: string
    agent: string
    order: number
    mission_id: string
    status: 'not_started' | 'started' | 'completed' | 'failed'
    failure_reason: string | null
    execution_id: string | null
  }>
  subtask_count: number
  subtasks_completed: number
  subtasks_failed: number
  changed_files: string[]
  events: import('../types').SubtaskLogEvent[]
  verification: import('../types').VerificationResult & { raw_output: string } | null
  failure: {
    stage: string
    category: string
    reason: string
    command: string | null
    exit_code: number | null
    created_at: string
  } | null
  artifact: ExecutionArtifact | null
}

export async function executeMission(missionId: string): Promise<{ run_id: string; status: string }> {
  return request<{ run_id: string; status: string }>(`/execute/${missionId}`, { method: 'POST' })
}

export async function retryExecution(runId: string): Promise<{ run_id: string; status: string; parent_run_id: string }> {
  return request<{ run_id: string; status: string; parent_run_id: string }>(
    `/execute/${encodeURIComponent(runId)}/retry`, { method: 'POST' },
  )
}

export async function getExecution(runId: string): Promise<ExecutionState> {
  return request<ExecutionState>(`/execute/${runId}`)
}

export async function downloadExecutionArtifact(runId: string, filename: string): Promise<void> {
  const response = await fetch(`${BASE}/execute/${encodeURIComponent(runId)}/artifact`, {
    credentials: 'same-origin',
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Artifact download failed (${response.status}): ${detail}`)
  }
  const objectUrl = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

// --- Verify ---

export async function verifyRun(runId: string): Promise<{ detail: string }> {
  return request<{ detail: string }>(`/verify/${runId}`, { method: 'POST' })
}

// --- Report ---

export async function getImpactReport(repoId: string): Promise<ImpactReport> {
  return request<ImpactReport>(`/report/${repoId}`)
}

export async function listExecutions(): Promise<Array<{ id: string; mission_id: string; mission_title: string; status: 'running' | 'completed' | 'failed'; started_at: string; finished_at: string | null }>> {
  return request('/executions')
}

export async function listEvidence(repositoryId?: string): Promise<EvidenceRecord[]> {
  const query = repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : ''
  return request(`/evidence${query}`)
}

// --- Repositories ---

export async function listRepositories(): Promise<Repository[]> {
  return request<Repository[]>('/repositories')
}
