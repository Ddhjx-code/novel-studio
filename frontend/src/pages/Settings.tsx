import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Descriptions, Space, Table, Tag, Typography, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { getHealth, listAgents, reloadAgents, type HealthResponse } from '../api'
import type { AgentInfo } from '../types'

export default function Settings() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [agentsLoading, setAgentsLoading] = useState(false)
  const [reloading, setReloading] = useState(false)

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

  useEffect(() => {
    fetchHealth()
    fetchAgents()
  }, [fetchHealth, fetchAgents])

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
