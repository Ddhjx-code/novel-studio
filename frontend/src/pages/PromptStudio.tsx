import { useCallback, useEffect, useRef, useState } from 'react'
import { Spin, Typography, message } from 'antd'
import Editor from '@monaco-editor/react'
import { useParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import {
  getPromptAgent,
  getPromptSkillFile,
  listPromptAgents,
  listPromptSkills,
  savePromptAgent,
  savePromptSkillFile,
} from '../api'
import PromptList from '../components/PromptList'

interface AgentEntry {
  name: string
  description: string
}

interface SkillEntry {
  name: string
  files: string[]
}

type ActiveItem =
  | { type: 'agent'; name: string }
  | { type: 'skill'; skill: string; file: string }

export default function PromptStudio() {
  const { project } = useParams<{ project: string }>()
  const { setCurrentProject } = useProject()
  const [agents, setAgents] = useState<AgentEntry[]>([])
  const [skills, setSkills] = useState<SkillEntry[]>([])
  const [activeItem, setActiveItem] = useState<ActiveItem | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const editorRef = useRef<unknown>(null)

  useEffect(() => {
    if (project) setCurrentProject(project)
  }, [project, setCurrentProject])

  const fetchLists = useCallback(async () => {
    try {
      const [agentsResp, skillsResp] = await Promise.all([listPromptAgents(), listPromptSkills()])
      setAgents(agentsResp.agents)
      setSkills(skillsResp.skills)
    } catch {
      message.error('加载列表失败')
    }
  }, [])

  useEffect(() => {
    fetchLists()
  }, [fetchLists])

  const handleSelectAgent = useCallback(async (name: string) => {
    setLoading(true)
    try {
      const data = await getPromptAgent(name)
      setContent(data.content)
      setActiveItem({ type: 'agent', name })
    } catch {
      message.error('加载 Agent 失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSelectSkillFile = useCallback(async (skill: string, file: string) => {
    setLoading(true)
    try {
      const data = await getPromptSkillFile(skill, file)
      setContent(data.content)
      setActiveItem({ type: 'skill', skill, file })
    } catch {
      message.error('加载文件失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSave = useCallback(async () => {
    if (!activeItem) return
    setSaving(true)
    try {
      if (activeItem.type === 'agent') {
        await savePromptAgent(activeItem.name, content)
        message.success('Agent 已保存并重新加载')
      } else {
        await savePromptSkillFile(activeItem.skill, activeItem.file, content)
        message.success('Skill 文件已保存')
      }
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }, [activeItem, content])

  const handleEditorMount = (editor: unknown) => {
    editorRef.current = editor
    const monacoEditor = editor as { addCommand: (keybinding: number, handler: () => void) => void }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const monaco = (window as any).monaco
    if (monaco) {
      monacoEditor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        handleSave()
      })
    }
  }

  const selectedKey = activeItem
    ? activeItem.type === 'agent'
      ? `agent:${activeItem.name}`
      : `skill:${activeItem.skill}:${activeItem.file}`
    : null

  const headerLabel = activeItem
    ? activeItem.type === 'agent'
      ? `Agent: ${activeItem.name}.md`
      : `Skill: ${activeItem.skill}/${activeItem.file}`
    : '请选择文件'

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 128px)' }}>
      {/* Left: Prompt list */}
      <div style={{ width: 280, borderRight: '1px solid #f0f0f0', overflow: 'auto' }}>
        <PromptList
          agents={agents}
          skills={skills}
          selectedKey={selectedKey}
          onSelectAgent={handleSelectAgent}
          onSelectSkillFile={handleSelectSkillFile}
        />
      </div>

      {/* Right: Monaco editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Typography.Text strong>{headerLabel}</Typography.Text>
          {saving && <Spin size="small" />}
          {activeItem && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Ctrl+S 保存
            </Typography.Text>
          )}
        </div>
        <div style={{ flex: 1 }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <Spin />
            </div>
          ) : (
            <Editor
              language="markdown"
              value={content}
              onChange={(v) => setContent(v ?? '')}
              onMount={handleEditorMount}
              options={{
                minimap: { enabled: false },
                wordWrap: 'on',
                fontSize: 14,
                padding: { top: 16 },
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
