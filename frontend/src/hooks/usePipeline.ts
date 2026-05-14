import { useCallback, useState } from 'react'
import type { PipelineResponse } from '../types'

interface PipelineEntry {
  status: string
  startedAt: Date
}

export function usePipeline() {
  const [activePipelines, setActivePipelines] = useState<Map<string, PipelineEntry>>(new Map())
  const [loading, setLoading] = useState(false)

  const trigger = useCallback(async (apiCall: () => Promise<PipelineResponse>) => {
    setLoading(true)
    try {
      const resp = await apiCall()
      setActivePipelines((prev) => {
        const next = new Map(prev)
        next.set(resp.pipeline_id, { status: resp.status, startedAt: new Date() })
        return next
      })
      return resp
    } finally {
      setLoading(false)
    }
  }, [])

  const clearPipeline = useCallback((id: string) => {
    setActivePipelines((prev) => {
      const next = new Map(prev)
      next.delete(id)
      return next
    })
  }, [])

  return { trigger, activePipelines, loading, clearPipeline }
}
