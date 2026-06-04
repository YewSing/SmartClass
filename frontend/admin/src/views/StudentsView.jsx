import { useState } from 'react'
import { useAdmin } from '../context/AdminContext'
import { avatarInitials } from '../components/ui/Avatar'
import { StatusBadge, FaceBadge } from '../components/ui/Badge'
import Button from '../components/ui/Button'

export default function StudentsView() {
  const { state, dispatch, openModal } = useAdmin()
  const [search, setSearch] = useState('')
  const allStudents = state.users.filter(u => u.role === 'Student')
  const students = allStudents.filter(u =>
    !search ||
    u.name.toLowerCase().includes(search.toLowerCase()) ||
    String(u.matric ?? '').toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase())
  )

  const openProfile = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('studentProfile')
  }

  const openFaceEnroll = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('faceEnroll')
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Student Accounts</span>
        <div className="flex items-center gap-2 bg-surface2 border border-border rounded-lg px-3 py-1.5 ml-auto">
          <span className="text-text3 text-[13px]">⌕</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search students…"
            className="bg-transparent outline-none text-[13px] text-text1 w-48 placeholder:text-text3"
          />
        </div>
        <Button variant="primary" size="sm" onClick={() => openModal('createUser')}>＋ Add Student</Button>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            {['Student', 'Matric ID', 'Enrolled', 'Face Data', 'Status', 'Actions'].map(h => (
              <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {students.map(u => (
            <tr key={u.id} className="hover:bg-gray-50">
              <td className="px-5 py-3 border-b border-border">
                <div className="flex items-center gap-2.5">
                  <div className="w-[30px] h-[30px] rounded-full flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0" style={{ background: u.color }}>
                    {avatarInitials(u.name)}
                  </div>
                  <div>
                    <div className="text-[13.5px] font-medium text-text1">{u.name}</div>
                    <div className="text-[11px] text-text3">{u.email}</div>
                  </div>
                </div>
              </td>
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text1">{u.matric ?? '—'}</td>
              <td className="px-5 py-3 border-b border-border">
                {(() => {
                  const count = (u.occurrences ?? []).length
                  return count > 0
                    ? <span className="text-[12px] text-text2">{count} occurrence{count !== 1 ? 's' : ''}</span>
                    : <span className="text-[12px] text-text3">None</span>
                })()}
              </td>
              <td className="px-5 py-3 border-b border-border"><FaceBadge enrolled={u.face} /></td>
              <td className="px-5 py-3 border-b border-border"><StatusBadge status={u.status} /></td>
              <td className="px-5 py-3 border-b border-border">
                <div className="flex gap-1.5">
                  <Button variant="ghost" size="sm" onClick={() => openProfile(u.id)}>✎ Profile</Button>
                  {!u.face && (
                    <Button variant="primary" size="sm" onClick={() => openFaceEnroll(u.id)}>⊙ Enroll Face</Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
