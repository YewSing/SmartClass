import { useStudent } from '../../context/StudentContext'

const TABS = [
  { id: 'home',          icon: 'fa-home',           label: 'Home'        },
  { id: 'attendance',    icon: 'fa-calendar-check',  label: 'Attendance'  },
  { id: 'participation', icon: 'fa-poll-h',          label: 'Participation' },
  { id: 'profile',       icon: 'fa-user',            label: 'Profile'     },
]

export default function BottomNav() {
  const { state, navigate } = useStudent()
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
