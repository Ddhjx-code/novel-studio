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
