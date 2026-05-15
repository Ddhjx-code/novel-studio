import { useCallback, useEffect, useRef, useState } from 'react'
import { createSession, submitPrompt, cancelSession, deleteSession } from '../api'
import { useWebSocket, type WSEvent } from './useWebSocket'

export interface ToolCallInfo {
  toolName: string
  toolInput: unknown
  output?: string
  isError?: boolean
  pending: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming: boolean
  toolCalls: ToolCallInfo[]
  timestamp: Date
}

export type ChatStatus = 'idle' | 'connecting' | 'ready' | 'thinking' | 'error'

function genId(): string {
  return Math.random().toString(36).slice(2, 10)
}

function processEvents(
  events: WSEvent[],
  cursor: number,
  prev: ChatMessage[],
): { messages: ChatMessage[]; newCursor: number; doneOrError: boolean } {
  const messages = [...prev]
  let doneOrError = false

  for (let i = cursor; i < events.length; i++) {
    const ev = events[i]
    const lastMsg = messages[messages.length - 1]

    switch (ev.type) {
      case 'agent.text': {
        const text = (ev.data.text as string) ?? ''
        if (!lastMsg || lastMsg.role !== 'assistant' || !lastMsg.streaming) {
          messages.push({
            id: genId(),
            role: 'assistant',
            content: text,
            streaming: true,
            toolCalls: [],
            timestamp: new Date(),
          })
        } else {
          messages[messages.length - 1] = {
            ...lastMsg,
            content: lastMsg.content + text,
          }
        }
        break
      }

      case 'agent.tool_start': {
        if (!lastMsg || lastMsg.role !== 'assistant') {
          messages.push({
            id: genId(),
            role: 'assistant',
            content: '',
            streaming: true,
            toolCalls: [],
            timestamp: new Date(),
          })
        }
        const target = messages[messages.length - 1]
        messages[messages.length - 1] = {
          ...target,
          toolCalls: [
            ...target.toolCalls,
            {
              toolName: (ev.data.tool_name as string) ?? '',
              toolInput: ev.data.tool_input,
              pending: true,
            },
          ],
        }
        break
      }

      case 'agent.tool_end': {
        if (lastMsg?.role === 'assistant') {
          const toolCalls = [...lastMsg.toolCalls]
          const idx = toolCalls.findLastIndex(
            (t) => t.pending && t.toolName === ((ev.data.tool_name as string) ?? ''),
          )
          if (idx >= 0) {
            toolCalls[idx] = {
              ...toolCalls[idx],
              output: (ev.data.output as string) ?? '',
              isError: (ev.data.is_error as boolean) ?? false,
              pending: false,
            }
          }
          messages[messages.length - 1] = { ...lastMsg, toolCalls }
        }
        break
      }

      case 'agent.turn_complete':
      case 'session.done': {
        if (lastMsg?.role === 'assistant' && lastMsg.streaming) {
          messages[messages.length - 1] = { ...lastMsg, streaming: false }
        }
        doneOrError = true
        break
      }

      case 'session.cancelled': {
        if (lastMsg?.role === 'assistant' && lastMsg.streaming) {
          messages[messages.length - 1] = { ...lastMsg, streaming: false }
        }
        doneOrError = true
        break
      }

      case 'error': {
        if (lastMsg?.role === 'assistant' && lastMsg.streaming) {
          messages[messages.length - 1] = { ...lastMsg, streaming: false }
        }
        doneOrError = true
        break
      }
    }
  }

  return { messages, newCursor: events.length, doneOrError }
}

export function useChat() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [agentName, setAgentName] = useState<string | null>(null)

  const sessionIdRef = useRef<string | null>(null)
  const cursorRef = useRef(0)

  const { events, connected } = useWebSocket(sessionId)

  useEffect(() => {
    if (connected && status === 'connecting') {
      setStatus('ready')
    }
  }, [connected, status])

  useEffect(() => {
    if (cursorRef.current >= events.length) return

    const { messages: updated, newCursor, doneOrError } = processEvents(
      events,
      cursorRef.current,
      messages,
    )
    cursorRef.current = newCursor
    setMessages(updated)

    if (doneOrError) {
      const lastEvent = events[events.length - 1]
      if (lastEvent?.type === 'error') {
        setStatus('error')
        setError((lastEvent.data.message as string) ?? 'Unknown error')
      } else {
        setStatus('ready')
      }
    }
  }, [events])

  const open = useCallback(async (agent: string) => {
    if (sessionIdRef.current) {
      await deleteSession(sessionIdRef.current).catch(() => {})
    }

    setStatus('connecting')
    setError(null)
    setMessages([])
    setAgentName(agent)
    cursorRef.current = 0

    try {
      const resp = await createSession({ agent_name: agent })
      sessionIdRef.current = resp.session_id
      setSessionId(resp.session_id)
    } catch (e) {
      setStatus('error')
      setError(e instanceof Error ? e.message : 'Failed to create session')
    }
  }, [])

  const send = useCallback(async (text: string) => {
    if (!sessionIdRef.current || !text.trim()) return

    setMessages((prev) => [
      ...prev,
      {
        id: genId(),
        role: 'user',
        content: text.trim(),
        streaming: false,
        toolCalls: [],
        timestamp: new Date(),
      },
    ])
    setStatus('thinking')

    try {
      await submitPrompt(sessionIdRef.current, text.trim())
    } catch (e) {
      setStatus('error')
      setError(e instanceof Error ? e.message : 'Failed to send message')
    }
  }, [])

  const cancel = useCallback(async () => {
    if (!sessionIdRef.current) return
    try {
      await cancelSession(sessionIdRef.current)
    } catch {
      /* ignore */
    }
  }, [])

  const close = useCallback(async () => {
    if (sessionIdRef.current) {
      await deleteSession(sessionIdRef.current).catch(() => {})
      sessionIdRef.current = null
    }
    setSessionId(null)
    setMessages([])
    setStatus('idle')
    setError(null)
    setAgentName(null)
    cursorRef.current = 0
  }, [])

  useEffect(() => {
    return () => {
      if (sessionIdRef.current) {
        deleteSession(sessionIdRef.current).catch(() => {})
      }
    }
  }, [])

  return {
    messages,
    status,
    error,
    agentName,
    isOpen: sessionId !== null,
    open,
    send,
    cancel,
    close,
  }
}
