import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  InputNumber,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  FileTextOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  HighlightOutlined,
} from '@ant-design/icons'
import { useParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { usePipeline } from '../hooks/usePipeline'
import { generateChapter, generateOutline, polishChapter, reviewChapter } from '../api'
import TaskHistory from '../components/TaskHistory'

const { TextArea } = Input

export default function Workbench() {
  const { project } = useParams<{ project: string }>()
  const { projectDetail, loading, setCurrentProject, refreshProject } = useProject()
  const { trigger, loading: pipelineLoading } = usePipeline()

  const [chapterNum, setChapterNum] = useState(1)
  const [synopsis, setSynopsis] = useState('')
  const [guidance, setGuidance] = useState('')

  useEffect(() => {
    if (project) setCurrentProject(project)
  }, [project, setCurrentProject])

  const handleGenerateOutline = async () => {
    if (!project || !synopsis.trim()) {
      message.warning('请输入故事梗概')
      return
    }
    const resp = await trigger(() => generateOutline(project, synopsis, guidance))
    message.success(`大纲生成已启动: ${resp.pipeline_id.slice(0, 8)}...`)
    refreshProject()
  }

  const handleGenerateChapter = async () => {
    if (!project) return
    const resp = await trigger(() => generateChapter(project, chapterNum))
    message.success(`第 ${chapterNum} 章生成已启动: ${resp.pipeline_id.slice(0, 8)}...`)
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
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleGenerateOutline}
                loading={pipelineLoading}
                disabled={!synopsis.trim()}
              >
                生成大纲
              </Button>
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
              <Space wrap>
                <Button
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={handleGenerateChapter}
                  loading={pipelineLoading}
                >
                  生成章节
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
    </Space>
  )
}
