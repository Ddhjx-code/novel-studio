import { useCallback, useEffect, useState } from 'react'
import { Button, Space, Tabs, Typography, message } from 'antd'
import { CommentOutlined, HighlightOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { usePipeline } from '../hooks/usePipeline'
import { polishChapter, readPlan, readReview, reviewChapter } from '../api'
import MarkdownViewer from './MarkdownViewer'

interface ReviewPanelProps {
  project: string
  chapterNum: number | null
  onOpenChat?: (agentName: string) => void
}

export default function ReviewPanel({ project, chapterNum, onOpenChat }: ReviewPanelProps) {
  const { trigger, activePipelines, loading } = usePipeline()

  const [planContent, setPlanContent] = useState('')
  const [planLoading, setPlanLoading] = useState(false)
  const [reviewContent, setReviewContent] = useState('')
  const [reviewLoading, setReviewLoading] = useState(false)

  const fetchPlan = useCallback(async () => {
    if (!project || !chapterNum) return
    setPlanLoading(true)
    try {
      const data = await readPlan(project, chapterNum)
      setPlanContent(data.content)
    } catch {
      setPlanContent('')
    } finally {
      setPlanLoading(false)
    }
  }, [project, chapterNum])

  const fetchReview = useCallback(async () => {
    if (!project || !chapterNum) return
    setReviewLoading(true)
    try {
      const data = await readReview(project, chapterNum)
      setReviewContent(data.content)
    } catch {
      setReviewContent('')
    } finally {
      setReviewLoading(false)
    }
  }, [project, chapterNum])

  useEffect(() => {
    setPlanContent('')
    setReviewContent('')
    if (chapterNum) {
      fetchPlan()
      fetchReview()
    }
  }, [chapterNum, fetchPlan, fetchReview])

  const handleReview = async () => {
    if (!chapterNum) return
    const resp = await trigger(() => reviewChapter(project, chapterNum))
    message.success(`审查已启动: ${resp.pipeline_id.slice(0, 8)}...`)
  }

  const handlePolish = async () => {
    if (!chapterNum) return
    const resp = await trigger(() => polishChapter(project, chapterNum))
    message.success(`润色已启动: ${resp.pipeline_id.slice(0, 8)}...`)
  }

  const pipelineList = Array.from(activePipelines.entries())

  const tabItems = [
    {
      key: 'plan',
      label: '规划',
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <Space style={{ marginBottom: 8 }}>
            <Button
              icon={<ReloadOutlined />}
              size="small"
              onClick={fetchPlan}
              loading={planLoading}
              disabled={!chapterNum}
            >
              刷新
            </Button>
            <Button
              icon={<CommentOutlined />}
              size="small"
              onClick={() => onOpenChat?.('planner')}
              disabled={!chapterNum}
            >
              讨论
            </Button>
          </Space>
          <div style={{ flex: 1, overflow: 'auto' }}>
            <MarkdownViewer
              content={planContent}
              loading={planLoading}
              emptyText="暂无规划，请先生成章节"
            />
          </div>
        </div>
      ),
    },
    {
      key: 'review',
      label: '审查',
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <Space style={{ marginBottom: 8 }}>
            <Button
              icon={<SearchOutlined />}
              size="small"
              onClick={handleReview}
              loading={loading}
              disabled={!chapterNum}
            >
              启动审查
            </Button>
            <Button
              icon={<ReloadOutlined />}
              size="small"
              onClick={fetchReview}
              loading={reviewLoading}
              disabled={!chapterNum}
            >
              刷新
            </Button>
            <Button
              icon={<CommentOutlined />}
              size="small"
              onClick={() => onOpenChat?.('reviewer')}
              disabled={!chapterNum}
            >
              讨论
            </Button>
          </Space>
          <div style={{ flex: 1, overflow: 'auto' }}>
            <MarkdownViewer
              content={reviewContent}
              loading={reviewLoading}
              emptyText="暂无审查报告"
            />
          </div>
        </div>
      ),
    },
    {
      key: 'actions',
      label: '操作',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button
            icon={<SearchOutlined />}
            onClick={handleReview}
            loading={loading}
            disabled={!chapterNum}
            block
          >
            启动审查
          </Button>
          <Button
            icon={<HighlightOutlined />}
            onClick={handlePolish}
            loading={loading}
            disabled={!chapterNum}
            block
          >
            启动润色
          </Button>
          <Button
            icon={<CommentOutlined />}
            onClick={() => onOpenChat?.('writer')}
            disabled={!chapterNum}
            block
          >
            与写手讨论
          </Button>
          {pipelineList.length > 0 && (
            <Typography.Text type="secondary">
              活跃任务: {pipelineList.length}
            </Typography.Text>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '0 12px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Typography.Title level={5} style={{ margin: '8px 0' }}>辅助面板</Typography.Title>
      {!chapterNum ? (
        <Typography.Text type="secondary">请先选择章节</Typography.Text>
      ) : (
        <Tabs
          items={tabItems}
          size="small"
          style={{ flex: 1, minHeight: 0 }}
        />
      )}
    </div>
  )
}
