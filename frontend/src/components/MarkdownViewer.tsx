import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Empty, Spin } from 'antd'

interface MarkdownViewerProps {
  content: string
  loading?: boolean
  emptyText?: string
}

export default function MarkdownViewer({ content, loading, emptyText = '暂无内容' }: MarkdownViewerProps) {
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
        <Spin />
      </div>
    )
  }

  if (!content) {
    return <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  return (
    <div className="markdown-viewer" style={{ padding: '0 4px', fontSize: 13, lineHeight: 1.7 }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
