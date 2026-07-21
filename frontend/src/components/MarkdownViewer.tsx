import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Empty, Spin, Result, Button } from 'antd'

interface MarkdownViewerProps {
  content: string
  loading?: boolean
  emptyText?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  errorMsg: string
}

class MarkdownErrorBoundary extends React.Component<
  { children: React.ReactNode; onRetry: () => void },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode; onRetry: () => void }) {
    super(props)
    this.state = { hasError: false, errorMsg: '' }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, errorMsg: error.message || 'Unknown render error' }
  }

  componentDidCatch(error: Error) {
    console.error('[MarkdownViewer] Render crashed:', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <Result
          status="warning"
          title="内容渲染失败"
          subTitle={this.state.errorMsg.slice(0, 120)}
          extra={
            <Button size="small" onClick={this.props.onRetry}>
              重试
            </Button>
          }
        />
      )
    }
    return this.props.children
  }
}

export default function MarkdownViewer({
  content,
  loading,
  emptyText = '暂无内容',
}: MarkdownViewerProps) {
  const [renderKey, setRenderKey] = React.useState(0)

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
      <MarkdownErrorBoundary
        key={renderKey}
        onRetry={() => setRenderKey((k) => k + 1)}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </MarkdownErrorBoundary>
    </div>
  )
}
