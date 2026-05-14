import { useEffect, useRef, useState, useCallback } from 'react'

export interface WSEvent {
  type: string
  data: Record<string, unknown>
  ts: string
}

interface UseWebSocketResult {
  events: WSEvent[]
  connected: boolean
  error: string | null
  clearEvents: () => void
}

export function useWebSocket(sessionId: string | null): UseWebSocketResult {
  const [events, setEvents] = useState<WSEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const clearEvents = useCallback(() => setEvents([]), [])

  useEffect(() => {
    if (!sessionId) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/sessions/${sessionId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data)
        setEvents((prev) => [...prev, event])
      } catch {
        /* ignore malformed messages */
      }
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
    }

    ws.onclose = () => {
      setConnected(false)
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [sessionId])

  return { events, connected, error, clearEvents }
}
