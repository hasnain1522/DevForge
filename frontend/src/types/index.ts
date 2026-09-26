/**
 * Shared TypeScript types matching the API response models defined in DATA_MODEL.md.
 * These types are used by the API client and all page components.
 */

export type RepositoryStatus = 'pending' | 'analyzing' | 'ready' | 'error'
export type MissionType = 'bug_fix' | 'test_coverage' | 'documentation' | 'refactor' | 'dependency_update'
export type MissionPriority = 'critical' | 'high' | 'medium' | 'low'
export type MissionStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'dismissed'
export type ExecutionStatus = 'running' | 'completed' | 'failed'
export type AgentType = 'implementer' | 'tester' | 'documenter' | 'orchestrator'
export type EventType = 'started' | 'progress' | 'completed' | 'failed'

export interface Repository {
  id: string
  name: string
  path: string
  status: RepositoryStatus
  created_at: string
}

export interface RepositorySnapshot {
  id: string
  repository_id: string
  taken_at: string
  snapshot_type: 'baseline' | 'post_mission'
  file_count: number
  test_file_count: number
  test_function_count: number
  todo_count: number
  lint_error_count: number
  documented_functions_pct: number
  languages: Record<string, number>
  top_issues: string[]
  analysis_summary: string
}

export interface Mission {
  id: string
  repository_id: string
  title: string
  problem: string
  mission_type: MissionType
  affected_files: string[]
  priority: MissionPriority
  /** Informational only — LLM-generated text, not a measured value */
  estimated_effort: string
  /** Informational only — LLM-generated text, not a measured value */
  expected_impact: string
  status: MissionStatus
  verification_requirements: string[]
  created_at: string
  updated_at: string
}

export interface ExecutionRun {
  id: string
  mission_id: string
  started_at: string
  finished_at: string | null
  status: ExecutionStatus
  subtask_count: number
  subtasks_completed: number
  subtasks_failed: number
  execution_time_seconds: number | null
}

export interface VerificationResult {
  id: string
  execution_run_id: string
  run_at: string
  passed: boolean
  test_count: number
  pass_count: number
  fail_count: number
  lint_errors: number
  /** null when pytest-cov is not installed or did not produce output */
  coverage_pct: number | null
}

export interface ImpactReport {
  mission_id: string
  /** Arithmetic delta — all objective measurements */
  delta_tests_added: number
  delta_lint_errors: number
  delta_todo_count: number
  delta_doc_coverage_pct: number
  lines_changed: number
  agent_execution_time_seconds: number
  verification_passed: boolean
  before_snapshot: RepositorySnapshot
  after_snapshot: RepositorySnapshot
}

export interface SubtaskLogEvent {
  execution_run_id: string
  agent_type: AgentType
  event_type: EventType
  message: string
  target_file: string | null
  timestamp: string
}
