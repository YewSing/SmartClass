import { StudentProvider, useStudent } from './context/StudentContext'
import PhoneFrame from './components/layout/PhoneFrame'
import BottomNav from './components/layout/BottomNav'
import ModalRouter from './components/ui/Modal'
import ToastContainer from './components/ui/Toast'

import Login from './views/Login'
import Home from './views/Home'
import Attendance from './views/Attendance'
import AttSessionDetail from './views/AttSessionDetail'
import AttReportStatus from './views/AttReportStatus'
import Participation from './views/Participation'
import PartSessionPerf from './views/PartSessionPerf'
import Profile from './views/Profile'

const VIEWS = {
  'home':               Home,
  'attendance':         Attendance,
  'att-session-detail': AttSessionDetail,
  'att-report-status':  AttReportStatus,
  'participation':      Participation,
  'part-session-perf':  PartSessionPerf,
  'profile':            Profile,
}

const MAIN_VIEWS = ['home', 'attendance', 'participation', 'profile']

function AppShell() {
  const { state } = useStudent()

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

  const ActiveView = VIEWS[state.currentView] ?? Home
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
    <StudentProvider>
      <AppShell />
    </StudentProvider>
  )
}
