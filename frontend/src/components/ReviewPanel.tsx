import { Button, Space, Tabs, Typography, message } from 'antd'
import { HighlightOutlined, SearchOutlined } from '@ant-design/icons'
import { usePipeline } from '../hooks/usePipeline'
import { polishChapter, reviewChapter } from '../api'

interface ReviewPanelProps {
  project: string
  chapterNum: number | null
}

export default function ReviewPanel({ project, chapterNum }: ReviewPanelProps) {
  const { trigger, activePipelines, loading } = usePipeline()

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
      key: 'review',
      label: '审查',
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
          {pipelineList.length > 0 && (
            <Typography.Text type="secondary">
              活跃任务: {pipelineList.length}
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      key: 'polish',
      label: '润色',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button
            icon={<HighlightOutlined />}
            onClick={handlePolish}
            loading={loading}
            disabled={!chapterNum}
            block
          >
            启动润色
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '0 12px' }}>
      <Typography.Title level={5}>操作面板</Typography.Title>
      {!chapterNum ? (
        <Typography.Text type="secondary">请先选择章节</Typography.Text>
      ) : (
        <Tabs items={tabItems} size="small" />
      )}
    </div>
  )
}
