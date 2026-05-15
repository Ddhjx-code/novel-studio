import { Menu } from 'antd'
import { CodeOutlined, FileTextOutlined, FolderOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'

interface AgentEntry {
  name: string
  description: string
}

interface SkillEntry {
  name: string
  files: string[]
}

interface PromptListProps {
  agents: AgentEntry[]
  skills: SkillEntry[]
  selectedKey: string | null
  onSelectAgent: (name: string) => void
  onSelectSkillFile: (skill: string, file: string) => void
}

export default function PromptList({
  agents,
  skills,
  selectedKey,
  onSelectAgent,
  onSelectSkillFile,
}: PromptListProps) {
  const agentItems: MenuProps['items'] = agents.map((a) => ({
    key: `agent:${a.name}`,
    icon: <CodeOutlined />,
    label: a.name,
  }))

  const skillItems: MenuProps['items'] = skills.map((s) => ({
    key: `skill-group:${s.name}`,
    icon: <FolderOutlined />,
    label: s.name,
    children: s.files.map((f) => ({
      key: `skill:${s.name}:${f}`,
      icon: <FileTextOutlined />,
      label: f,
    })),
  }))

  const menuItems: MenuProps['items'] = [
    { key: 'group-agents', label: 'Agents', type: 'group', children: agentItems },
    { key: 'group-skills', label: 'Skills', type: 'group', children: skillItems },
  ]

  const handleClick: MenuProps['onClick'] = ({ key }) => {
    if (key.startsWith('agent:')) {
      onSelectAgent(key.slice(6))
    } else if (key.startsWith('skill:')) {
      const parts = key.slice(6).split(':')
      const skill = parts[0]
      const file = parts.slice(1).join(':')
      onSelectSkillFile(skill, file)
    }
  }

  return (
    <Menu
      mode="inline"
      selectedKeys={selectedKey ? [selectedKey] : []}
      openKeys={skills.map((s) => `skill-group:${s.name}`)}
      items={menuItems}
      onClick={handleClick}
      style={{ height: '100%', borderRight: 0 }}
    />
  )
}
