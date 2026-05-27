import { AdminProvider, useAdmin } from './context/AdminContext'
import Sidebar from './components/layout/Sidebar'
import Topbar from './components/layout/Topbar'
import ToastContainer from './components/ui/Toast'
import CreateUserModal from './components/modals/CreateUserModal'
import StudentProfileModal from './components/modals/StudentProfileModal'
import FaceEnrollModal from './components/modals/FaceEnrollModal'
import { ConfirmDeleteModal, ConfirmRemoveFaceModal } from './components/modals/ConfirmModal'
import FaceReviewPromoteModal from './components/modals/FaceReviewPromoteModal'
import Login from './views/Login'
import Dashboard from './views/Dashboard'
import UsersView from './views/UsersView'
import StudentsView from './views/StudentsView'
import LecturersView from './views/LecturersView'
import EnrollmentView from './views/EnrollmentView'
import FaceDataView from './views/FaceDataView'
import FaceReviewView from './views/FaceReviewView'
import EnvironmentView from './views/EnvironmentView'
import AuditLogView from './views/AuditLogView'

const VIEWS = {
  dashboard:   Dashboard,
  users:       UsersView,
  students:    StudentsView,
  lecturers:   LecturersView,
  enrollment:  EnrollmentView,
  facedata:    FaceDataView,
  facereview:  FaceReviewView,
  environment: EnvironmentView,
  audit:       AuditLogView,
}

function AppShell() {
  const { state } = useAdmin()

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
