import { useEffect, useState } from 'react'
import { Layout, Menu, Typography } from 'antd'
import {
  BookOutlined,
  DashboardOutlined,
  EditOutlined,
  ProjectOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'

const { Sider, Content, Header } = Layout
const { Title } = Typography

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const params = useParams<{ project?: string }>()
  const { currentProject, setCurrentProject } = useProject()

  useEffect(() => {
    if (params.project && params.project !== currentProject) {
      setCurrentProject(params.project)
    }
  }, [params.project, currentProject, setCurrentProject])

  const selectedKey = (() => {
    if (location.pathname.startsWith('/workbench')) return 'workbench'
    if (location.pathname.startsWith('/chapters')) return 'chapters'
    if (location.pathname.startsWith('/settings')) return 'settings'
    return 'projects'
  })()

  const menuItems = [
    { key: 'projects', icon: <ProjectOutlined />, label: '项目列表' },
    {
      key: 'workbench',
      icon: <DashboardOutlined />,
      label: '工作台',
      disabled: !currentProject,
    },
    {
      key: 'chapters',
      icon: <EditOutlined />,
      label: '章节编辑',
      disabled: !currentProject,
    },
    { key: 'settings', icon: <SettingOutlined />, label: '设置' },
  ]

  const handleMenuClick = ({ key }: { key: string }) => {
    switch (key) {
      case 'projects':
        navigate('/projects')
        break
      case 'workbench':
        if (currentProject) navigate(`/workbench/${currentProject}`)
        break
      case 'chapters':
        if (currentProject) navigate(`/chapters/${currentProject}`)
        break
      case 'settings':
        navigate('/settings')
        break
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ padding: '16px', textAlign: 'center' }}>
          <BookOutlined style={{ fontSize: 24, color: '#fff' }} />
          {!collapsed && (
            <Title level={5} style={{ color: '#fff', margin: '8px 0 0' }}>
              Novel Studio
            </Title>
          )}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
          {currentProject && (
            <Typography.Text type="secondary">
              当前项目：<Typography.Text strong>{currentProject}</Typography.Text>
            </Typography.Text>
          )}
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
