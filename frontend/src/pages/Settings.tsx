import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons'
import {
  getHealth,
  getLLMSettings,
  listAgents,
  reloadAgents,
  saveLLMSettings,
  type HealthResponse,
  type LLMSettings,
} from '../api'
import type { AgentInfo } from '../types'

export default function Settings() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [agentsLoading, setAgentsLoading] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [llmForm] = Form.useForm<LLMSettings>()

  const fetchHealth = useCallback(async () => {
    setHealthLoading(true)
    try {
      setHealth(await getHealth())
    } catch {
      message.error('无法连接后端')
    } finally {
      setHealthLoading(false)
    }
  }, [])

  const fetchAgents = useCallback(async () => {
    setAgentsLoading(true)
    try {
      const resp = await listAgents()
      setAgents(resp.agents)
    } catch {
      message.error('加载 Agent 列表失败')
    } finally {
      setAgentsLoading(false)
    }
  }, [])

  const fetchLLMSettings = useCallback(async () => {
    try {
      const settings = await getLLMSettings()
      llmForm.setFieldsValue(settings)
    } catch {
      message.error('加载 LLM 配置失败')
    }
  }, [llmForm])

  useEffect(() => {
    fetchHealth()
    fetchAgents()
    fetchLLMSettings()
  }, [fetchHealth, fetchAgents, fetchLLMSettings])

  const handleReload = async () => {
    setReloading(true)
    try {
      const resp = await reloadAgents()
      message.success(`已重新加载 ${resp.reloaded} 个 Agent`)
      fetchAgents()
    } catch {
      message.error('重新加载失败')
    } finally {
      setReloading(false)
    }
  }

  const handleSaveLLM = async () => {
    setSaving(true)
    try {
      const values = await llmForm.validateFields()
      await saveLLMSettings(values)
      message.success('LLM 配置已保存（重启后端生效）')
      fetchHealth()
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const agentColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: 'Tools',
      dataIndex: 'tools',
      key: 'tools',
      render: (tools: string[]) => (
        <Space size={[0, 4]} wrap>
          {tools.slice(0, 3).map((t) => <Tag key={t}>{t}</Tag>)}
          {tools.length > 3 && <Tag>+{tools.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: 'Skills',
      dataIndex: 'skills',
      key: 'skills',
      render: (skills: string[]) => (
        <Space size={[0, 4]} wrap>
          {skills.map((s) => <Tag color="blue" key={s}>{s}</Tag>)}
        </Space>
      ),
    },
    { title: 'Max Turns', dataIndex: 'max_turns', key: 'max_turns', width: 100 },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={4}>设置</Typography.Title>

      <Card
        title="后端状态"
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchHealth} loading={healthLoading} size="small">
            刷新
          </Button>
        }
      >
        {health && (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="状态">
              <Tag color={health.status === 'ok' ? 'green' : 'red'}>{health.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="版本">{health.version}</Descriptions.Item>
            <Descriptions.Item label="LLM 配置">
              <Tag color={health.llm_configured === 'yes' ? 'green' : 'orange'}>
                {health.llm_configured}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="模型">{health.llm_model}</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Card
        title="LLM 配置"
        extra={
          <Button icon={<SaveOutlined />} type="primary" onClick={handleSaveLLM} loading={saving} size="small">
            保存
          </Button>
        }
      >
        <Form form={llmForm} layout="vertical" style={{ maxWidth: 600 }}>
          <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
            修改后保存，重启后端服务即可生效。API Key 以脱敏形式展示，留空或不修改则保持原值。
          </Typography.Text>
          <Form.Item label="API 格式" name="llm_api_format">
            <Select>
              <Select.Option value="openai_compat">OpenAI Compatible</Select.Option>
              <Select.Option value="ollama">Ollama</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="Base URL" name="llm_base_url">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item label="模型" name="llm_model">
            <Input placeholder="gpt-4o / deepseek-chat / ..." />
          </Form.Item>
          <Form.Item label="API Key" name="llm_api_key">
            <Input.Password placeholder="sk-..." />
          </Form.Item>

          <Typography.Text type="secondary" style={{ display: 'block', margin: '16px 0 8px' }}>
            Embedding 配置（留空则复用 LLM 配置）
          </Typography.Text>
          <Form.Item label="Embedding Base URL" name="embedding_base_url">
            <Input placeholder="留空则使用 LLM Base URL" />
          </Form.Item>
          <Form.Item label="Embedding 模型" name="embedding_model">
            <Input placeholder="text-embedding-3-small" />
          </Form.Item>
        </Form>
      </Card>

      <Card
        title="Agent 列表"
        extra={
          <Button icon={<ReloadOutlined />} onClick={handleReload} loading={reloading} size="small">
            重新加载
          </Button>
        }
      >
        <Table
          dataSource={agents}
          columns={agentColumns}
          rowKey="name"
          loading={agentsLoading}
          pagination={false}
          size="small"
        />
      </Card>
    </Space>
  )
}
