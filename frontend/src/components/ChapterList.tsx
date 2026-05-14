import { Menu, Empty } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'

interface ChapterListProps {
  chapters: number[]
  selectedChapter: number | null
  onSelect: (n: number) => void
}

export default function ChapterList({ chapters, selectedChapter, onSelect }: ChapterListProps) {
  if (chapters.length === 0) {
    return <Empty description="暂无章节" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  const items = chapters.map((n) => ({
    key: String(n),
    icon: <FileTextOutlined />,
    label: `第 ${n} 章`,
  }))

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
