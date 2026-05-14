import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ConfigProvider, theme as antdTheme } from 'antd'
import { ProjectProvider } from './context/ProjectContext'
import AppLayout from './layouts/AppLayout'
import Projects from './pages/Projects'
import Workbench from './pages/Workbench'
import Chapters from './pages/Chapters'
import Bible from './pages/Bible'
import PromptStudio from './pages/PromptStudio'
import Settings from './pages/Settings'

function App() {
  return (
    <ConfigProvider theme={{ algorithm: antdTheme.defaultAlgorithm }}>
      <BrowserRouter>
        <ProjectProvider>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/projects" element={<Projects />} />
              <Route path="/workbench/:project" element={<Workbench />} />
              <Route path="/chapters/:project" element={<Chapters />} />
              <Route path="/bible/:project" element={<Bible />} />
              <Route path="/prompts/:project" element={<PromptStudio />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/projects" replace />} />
            </Route>
          </Routes>
        </ProjectProvider>
      </BrowserRouter>
    </ConfigProvider>
  )
}

export default App
