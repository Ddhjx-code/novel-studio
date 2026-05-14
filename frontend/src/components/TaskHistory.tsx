import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Table, Tag, Tooltip, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { listTasks, retryTask } from '../api'
import type { TaskCard, TaskKind, TaskStatus } from '../types'

interface TaskHistoryProps {
  project: string
}

const KIND_LABELS: Record<TaskKind, string> = {
  chapter_generate: '章节生成',
  outline_generate: '大纲生成',
  chapter_review: '章节审查',
  chapter_polish: '章节润色',
}

const KIND_COLORS: Record<TaskKind, string> = {
  chapter_generate: 'blue',
  outline_generate: 'purple',
  chapter_review: 'cyan',
  chapter_polish: 'geekblue',
}

const STATUS_COLORS: Record<TaskStatus, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso
  }
}

export default function TaskHistory({ project }: TaskHistoryProps) {
  const [tasks, setTasks] = useState<TaskCard[]>([])
  const [loading, setLoading] = useState(false)
  const [retrying, setRetrying] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchTasks = useCallback(async () => {
    try {
      const resp = await listTasks(project)
      setTasks(resp.tasks)
    } catch {
      /* silent on poll failure */
    }
  }, [project])

  useEffect(() => {
    setLoading(true)
    fetchTasks().finally(() => setLoading(false))
  }, [fetchTasks])

  useEffect(() => {
    const hasRunning = tasks.some((t) => t.status === 'running' || t.status === 'pending')
    if (hasRunning) {
      timerRef.current = setInterval(fetchTasks, 5000)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [tasks, fetchTasks])

  const handleRetry = async (taskId: string) => {
    setRetrying(taskId)
    try {
      const resp = await retryTask(project, taskId)
      message.success(`重试已启动: ${resp.pipeline_id.slice(0, 8)}...`)
      fetchTasks()
    } catch {
      message.error('重试失败')
    } finally {
      setRetrying(null)
    }
  }

  const columns: ColumnsType<TaskCard> = [
    {
      title: '类型',
      dataIndex: 'kind',
      width: 100,
      render: (kind: TaskKind) => (
        <Tag color={KIND_COLORS[kind]}>{KIND_LABELS[kind]}</Tag>
      ),
    },
    {
      title: '章节',
      dataIndex: 'chapter_num',
      width: 60,
      render: (n: number | null) => n ?? '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (status: TaskStatus) => (
        <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>
      ),
    },
    {
      title: '进度',
      key: 'progress',
      width: 120,
      render: (_: unknown, record: TaskCard) => {
        if (!record.steps_requested.length) return '-'
        return `${record.steps_completed.length}/${record.steps_requested.length}`
      },
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 140,
      render: (ts: string) => formatTime(ts),
    },
    {
      title: '错误',
      dataIndex: 'error',
      ellipsis: true,
      render: (err: string | null) =>
        err ? (
          <Tooltip title={err}>
            <span style={{ color: '#ff4d4f' }}>{err.slice(0, 40)}{err.length > 40 ? '...' : ''}</span>
          </Tooltip>
        ) : null,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: TaskCard) => {
        if (record.status === 'failed' || record.status === 'cancelled') {
          return (
            <Button
              size="small"
              icon={<ReloadOutlined />}
              loading={retrying === record.id}
              onClick={() => handleRetry(record.id)}
            >
              重试
            </Button>
          )
        }
        return null
      },
    },
  ]

  return (
    <Table<TaskCard>
      columns={columns}
      dataSource={tasks}
      rowKey="id"
      size="small"
      loading={loading}
      pagination={{ pageSize: 10, hideOnSinglePage: true }}
    />
  )
}
