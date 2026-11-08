import { useAdmin } from '../context/AdminContext'
import StatCard from '../components/ui/StatCard'
import { StatusBadge } from '../components/ui/Badge'
import { AUDIT_LOG } from '../data/users'

const ACTION_LABELS = {
  FACE_ENROLL:    'Face data enrolled',
  USER_CREATE:    'User created',
  ENROLL_UPDATE:  'Class enrollment updated',
  USER_DEACTIVATE:'Account deactivated',
  FACE_REMOVE:    'Face data removed',
  USER_UPDATE:    'Profile updated',
  FACE_PROMOTE:   'Face promoted from review queue',
}

export default function Dashboard() {
  const { state, dispatch } = useAdmin()
  const students  = state.users.filter(u => u.role === 'Student'  && u.status === 'Active')
  const lecturers = state.users.filter(u => u.role === 'Lecturer' && u.status === 'Active')
  const activeUsers = state.users.filter(u => u.status === 'Active')
  const pendingFace = students.filter(u => !u.face).length
  const queueCount  = state.unrecognisedQueue.length

  const recent = AUDIT_LOG.slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-3.5">
        <StatCard label="Total Users"         value={activeUsers.length}                                                   accentColor="#1B6EF3" />
        <StatCard label="Students"            value={students.length}    sub={`${students.filter(u => u.face).length} face-enrolled`} accentColor="#12A564" />
        <StatCard label="Lecturers"           value={lecturers.length}                                                       accentColor="#7C3AED" />
        <StatCard label="Pending Face Enroll" value={pendingFace}        sub="⚠ action needed"                               accentColor="#E87722" />
      </div>

      <div className="grid grid-cols-3 gap-3.5">
        {/* Recent activity — from AUDIT_LOG */}
        <div className="col-span-2 bg-surface border border-border rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <span className="text-[14px] font-semibold text-text1">Recent Activity</span>
            <button
              onClick={() => dispatch({ type: 'SET_VIEW', payload: 'audit' })}
              className="text-[12px] text-accent hover:underline"
            >
              View full log →
            </button>
          </div>
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-surface2">
                {['Timestamp', 'Actor', 'Action', 'Target'].map(h => (
                  <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recent.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-5 py-3 font-sans text-[12px] text-text3 border-b border-border">{r.ts}</td>
                  <td className="px-5 py-3 text-[13px] text-text2 border-b border-border">{r.actor}</td>
                  <td className="px-5 py-3 text-[13px] text-text2 border-b border-border">{ACTION_LABELS[r.action] ?? r.action}</td>
                  <td className="px-5 py-3 font-sans text-[12px] text-text2 border-b border-border">{r.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Face review */}
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <span className="text-[14px] font-semibold text-text1">Face Review</span>
          </div>
          <div className="px-5 py-4">
            <div className="flex items-center justify-between text-[12px] text-text3 mb-1">
              <span>Pending face review</span>
              <span className="font-semibold text-sc-orange">{queueCount}</span>
            </div>
            {queueCount > 0 && (
              <button
                onClick={() => dispatch({ type: 'SET_VIEW', payload: 'facereview' })}
                className="text-[12px] text-accent hover:underline"
              >
                Review queue →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
