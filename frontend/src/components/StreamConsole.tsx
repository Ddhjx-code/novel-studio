import { useEffect, useRef } from 'react'
import { Card, Tag, Typography, Empty } from 'antd'
import type { WSEvent } from '../hooks/useWebSocket'

const { Text, Paragraph } = Typography

interface StreamConsoleProps {
  events: WSEvent[]
  connected: boolean
}

function EventBadge({ type }: { type: string }) {
  const colorMap: Record<string, string> = {
    'agent.text': 'blue',
    'agent.turn_complete': 'green',
    'agent.tool_start': 'orange',
    'agent.tool_end': 'cyan',
    'error': 'red',
    'status': 'default',
    'compact': 'purple',
    'session.started': 'geekblue',
    'session.done': 'green',
    'session.cancelled': 'volcano',
  }
  return <Tag color={colorMap[type] ?? 'default'}>{type}</Tag>
}

function renderEventContent(event: WSEvent) {
  switch (event.type) {
    case 'agent.text':
      return <Text>{String(event.data.text ?? '')}</Text>
    case 'agent.turn_complete': {
      const usage = event.data.usage as Record<string, unknown> | undefined
      const info = usage
        ? `${usage.input_tokens}→${usage.output_tokens}`
        : '?'
      return <Text type="secondary">Turn complete (tokens: {info})</Text>
    }
    case 'agent.tool_start':
      return (
        <Text code>
          {String(event.data.tool_name)}({JSON.stringify(event.data.tool_input)})
        </Text>
      )
    case 'agent.tool_end':
      return (
        <Paragraph
          ellipsis={{ rows: 2, expandable: 'collapsible' }}
          style={{ margin: 0, maxWidth: '100%' }}
        >
          <Text type={event.data.is_error ? 'danger' : 'success'}>
            {String(event.data.tool_name)}: {String(event.data.output ?? '')}
          </Text>
        </Paragraph>
      )
    case 'error':
      return <Text type="danger">{String(event.data.message ?? 'Unknown error')}</Text>
    case 'session.started':
      return <Text type="secondary">Prompt: {String(event.data.prompt ?? '')}</Text>
    case 'session.done':
      return <Text type="success">Done</Text>
    case 'session.cancelled':
      return <Text type="warning">Cancelled</Text>
    default:
      return <Text type="secondary">{JSON.stringify(event.data)}</Text>
  }
}

export default function StreamConsole({ events, connected }: StreamConsoleProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <Card
      title="Event Stream"
      extra={
        <Tag color={connected ? 'green' : 'default'}>
          {connected ? 'Connected' : 'Disconnected'}
        </Tag>
      }
      style={{ marginTop: 16 }}
      styles={{ body: { maxHeight: 480, overflowY: 'auto', padding: '12px 16px' } }}
    >
      {events.length === 0 ? (
        <Empty description="No events yet" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        events.map((event, idx) => (
          <div
            key={idx}
            style={{
              marginBottom: 6,
              display: 'flex',
              gap: 8,
              alignItems: 'flex-start',
            }}
          >
            <EventBadge type={event.type} />
            <div style={{ flex: 1, minWidth: 0 }}>{renderEventContent(event)}</div>
          </div>
        ))
      )}
      <div ref={bottomRef} />
    </Card>
  )
}
