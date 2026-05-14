import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Descriptions,
  Input,
  Layout,
  Space,
  Spin,
  Tag,
  Typography,
  theme as antdTheme,
} from 'antd'
import {
  CaretRightOutlined,
  CloseOutlined,
  ReloadOutlined,
  StopOutlined,
} from '@ant-design/icons'
import {
  getHealth,
  createSession,
  submitPrompt,
  cancelSession,
  deleteSession,
  type HealthResponse,
} from './api'
import { useWebSocket } from './hooks/useWebSocket'
import StreamConsole from './components/StreamConsole'

const { Header, Content } = Layout
const { Title, Paragraph } = Typography
const { TextArea } = Input

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [sessionError, setSessionError] = useState<string | null>(null)

  const { events, connected, error: wsError, clearEvents } = useWebSocket(sessionId)

  const fetchHealth = async () => {
    setHealthLoading(true)
    setHealthError(null)
    try {
      setHealth(await getHealth())
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : String(err))
      setHealth(null)
    } finally {
      setHealthLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
  }, [])

  const handleStartSession = async () => {
    setSessionError(null)
    try {
      const resp = await createSession({})
      setSessionId(resp.session_id)
      clearEvents()
    } catch (err) {
      setSessionError(err instanceof Error ? err.message : String(err))
    }
  }

  const handleSubmit = async () => {
    if (!sessionId || !prompt.trim()) return
    setSubmitting(true)
    setSessionError(null)
    try {
      await submitPrompt(sessionId, prompt.trim())
      setPrompt('')
    } catch (err) {
      setSessionError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = async () => {
    if (!sessionId) return
    try {
      await cancelSession(sessionId)
    } catch {
      /* best effort */
    }
  }

  const handleClose = async () => {
    if (sessionId) {
      try {
        await deleteSession(sessionId)
      } catch {
        /* best effort */
      }
    }
    setSessionId(null)
    clearEvents()
  }

  return (
    <ConfigProvider theme={{ algorithm: antdTheme.defaultAlgorithm }}>
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ display: 'flex', alignItems: 'center', background: '#001529' }}>
          <Title level={3} style={{ color: '#fff', margin: 0 }}>
            Novel Studio
          </Title>
          <Tag color="blue" style={{ marginLeft: 12 }}>
            Phase 2 Runtime + WS
          </Tag>
        </Header>
        <Content style={{ padding: 32, maxWidth: 960, margin: '0 auto', width: '100%' }}>
          {/* Health Check */}
          <Card
            title="后端健康检查"
            extra={
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchHealth}
                loading={healthLoading}
                size="small"
              >
                重新检查
              </Button>
            }
          >
            {healthLoading && <Spin />}
            {healthError && (
              <Alert type="error" message="无法连接后端" description={healthError} showIcon />
            )}
            {health && (
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="状态">
                  <Tag color={health.status === 'ok' ? 'green' : 'red'}>{health.status}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="后端版本">{health.version}</Descriptions.Item>
                <Descriptions.Item label="LLM 已配置">
                  <Tag color={health.llm_configured === 'yes' ? 'green' : 'orange'}>
                    {health.llm_configured}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="LLM 模型">{health.llm_model}</Descriptions.Item>
              </Descriptions>
            )}
          </Card>

          {/* Test Agent */}
          <Card
            title="Test Agent"
            style={{ marginTop: 24 }}
            extra={
              sessionId ? (
                <Space>
                  <Tag color={connected ? 'green' : 'orange'}>
                    {connected ? 'WS Connected' : 'WS Connecting...'}
                  </Tag>
                  <Button icon={<CloseOutlined />} size="small" onClick={handleClose} danger>
                    Close Session
                  </Button>
                </Space>
              ) : (
                <Button type="primary" size="small" onClick={handleStartSession}>
                  Start Session
                </Button>
              )
            }
          >
            {sessionError && (
              <Alert
                type="error"
                message={sessionError}
                showIcon
                closable
                style={{ marginBottom: 12 }}
              />
            )}
            {wsError && (
              <Alert
                type="warning"
                message={wsError}
                showIcon
                closable
                style={{ marginBottom: 12 }}
              />
            )}

            {!sessionId ? (
              <Paragraph type="secondary">
                点击 Start Session 创建一个 Agent 会话，然后发送提示词测试 OpenHarness 集成。
              </Paragraph>
            ) : (
              <>
                <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
                  <TextArea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="输入提示词..."
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    onPressEnter={(e) => {
                      if (!e.shiftKey) {
                        e.preventDefault()
                        handleSubmit()
                      }
                    }}
                    disabled={!connected}
                    style={{ flex: 1 }}
                  />
                  <Button
                    type="primary"
                    icon={<CaretRightOutlined />}
                    onClick={handleSubmit}
                    loading={submitting}
                    disabled={!connected || !prompt.trim()}
                  >
                    Send
                  </Button>
                  <Button icon={<StopOutlined />} onClick={handleCancel} disabled={!connected}>
                    Cancel
                  </Button>
                </Space.Compact>
                <StreamConsole events={events} connected={connected} />
              </>
            )}
          </Card>
        </Content>
      </Layout>
    </ConfigProvider>
  )
}

export default App
