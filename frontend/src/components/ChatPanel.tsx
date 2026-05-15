import { useCallback, useEffect, useRef } from 'react'
import { Badge, Button, Drawer, Input, Space, Typography } from 'antd'
import { CloseOutlined, SendOutlined, StopOutlined } from '@ant-design/icons'
import { useChat, type ChatStatus } from '../hooks/useChat'
import ChatMessage from './ChatMessage'

const AGENT_LABELS: Record<string, string> = {
  planner: '规划师',
  reviewer: '审查员',
  writer: '写手',
  polisher: '润色师',
}

function statusBadge(s: ChatStatus) {
  switch (s) {
    case 'ready': return <Badge status="success" text="就绪" />
    case 'connecting': return <Badge status="processing" text="连接中" />
    case 'thinking': return <Badge status="processing" text="思考中" />
    case 'error': return <Badge status="error" text="出错" />
    default: return <Badge status="default" text="未连接" />
  }
}

interface ChatPanelProps {
  open: boolean
  agentName: string | null
  project: string
  chapterNum: number | null
  onClose: () => void
}

export default function ChatPanel({ open, agentName, project, chapterNum, onClose }: ChatPanelProps) {
  const chat = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<string>('')

  useEffect(() => {
    if (open && agentName && !chat.isOpen) {
      chat.open(agentName)
    }
    if (!open && chat.isOpen) {
      chat.close()
    }
  }, [open, agentName])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.messages])

  const handleSend = useCallback(() => {
    const text = inputRef.current
    if (!text.trim()) return
    chat.send(text)
    inputRef.current = ''
    const textarea = document.querySelector('.chat-input textarea') as HTMLTextAreaElement | null
    if (textarea) textarea.value = ''
  }, [chat.send])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const label = agentName ? (AGENT_LABELS[agentName] ?? agentName) : ''
  const canSend = chat.status === 'ready'
  const isThinking = chat.status === 'thinking'

  const title = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Space>
        <Typography.Text strong>与{label}讨论</Typography.Text>
        {statusBadge(chat.status)}
      </Space>
      <Button type="text" icon={<CloseOutlined />} onClick={onClose} size="small" />
    </div>
  )

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={title}
      placement="right"
      width={520}
      closable={false}
      styles={{
        body: { padding: 0, display: 'flex', flexDirection: 'column', height: '100%' },
      }}
    >
      {/* Context hint */}
      {project && chapterNum && (
        <div style={{ padding: '8px 16px', background: '#fafafa', borderBottom: '1px solid #f0f0f0', fontSize: 12, color: '#8c8c8c' }}>
          项目：{project}　章节：第 {chapterNum} 章
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
        {chat.messages.length === 0 && chat.status === 'ready' && (
          <div style={{ textAlign: 'center', padding: 32, color: '#bfbfbf' }}>
            <Typography.Text type="secondary">
              输入你的想法或问题，开始讨论
            </Typography.Text>
          </div>
        )}

        {chat.messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Error display */}
      {chat.error && (
        <div style={{ padding: '4px 16px', background: '#fff2f0', borderTop: '1px solid #ffccc7', fontSize: 12, color: '#ff4d4f' }}>
          {chat.error}
        </div>
      )}

      {/* Input area */}
      <div style={{ padding: '8px 16px', borderTop: '1px solid #f0f0f0', background: '#fff' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <Input.TextArea
            className="chat-input"
            placeholder={canSend ? '输入消息... (Enter 发送, Shift+Enter 换行)' : '等待回复...'}
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={!canSend}
            onChange={(e) => { inputRef.current = e.target.value }}
            onKeyDown={handleKeyDown}
            style={{ flex: 1 }}
          />
          {isThinking ? (
            <Button
              icon={<StopOutlined />}
              danger
              onClick={() => chat.cancel()}
            >
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              disabled={!canSend}
              onClick={handleSend}
            >
              发送
            </Button>
          )}
        </div>
      </div>
    </Drawer>
  )
}
