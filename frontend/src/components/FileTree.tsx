import { useMemo } from 'react'
import { Tree, Empty } from 'antd'
import { FileTextOutlined, FolderOutlined } from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'

interface FileTreeProps {
  files: string[]
  selectedFile: string | null
  onSelect: (path: string) => void
}

interface TreeBuildNode extends DataNode {
  _childMap?: Record<string, TreeBuildNode>
}

function buildTreeData(files: string[]): DataNode[] {
  const root: Record<string, TreeBuildNode> = {}

  for (const filePath of files) {
    const parts = filePath.split('/')
    let current = root
    let keyPrefix = ''

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      keyPrefix = keyPrefix ? `${keyPrefix}/${part}` : part
      const isLeaf = i === parts.length - 1

      if (!current[part]) {
        current[part] = {
          key: keyPrefix,
          title: part,
          icon: isLeaf ? <FileTextOutlined /> : <FolderOutlined />,
          isLeaf,
          children: isLeaf ? undefined : [],
        }
      }

      if (!isLeaf) {
        const parentNode = current[part]
        if (!parentNode._childMap) {
          parentNode._childMap = {}
        }
        current = parentNode._childMap
      }
    }
  }

  function collectChildren(map: Record<string, TreeBuildNode>): DataNode[] {
    return Object.values(map)
      .sort((a, b) => {
        if (a.isLeaf !== b.isLeaf) return a.isLeaf ? 1 : -1
        return String(a.title).localeCompare(String(b.title))
      })
      .map((node): DataNode => {
        const { _childMap, ...rest } = node
        if (!node.isLeaf && _childMap) {
          return { ...rest, children: collectChildren(_childMap) }
        }
        return rest
      })
  }

  return collectChildren(root)
}

export default function FileTree({ files, selectedFile, onSelect }: FileTreeProps) {
  const treeData = useMemo(() => buildTreeData(files), [files])

  if (files.length === 0) {
    return <Empty description="暂无文件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  return (
    <Tree
      showIcon
      defaultExpandAll
      selectedKeys={selectedFile ? [selectedFile] : []}
      treeData={treeData}
      onSelect={(keys) => {
        const key = keys[0] as string | undefined
        if (key) onSelect(key)
      }}
      style={{ padding: '8px 0' }}
    />
  )
}
