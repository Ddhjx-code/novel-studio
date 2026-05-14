import { useCallback, useEffect, useRef, useState } from 'react'
import { Spin, Typography, message } from 'antd'
import Editor from '@monaco-editor/react'
import { useParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { readChapter, saveChapter } from '../api'
import ChapterList from '../components/ChapterList'
import ReviewPanel from '../components/ReviewPanel'

export default function Chapters() {
  const { project } = useParams<{ project: string }>()
  const { projectDetail, setCurrentProject } = useProject()
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const editorRef = useRef<unknown>(null)

  useEffect(() => {
    if (project) setCurrentProject(project)
  }, [project, setCurrentProject])

  const loadChapter = useCallback(async (n: number) => {
    if (!project) return
    setLoading(true)
    try {
      const data = await readChapter(project, n)
      setContent(data.content)
      setSelectedChapter(n)
    } catch {
      message.error(`加载第 ${n} 章失败`)
    } finally {
      setLoading(false)
    }
  }, [project])

  const handleSave = useCallback(async () => {
    if (!project || !selectedChapter) return
    setSaving(true)
    try {
      await saveChapter(project, selectedChapter, content)
      message.success('保存成功')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }, [project, selectedChapter, content])

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

  const chapters = projectDetail?.chapters ?? []

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 128px)', gap: 0 }}>
      {/* Left: Chapter list */}
      <div style={{ width: 200, borderRight: '1px solid #f0f0f0', overflow: 'auto' }}>
        <ChapterList
          chapters={chapters}
          selectedChapter={selectedChapter}
          onSelect={loadChapter}
        />
      </div>

      {/* Center: Monaco editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Typography.Text strong>
            {selectedChapter ? `第 ${selectedChapter} 章` : '请选择章节'}
          </Typography.Text>
          {saving && <Spin size="small" />}
          {selectedChapter && (
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
                lineNumbers: 'off',
                padding: { top: 16 },
              }}
            />
          )}
        </div>
      </div>

      {/* Right: Review panel */}
      <div style={{ width: 300, borderLeft: '1px solid #f0f0f0', overflow: 'auto' }}>
        <ReviewPanel project={project ?? ''} chapterNum={selectedChapter} />
      </div>
    </div>
  )
}
