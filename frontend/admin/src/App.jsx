import { AdminProvider, useAdmin } from './context/AdminContext'
import Sidebar from './components/layout/Sidebar'
import Topbar from './components/layout/Topbar'
import ToastContainer from './components/ui/Toast'
import CreateUserModal from './components/modals/CreateUserModal'
import StudentProfileModal from './components/modals/StudentProfileModal'
import FaceEnrollModal from './components/modals/FaceEnrollModal'
import { ConfirmDeleteModal, ConfirmRemoveFaceModal } from './components/modals/ConfirmModal'
import FaceReviewPromoteModal from './components/modals/FaceReviewPromoteModal'
import CourseDetailModal from './components/modals/CourseDetailModal'
import Login from './views/Login'
import Dashboard from './views/Dashboard'
import StudentsView from './views/StudentsView'
import LecturersView from './views/LecturersView'
import FaceReviewView from './views/FaceReviewView'
import EnvironmentView from './views/EnvironmentView'
import AuditLogView from './views/AuditLogView'
import ClassManagementView from './views/ClassManagementView'

const VIEWS = {
  dashboard:       Dashboard,
  students:        StudentsView,
  lecturers:       LecturersView,
  classmanagement: ClassManagementView,
  facereview:      FaceReviewView,
  environment:     EnvironmentView,
  audit:           AuditLogView,
}

function AppShell() {
  const { state } = useAdmin()

  if (state.restoring) return null

  if (!state.isLoggedIn) {
    return (
      <>
        <Login />
        <ToastContainer />
      </>
    )
  }

  const ActiveView = VIEWS[state.currentView] ?? Dashboard

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-7">
          <ActiveView />
        </main>
      </div>

      {/* Modals — only one renders at a time based on modal.type */}
      <CreateUserModal />
      <StudentProfileModal />
      <FaceEnrollModal />
      <ConfirmDeleteModal />
      <ConfirmRemoveFaceModal />
      <FaceReviewPromoteModal />
      <CourseDetailModal />

      <ToastContainer />
    </div>
  )
}

export default function App() {
  return (
    <AdminProvider>
      <AppShell />
    </AdminProvider>
  )
}
