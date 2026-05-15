import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Input,
  InputNumber,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CommentOutlined,
  FileTextOutlined,
  HighlightOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { usePipeline } from '../hooks/usePipeline'
import { generateChapter, generateOutline, polishChapter, reviewChapter } from '../api'
import ChatPanel from '../components/ChatPanel'
import TaskHistory from '../components/TaskHistory'

const { TextArea } = Input

export default function Workbench() {
  const { project } = useParams<{ project: string }>()
  const { projectDetail, loading, setCurrentProject, refreshProject } = useProject()
  const { trigger, loading: pipelineLoading } = usePipeline()

  const [chapterNum, setChapterNum] = useState(1)
  const [synopsis, setSynopsis] = useState('')
  const [guidance, setGuidance] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatAgent, setChatAgent] = useState<string | null>(null)

  useEffect(() => {
    if (project) setCurrentProject(project)
  }, [project, setCurrentProject])

  const handleOpenChat = useCallback((agentName: string) => {
    setChatAgent(agentName)
    setChatOpen(true)
  }, [])

  const handleGenerateOutline = async () => {
    if (!project || !synopsis.trim()) {
      message.warning('请输入故事梗概')
      return
    }
    const resp = await trigger(() => generateOutline(project, synopsis, guidance))
    message.success(`大纲生成已启动: ${resp.pipeline_id.slice(0, 8)}...`)
    refreshProject()
  }

  const handleGeneratePlan = async () => {
    if (!project) return
    const resp = await trigger(() => generateChapter(project, chapterNum, ['A', 'B']))
    message.success(`第 ${chapterNum} 章规划已启动: ${resp.pipeline_id.slice(0, 8)}...`)
  }

  const handleGenerateWrite = async () => {
    if (!project) return
    const resp = await trigger(() => generateChapter(project, chapterNum, ['C', 'D', 'E', 'F']))
    message.success(`第 ${chapterNum} 章写作已启动: ${resp.pipeline_id.slice(0, 8)}...`)
  }

  const handleGenerateFull = async () => {
    if (!project) return
    const resp = await trigger(() => generateChapter(project, chapterNum))
    message.success(`第 ${chapterNum} 章完整生成已启动: ${resp.pipeline_id.slice(0, 8)}...`)
  }

  const handleReview = async () => {
    if (!project) return
    const resp = await trigger(() => reviewChapter(project, chapterNum))
    message.success(`第 ${chapterNum} 章审查已启动: ${resp.pipeline_id.slice(0, 8)}...`)
  }

  const handlePolish = async () => {
    if (!project) return
    const resp = await trigger(() => polishChapter(project, chapterNum))
    message.success(`第 ${chapterNum} 章润色已启动: ${resp.pipeline_id.slice(0, 8)}...`)
  }

  if (loading || !projectDetail) {
    return <Card loading />
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={4}>工作台 — {project}</Typography.Title>

      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="项目名称">{projectDetail.name}</Descriptions.Item>
        <Descriptions.Item label="章节数">{projectDetail.chapters.length}</Descriptions.Item>
        <Descriptions.Item label="大纲">
          <Tag color={projectDetail.has_outline ? 'green' : 'default'}>
            {projectDetail.has_outline ? '已生成' : '未生成'}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="全局摘要">
          {projectDetail.global_summary_length > 0
            ? `${projectDetail.global_summary_length} 字`
            : '无'}
        </Descriptions.Item>
        <Descriptions.Item label="角色状态">
          {projectDetail.character_state_length > 0
            ? `${projectDetail.character_state_length} 字`
            : '无'}
        </Descriptions.Item>
      </Descriptions>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title={<><FileTextOutlined /> 生成大纲</>}
            size="small"
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <TextArea
                placeholder="请输入故事梗概..."
                rows={3}
                value={synopsis}
                onChange={(e) => setSynopsis(e.target.value)}
              />
              <Input
                placeholder="补充指导（可选）"
                value={guidance}
                onChange={(e) => setGuidance(e.target.value)}
              />
              <Space wrap>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleGenerateOutline}
                  loading={pipelineLoading}
                  disabled={!synopsis.trim()}
                >
                  生成大纲
                </Button>
                <Button
                  icon={<CommentOutlined />}
                  onClick={() => handleOpenChat('planner')}
                  disabled={!projectDetail.has_outline}
                >
                  讨论大纲
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title={<><PlayCircleOutlined /> 生成章节</>}
            size="small"
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space>
                <Typography.Text>章节号：</Typography.Text>
                <InputNumber min={1} value={chapterNum} onChange={(v) => setChapterNum(v ?? 1)} />
              </Space>

              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                分步生成：先生成规划 → 讨论确认 → 再开始写作
              </Typography.Text>

              <Space wrap>
                <Button
                  type="primary"
                  icon={<FileTextOutlined />}
                  onClick={handleGeneratePlan}
                  loading={pipelineLoading}
                >
                  生成规划
                </Button>
                <Button
                  icon={<CommentOutlined />}
                  onClick={() => handleOpenChat('planner')}
                >
                  讨论规划
                </Button>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleGenerateWrite}
                  loading={pipelineLoading}
                >
                  开始写作
                </Button>
              </Space>

              <Divider style={{ margin: '8px 0' }} />

              <Space wrap>
                <Button
                  icon={<ThunderboltOutlined />}
                  onClick={handleGenerateFull}
                  loading={pipelineLoading}
                >
                  完整生成
                </Button>
                <Button
                  icon={<SearchOutlined />}
                  onClick={handleReview}
                  loading={pipelineLoading}
                >
                  审查
                </Button>
                <Button
                  icon={<HighlightOutlined />}
                  onClick={handlePolish}
                  loading={pipelineLoading}
                >
                  润色
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>

      {project && (
        <Card title="任务历史" size="small">
          <TaskHistory project={project} />
        </Card>
      )}

      <ChatPanel
        open={chatOpen}
        agentName={chatAgent}
        project={project ?? ''}
        chapterNum={chapterNum}
        onClose={() => setChatOpen(false)}
      />
    </Space>
  )
}
