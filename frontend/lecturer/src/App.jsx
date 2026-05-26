import { LecturerProvider, useLecturer } from './context/LecturerContext'
import PhoneFrame from './components/layout/PhoneFrame'
import BottomNav from './components/layout/BottomNav'
import ModalRouter from './components/ui/Modal'
import ToastContainer from './components/ui/Toast'

import Login from './views/Login'
import Dashboard from './views/Dashboard'
import AttendanceSessions from './views/AttendanceSessions'
import AttendanceDetail from './views/AttendanceDetail'
import QuizList from './views/QuizList'
import CreateQuiz from './views/CreateQuiz'
import LiveResults from './views/LiveResults'
import ResultsClosed from './views/ResultsClosed'
import Breakdown from './views/Breakdown'
import Analytics from './views/Analytics'
import Environment from './views/Environment'
import Profile from './views/Profile'

const VIEWS = {
  'dashboard':           Dashboard,
  'attendance-sessions': AttendanceSessions,
  'attendance-detail':   AttendanceDetail,
  'quiz-list':           QuizList,
  'create-quiz':         CreateQuiz,
  'live-results':        LiveResults,
  'results-closed':      ResultsClosed,
  'breakdown':           Breakdown,
  'analytics':           Analytics,
  'environment':         Environment,
  'profile':             Profile,
}

const MAIN_VIEWS = ['dashboard', 'attendance-sessions', 'quiz-list', 'analytics', 'environment']

function AppShell() {
  const { state } = useLecturer()

  if (!state.isLoggedIn) {
    return (
      <PhoneFrame>
        <div style={{ display: 'flex', flexDirection: 'column', height: '844px', overflow: 'hidden', position: 'relative' }}>
          <Login />
          <ModalRouter />
        </div>
      </PhoneFrame>
    )
  }

  const ActiveView = VIEWS[state.currentView] ?? Dashboard
  const showBottomNav = MAIN_VIEWS.includes(state.currentView)

  return (
    <PhoneFrame>
      <div style={{ display: 'flex', flexDirection: 'column', height: '844px', overflow: 'hidden', position: 'relative', background: 'var(--bg)' }}>
        <ActiveView />
        {showBottomNav && <BottomNav />}
        <ModalRouter />
        <ToastContainer />
      </div>
    </PhoneFrame>
  )
}

export default function App() {
  return (
    <LecturerProvider>
      <AppShell />
    </LecturerProvider>
  )
}
