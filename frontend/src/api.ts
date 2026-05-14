import axios from 'axios'
import type {
  AgentListResponse,
  ChapterContent,
  PipelineResponse,
  Project,
  ProjectListResponse,
  ReloadAgentsResponse,
} from './types'

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export interface HealthResponse {
  status: string
  version: string
  llm_configured: 'yes' | 'no'
  llm_model: string
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await api.get<HealthResponse>('/health')
  return res.data
}

// --- Session types ---

export interface CreateSessionRequest {
  cwd?: string
  model?: string
  system_prompt?: string
  max_turns?: number
}

export interface CreateSessionResponse {
  session_id: string
}

export interface SubmitPromptRequest {
  prompt: string
}

// --- Session API ---

export async function createSession(
  body: CreateSessionRequest = {},
): Promise<CreateSessionResponse> {
  const resp = await api.post<CreateSessionResponse>('/sessions', body)
  return resp.data
}

export async function listSessions(): Promise<{ session_ids: string[] }> {
  const resp = await api.get<{ session_ids: string[] }>('/sessions')
  return resp.data
}

export async function submitPrompt(sessionId: string, prompt: string): Promise<void> {
  await api.post(`/sessions/${sessionId}/submit`, { prompt })
}

export async function cancelSession(sessionId: string): Promise<void> {
  await api.post(`/sessions/${sessionId}/cancel`)
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/sessions/${sessionId}`)
}

// --- Projects API ---

export async function listProjects(): Promise<ProjectListResponse> {
  const resp = await api.get<ProjectListResponse>('/projects')
  return resp.data
}

export async function createProject(name: string): Promise<{ name: string; path: string }> {
  const resp = await api.post<{ name: string; path: string }>('/projects', { name })
  return resp.data
}

export async function getProject(name: string): Promise<Project> {
  const resp = await api.get<Project>(`/projects/${name}`)
  return resp.data
}

// --- Chapters API ---

export async function readChapter(project: string, n: number): Promise<ChapterContent> {
  const resp = await api.get<ChapterContent>(`/projects/${project}/chapters/${n}`)
  return resp.data
}

export async function saveChapter(project: string, n: number, content: string): Promise<void> {
  await api.put(`/projects/${project}/chapters/${n}`, { content })
}

export async function generateChapter(
  project: string,
  n: number,
  steps?: string[],
): Promise<PipelineResponse> {
  const resp = await api.post<PipelineResponse>(
    `/projects/${project}/chapters/${n}/generate`,
    { steps: steps ?? null },
  )
  return resp.data
}

export async function reviewChapter(project: string, n: number): Promise<PipelineResponse> {
  const resp = await api.post<PipelineResponse>(`/projects/${project}/chapters/${n}/review`)
  return resp.data
}

export async function polishChapter(project: string, n: number): Promise<PipelineResponse> {
  const resp = await api.post<PipelineResponse>(`/projects/${project}/chapters/${n}/polish`)
  return resp.data
}

// --- Outline API ---

export async function generateOutline(
  project: string,
  synopsis: string,
  userGuidance?: string,
): Promise<PipelineResponse> {
  const resp = await api.post<PipelineResponse>(`/projects/${project}/outline/generate`, {
    synopsis,
    user_guidance: userGuidance ?? '',
  })
  return resp.data
}

// --- Agents API ---

export async function listAgents(): Promise<AgentListResponse> {
  const resp = await api.get<AgentListResponse>('/agents')
  return resp.data
}

export async function reloadAgents(): Promise<ReloadAgentsResponse> {
  const resp = await api.post<ReloadAgentsResponse>('/agents/reload')
  return resp.data
}
