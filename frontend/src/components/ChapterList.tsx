import { Menu, Empty, Tag } from 'antd'
import { EditOutlined, FileTextOutlined } from '@ant-design/icons'

interface ChapterListProps {
  chapters: number[]
  plannedChapters?: number[]
  selectedChapter: number | null
  onSelect: (n: number) => void
}

export default function ChapterList({ chapters, plannedChapters = [], selectedChapter, onSelect }: ChapterListProps) {
  const allNums = [...new Set([...chapters, ...plannedChapters])].sort((a, b) => a - b)

  if (allNums.length === 0) {
    return <Empty description="暂无章节" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  const writtenSet = new Set(chapters)

  const items = allNums.map((n) => {
    const hasText = writtenSet.has(n)
    return {
      key: String(n),
      icon: hasText ? <FileTextOutlined /> : <EditOutlined />,
      label: hasText
        ? `第 ${n} 章`
        : <span>第 {n} 章 <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>规划中</Tag></span>,
    }
  })

  return (
    <Menu
      mode="inline"
      selectedKeys={selectedChapter ? [String(selectedChapter)] : []}
      items={items}
      onClick={({ key }) => onSelect(Number(key))}
      style={{ height: '100%', borderRight: 0 }}
    />
  )
}
