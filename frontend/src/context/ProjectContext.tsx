import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getProject } from '../api'
import type { Project } from '../types'

interface ProjectContextValue {
  currentProject: string | null
  projectDetail: Project | null
  loading: boolean
  setCurrentProject: (name: string | null) => void
  refreshProject: () => Promise<void>
}

const ProjectContext = createContext<ProjectContextValue>({
  currentProject: null,
  projectDetail: null,
  loading: false,
  setCurrentProject: () => {},
  refreshProject: async () => {},
})

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [currentProject, setCurrentProject] = useState<string | null>(null)
  const [projectDetail, setProjectDetail] = useState<Project | null>(null)
  const [loading, setLoading] = useState(false)

  const refreshProject = useCallback(async () => {
    if (!currentProject) {
      setProjectDetail(null)
      return
    }
    setLoading(true)
    try {
      const detail = await getProject(currentProject)
      setProjectDetail(detail)
    } catch {
      setProjectDetail(null)
    } finally {
      setLoading(false)
    }
  }, [currentProject])

  useEffect(() => {
    refreshProject()
  }, [refreshProject])

  return (
    <ProjectContext.Provider
      value={{ currentProject, projectDetail, loading, setCurrentProject, refreshProject }}
    >
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject() {
  return useContext(ProjectContext)
}
