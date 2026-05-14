export interface Project {
  name: string
  chapters: number[]
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

export interface PipelineResponse {
  pipeline_id: string
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
