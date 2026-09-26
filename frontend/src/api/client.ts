/**
 * API client — typed fetch wrappers for all DevForge backend endpoints.
 *
 * Phase 1: function signatures and structure in place.
 * Phase 2+ will use these functions with real data.
 *
 * All requests go to /api/... which Vite proxies to http://localhost:8000
 */
import type { ImpactReport, Mission, Repository, RepositorySnapshot } from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`API error ${response.status}: ${text}`)
  }
  return response.json() as Promise<T>
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

export async function executeMission(missionId: string): Promise<{ run_id: string }> {
  return request<{ run_id: string }>(`/execute/${missionId}`, { method: 'POST' })
}

// --- Verify ---

export async function verifyRun(runId: string): Promise<{ detail: string }> {
  return request<{ detail: string }>(`/verify/${runId}`, { method: 'POST' })
}

// --- Report ---

export async function getImpactReport(repoId: string): Promise<ImpactReport> {
  return request<ImpactReport>(`/report/${repoId}`)
}

// --- Repositories ---

export async function listRepositories(): Promise<Repository[]> {
  return request<Repository[]>('/repositories')
}
