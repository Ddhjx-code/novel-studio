export interface Project {
  name: string
  chapters: number[]
  planned_chapters: number[]
  has_outline: boolean
  global_summary_length: number
  character_state_length: number
}

export interface ProjectListResponse {
  projects: string[]
}

export interface ChapterContent {
  chapter_num: number
  content: string
}

export interface ChapterArtifact {
  chapter_num: number
  content: string
  exists: boolean
}

export interface PipelineResponse {
  pipeline_id: string
  task_id?: string
  status: string
}

export interface AgentInfo {
  name: string
  description: string
  tools: string[]
  disallowed_tools: string[]
  skills: string[]
  max_turns: number
}

export interface AgentListResponse {
  agents: AgentInfo[]
}

export interface ReloadAgentsResponse {
  reloaded: number
  names: string[]
}

// --- Bible ---

export interface BibleTreeResponse {
  files: string[]
}

export interface BibleFileContent {
  path: string
  content: string
}

// --- Prompts ---

export interface PromptAgentEntry {
  name: string
  description: string
  path: string
}

export interface PromptAgentDetail {
  name: string
  content: string
}

export interface PromptSkillEntry {
  name: string
  files: string[]
}

export interface PromptSkillFile {
  path: string
  content: string
}

// --- Tasks ---

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TaskKind = 'chapter_generate' | 'outline_generate' | 'chapter_review' | 'chapter_polish'

export interface TaskCard {
  id: string
  kind: TaskKind
  status: TaskStatus
  project_name: string
  chapter_num: number | null
  pipeline_id: string
  steps_requested: string[]
  steps_completed: string[]
  error: string | null
  created_at: string
  updated_at: string
  metadata: Record<string, unknown>
}

export interface TaskListResponse {
  tasks: TaskCard[]
}
