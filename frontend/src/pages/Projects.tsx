import { useCallback, useEffect, useState } from 'react'
import { Button, Form, Input, Modal, Space, Table, Typography, message } from 'antd'
import { PlusOutlined, RightOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { createProject, getProject, listProjects } from '../api'
import { useProject } from '../context/ProjectContext'
import type { Project } from '../types'

interface ProjectRow {
  name: string
  chapters: number
  has_outline: boolean
}

export default function Projects() {
  const [rows, setRows] = useState<ProjectRow[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm<{ name: string }>()
  const navigate = useNavigate()
  const { setCurrentProject } = useProject()

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    try {
      const { projects } = await listProjects()
      const details = await Promise.all(
        projects.map(async (name) => {
          try {
            const detail: Project = await getProject(name)
            return { name, chapters: detail.chapters.length, has_outline: detail.has_outline }
          } catch {
            return { name, chapters: 0, has_outline: false }
          }
        }),
      )
      setRows(details)
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载项目列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      setCreating(true)
      await createProject(values.name)
      message.success(`项目 "${values.name}" 创建成功`)
      setModalOpen(false)
      form.resetFields()
      fetchProjects()
    } catch (err) {
      if (err && typeof err === 'object' && 'errorFields' in err) return
      message.error(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleEnter = (name: string) => {
    setCurrentProject(name)
    navigate(`/workbench/${name}`)
  }

  const columns = [
    { title: '项目名称', dataIndex: 'name', key: 'name' },
    { title: '章节数', dataIndex: 'chapters', key: 'chapters', width: 100 },
    {
      title: '大纲',
      dataIndex: 'has_outline',
      key: 'has_outline',
      width: 80,
      render: (v: boolean) => (v ? '已有' : '无'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: ProjectRow) => (
        <Button
          type="link"
          icon={<RightOutlined />}
          onClick={() => handleEnter(record.name)}
        >
          进入
        </Button>
      ),
    },
  ]

  return (
    <>
      <Space style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          项目列表
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建项目
        </Button>
      </Space>

      <Table
        dataSource={rows}
        columns={columns}
        rowKey="name"
        loading={loading}
        pagination={false}
      />

      <Modal
        title="新建项目"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="项目名称"
            rules={[
              { required: true, message: '请输入项目名称' },
              { pattern: /^[a-z0-9-]+$/, message: '仅支持小写字母、数字和连字符' },
            ]}
          >
            <Input placeholder="my-novel" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
