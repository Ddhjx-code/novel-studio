import { Collapse, Spin, Tag, Typography } from 'antd'
import { RobotOutlined, UserOutlined } from '@ant-design/icons'
import type { ChatMessage as ChatMessageType, ToolCallInfo } from '../hooks/useChat'
import MarkdownViewer from './MarkdownViewer'

function ToolCallItem({ tc }: { tc: ToolCallInfo }) {
  const header = (
    <span style={{ fontSize: 12 }}>
      {tc.pending && <Spin size="small" style={{ marginRight: 6 }} />}
      <Tag color={tc.isError ? 'red' : tc.pending ? 'processing' : 'green'} style={{ fontSize: 11 }}>
        {tc.toolName}
      </Tag>
      {tc.pending && '运行中...'}
    </span>
  )

  if (tc.pending) {
    return <div style={{ padding: '4px 0' }}>{header}</div>
  }

  const inputStr = typeof tc.toolInput === 'string'
    ? tc.toolInput
    : JSON.stringify(tc.toolInput, null, 2)

  const outputStr = tc.output && tc.output.length > 500
    ? tc.output.slice(0, 500) + '...'
    : tc.output

  return (
    <Collapse
      size="small"
      items={[{
        key: '1',
        label: header,
        children: (
          <div style={{ fontSize: 11, lineHeight: 1.5 }}>
            {inputStr && (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 120, overflow: 'auto' }}>
                {inputStr}
              </pre>
            )}
            {outputStr && (
              <>
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>输出：</Typography.Text>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 200, overflow: 'auto', color: tc.isError ? '#ff4d4f' : undefined }}>
                  {outputStr}
                </pre>
              </>
            )}
          </div>
        ),
      }]}
      style={{ marginTop: 4 }}
    />
  )
}

const userBubbleStyle: React.CSSProperties = {
  background: '#e6f4ff',
  borderRadius: 12,
  padding: '8px 12px',
  maxWidth: '85%',
  marginLeft: 'auto',
  wordBreak: 'break-word',
}

const assistantBubbleStyle: React.CSSProperties = {
  background: '#f5f5f5',
  borderRadius: 12,
  padding: '8px 12px',
  maxWidth: '85%',
  wordBreak: 'break-word',
}

export default function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === 'user'

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'flex-start' }}>
      {!isUser && (
        <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#f0f0f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <RobotOutlined style={{ fontSize: 14, color: '#8c8c8c' }} />
        </div>
      )}

      <div style={isUser ? userBubbleStyle : assistantBubbleStyle}>
        {isUser ? (
          <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {message.content}
          </div>
        ) : (
          <>
            {message.content ? (
              message.streaming ? (
                <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                  {message.content}
                  <span style={{ animation: 'blink 1s infinite', opacity: 0.6 }}>▍</span>
                </div>
              ) : (
                <MarkdownViewer content={message.content} />
              )
            ) : message.streaming ? (
              <Spin size="small" />
            ) : null}

            {message.toolCalls.length > 0 && (
              <div style={{ marginTop: 6 }}>
                {message.toolCalls.map((tc, i) => (
                  <ToolCallItem key={i} tc={tc} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {isUser && (
        <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#e6f4ff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <UserOutlined style={{ fontSize: 14, color: '#1677ff' }} />
        </div>
      )}
    </div>
  )
}
