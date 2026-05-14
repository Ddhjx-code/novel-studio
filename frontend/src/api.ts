import axios from 'axios'

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
