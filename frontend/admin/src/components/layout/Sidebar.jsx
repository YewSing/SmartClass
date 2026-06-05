import { useAdmin } from '../../context/AdminContext'
import { NavBadge } from '../ui/Badge'

const NAV = [
  {
    label: 'Main',
    items: [
      { id: 'dashboard', icon: 'fa-solid fa-gauge',            label: 'Dashboard' },
    ],
  },
  {
    label: 'User Management',
    items: [
      { id: 'students',  icon: 'fa-solid fa-graduation-cap',   label: 'Students' },
      { id: 'lecturers', icon: 'fa-solid fa-id-badge',         label: 'Lecturers' },
    ],
  },
  {
    label: 'Enrollment',
    items: [
      { id: 'classmanagement', icon: 'fa-solid fa-book-open',        label: 'Class Management' },
      { id: 'facereview', icon: 'fa-solid fa-user-slash',      label: 'Face Review Queue', badge: { dynamic: 'unrecognisedQueue', color: '#E87722' } },
    ],
  },
  {
    label: 'System',
    items: [
      { id: 'environment', icon: 'fa-solid fa-temperature-half',  label: 'Environment' },
      { id: 'audit',       icon: 'fa-solid fa-clock-rotate-left', label: 'Audit Log' },
    ],
  },
]

export default function Sidebar() {
  const { state, dispatch, logout } = useAdmin()

  return (
    <aside className="w-60 min-w-60 bg-surface border-r border-border flex flex-col h-screen sticky top-0">
      <div className="px-5 py-6 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent2 flex items-center justify-center font-sans text-sm font-bold text-white flex-shrink-0">
            SC
          </div>
          <div>
            <div className="font-sans text-xs font-bold tracking-wide text-text1">SmartClass</div>
            <div className="text-[10px] text-text3 mt-0.5">Admin Panel</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pt-4">
        {NAV.map(section => (
          <div key={section.label}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-text3 px-2 mb-1.5 mt-4 first:mt-0">
              {section.label}
            </div>
            {section.items.map(item => {
              const active = state.currentView === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => dispatch({ type: 'SET_VIEW', payload: item.id })}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13.5px] transition-all duration-150 mb-0.5 relative cursor-pointer ${
                    active
                      ? 'bg-accent-lt text-accent font-medium'
                      : 'text-text2 hover:bg-surface2 hover:text-text1'
                  }`}
                >
                  {active && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] bg-accent rounded-r-sm" />
                  )}
                  <i className={`${item.icon} text-[14px] w-5 text-center flex-shrink-0`} />
                  {item.label}
                  {item.badge && (() => {
                    const count = item.badge.dynamic
                      ? state[item.badge.dynamic]?.length ?? 0
                      : item.badge.count
                    return count > 0 ? <NavBadge count={count} color={item.badge.color} /> : null
                  })()}
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-2.5 p-2.5 bg-surface2 rounded-lg">
          <div className="w-[30px] h-[30px] rounded-full bg-gradient-to-br from-accent2 to-accent flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
            AD
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[12.5px] font-medium text-text1 truncate">Admin User</div>
            <div className="text-[10px] text-text3 font-semibold tracking-wide">ADMINISTRATOR</div>
          </div>
          <button
            onClick={logout}
            className="text-text3 hover:text-text1 text-base px-1 transition-colors"
            title="Logout"
          >
            ⇠
          </button>
        </div>
      </div>
    </aside>
  )
}
