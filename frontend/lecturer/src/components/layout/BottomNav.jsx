import { useLecturer } from '../../context/LecturerContext'

const TABS = [
  { id: 'dashboard',           icon: 'fa-home',            label: 'Home'        },
  { id: 'attendance-sessions', icon: 'fa-user-check',      label: 'Attendance'  },
  { id: 'quiz-list',           icon: 'fa-question-circle', label: 'Quiz'        },
  { id: 'analytics',           icon: 'fa-chart-bar',       label: 'Analytics'   },
  { id: 'environment',         icon: 'fa-leaf',            label: 'Environment' },
]

export default function BottomNav() {
  const { state, navigate } = useLecturer()
  return (
    <div className="bottomnav">
      {TABS.map(tab => (
        <button
          key={tab.id}
          className={`nav-item${state.currentView === tab.id ? ' active' : ''}`}
          onClick={() => navigate(tab.id)}
        >
          <i className={`fa ${tab.icon}`}></i>
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  )
}
