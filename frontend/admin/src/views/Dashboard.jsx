import { useAdmin } from '../context/AdminContext'
import StatCard from '../components/ui/StatCard'
import { StatusBadge } from '../components/ui/Badge'

const RECENT = [
  { ts: '2025-05-26 09:14', actor: 'Admin User', action: 'Face data enrolled',       target: 'U2024001 — Nurul Ain',    status: 'Active' },
  { ts: '2025-05-26 08:50', actor: 'Admin User', action: 'User created',             target: 'U2024047 — Lim Wei',      status: 'Active' },
  { ts: '2025-05-25 16:30', actor: 'Admin User', action: 'Class enrollment updated', target: 'U2024032 — Ahmad Fariz',  status: 'Active' },
  { ts: '2025-05-25 14:10', actor: 'Admin User', action: 'Account deactivated',      target: 'U2023089 — Priya N.',     status: 'Inactive' },
]

export default function Dashboard() {
  const { state } = useAdmin()
  const students = state.users.filter(u => u.role === 'Student')
  const lecturers = state.users.filter(u => u.role === 'Lecturer')
  const pendingFace = students.filter(u => !u.face).length

  return (
    <div>
      <div className="grid grid-cols-4 gap-3.5 mb-6">
        <StatCard label="Total Users"          value={state.users.length} sub="↑ 3 this semester"                accentColor="#1B6EF3" />
        <StatCard label="Students"             value={students.length}    sub={`${students.filter(u => u.face).length} face-enrolled`} accentColor="#12A564" />
        <StatCard label="Lecturers"            value={lecturers.length}   sub="across 4 departments"             accentColor="#7C3AED" />
        <StatCard label="Pending Face Enroll"  value={pendingFace}        sub="⚠ action needed"                  accentColor="#E87722" />
      </div>

      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <span className="text-[14px] font-semibold text-text1">Recent Activity</span>
        </div>
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-surface2">
              {['Timestamp', 'Actor', 'Action', 'Target', 'Status'].map(h => (
                <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {RECENT.map((r, i) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="px-5 py-3 font-sans text-[12px] text-text3 border-b border-border">{r.ts}</td>
                <td className="px-5 py-3 text-[13.5px] text-text2 border-b border-border">{r.actor}</td>
                <td className="px-5 py-3 text-[13.5px] text-text2 border-b border-border">{r.action}</td>
                <td className="px-5 py-3 font-sans text-[12px] text-text2 border-b border-border">{r.target}</td>
                <td className="px-5 py-3 border-b border-border"><StatusBadge status={r.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
