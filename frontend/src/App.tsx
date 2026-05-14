import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Descriptions,
  Layout,
  Spin,
  Tag,
  Typography,
  theme as antdTheme,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { getHealth, type HealthResponse } from './api'

const { Header, Content } = Layout
const { Title, Paragraph } = Typography

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchHealth = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getHealth()
      setHealth(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
  }, [])

  return (
    <ConfigProvider theme={{ algorithm: antdTheme.defaultAlgorithm }}>
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ display: 'flex', alignItems: 'center', background: '#001529' }}>
          <Title level={3} style={{ color: '#fff', margin: 0 }}>
            Novel Studio
          </Title>
          <Tag color="blue" style={{ marginLeft: 12 }}>
            Phase 1 骨架
          </Tag>
        </Header>
        <Content style={{ padding: 32, maxWidth: 880, margin: '0 auto', width: '100%' }}>
          <Card
            title="后端健康检查"
            extra={
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchHealth}
                loading={loading}
                size="small"
              >
                重新检查
              </Button>
            }
          >
            {loading && <Spin />}
            {error && (
              <Alert
                type="error"
                message="无法连接后端"
                description={error}
                showIcon
                style={{ marginBottom: 16 }}
              />
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

          <Card title="后续阶段" style={{ marginTop: 24 }} size="small">
            <Paragraph type="secondary" style={{ margin: 0 }}>
              Phase 2: Runtime + WebSocket · Phase 3: 移植 4-Agent · Phase 4: 单章流水线 ·
              Phase 5: RAG · Phase 6a: 工作台 UI
            </Paragraph>
          </Card>
        </Content>
      </Layout>
    </ConfigProvider>
  )
}

export default App
