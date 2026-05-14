import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Form, Input, Modal, Popconfirm, Space, Spin, Typography, message } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import Editor from '@monaco-editor/react'
import { useParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { deleteBibleFile, getBibleTree, readBibleFile, saveBibleFile } from '../api'
import FileTree from '../components/FileTree'

export default function Bible() {
  const { project } = useParams<{ project: string }>()
  const { setCurrentProject } = useProject()
  const [files, setFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm<{ path: string }>()
  const editorRef = useRef<unknown>(null)

  useEffect(() => {
    if (project) setCurrentProject(project)
  }, [project, setCurrentProject])

  const fetchTree = useCallback(async () => {
    if (!project) return
    try {
      const resp = await getBibleTree(project)
      setFiles(resp.files)
    } catch {
      message.error('加载文件列表失败')
    }
  }, [project])

  useEffect(() => {
    fetchTree()
  }, [fetchTree])

  const handleSelectFile = useCallback(async (path: string) => {
    if (!project) return
    const isFile = !files.some((f) => f.startsWith(path + '/') && f !== path)
    const isActualFile = files.includes(path)
    if (!isActualFile && !isFile) return

    setLoading(true)
    try {
      const data = await readBibleFile(project, path)
      setContent(data.content)
      setSelectedFile(path)
    } catch {
      message.error('加载文件失败')
    } finally {
      setLoading(false)
    }
  }, [project, files])

  const handleSave = useCallback(async () => {
    if (!project || !selectedFile) return
    setSaving(true)
    try {
      await saveBibleFile(project, selectedFile, content)
      message.success('保存成功')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }, [project, selectedFile, content])

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

  const handleCreateFile = async () => {
    if (!project) return
    try {
      const values = await form.validateFields()
      const path = values.path.startsWith('bible/') ? values.path : `bible/${values.path}`
      await saveBibleFile(project, path, '')
      message.success('文件已创建')
      setModalOpen(false)
      form.resetFields()
      fetchTree()
    } catch (err) {
      if (err && typeof err === 'object' && 'errorFields' in err) return
      message.error('创建失败')
    }
  }

  const handleDeleteFile = async () => {
    if (!project || !selectedFile) return
    try {
      await deleteBibleFile(project, selectedFile)
      message.success('已删除')
      setSelectedFile(null)
      setContent('')
      fetchTree()
    } catch {
      message.error('删除失败')
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 128px)' }}>
      {/* Left: File tree */}
      <div style={{ width: 260, borderRight: '1px solid #f0f0f0', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
          <Button icon={<PlusOutlined />} size="small" block onClick={() => setModalOpen(true)}>
            新建文件
          </Button>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <FileTree files={files} selectedFile={selectedFile} onSelect={handleSelectFile} />
        </div>
      </div>

      {/* Right: Monaco editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Typography.Text strong>
            {selectedFile ?? '请选择文件'}
          </Typography.Text>
          {saving && <Spin size="small" />}
          {selectedFile && (
            <>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                Ctrl+S 保存
              </Typography.Text>
              <Space style={{ marginLeft: 'auto' }}>
                <Popconfirm title="确定删除该文件？" onConfirm={handleDeleteFile} okText="删除" cancelText="取消">
                  <Button icon={<DeleteOutlined />} size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            </>
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

      <Modal
        title="新建 Bible 文件"
        open={modalOpen}
        onOk={handleCreateFile}
        onCancel={() => setModalOpen(false)}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="path"
            label="文件路径"
            rules={[{ required: true, message: '请输入文件路径' }]}
            help="例如: characters/新角色.md 或 worldbuilding/魔法体系.md"
          >
            <Input placeholder="characters/新角色.md" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
