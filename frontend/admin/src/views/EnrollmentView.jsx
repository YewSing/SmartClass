import { useEffect, useState } from 'react'
import { useAdmin } from '../context/AdminContext'
import { avatarInitials } from '../components/ui/Avatar'

export default function EnrollmentView() {
  const { state, dispatch, loadAllClasses, toggleEnrollment, openModal, toast } = useAdmin()
  const [search, setSearch] = useState('')
  const [toggling, setToggling] = useState(null) // `${userId}-${classId}` while in-flight

  useEffect(() => {
    if (!state.allClasses.length) loadAllClasses()
  }, [])

  const allStudents = state.users.filter(u => u.role === 'Student')
  const students = allStudents.filter(u =>
    !search ||
    u.name.toLowerCase().includes(search.toLowerCase()) ||
    String(u.matric ?? u.id).toLowerCase().includes(search.toLowerCase())
  )

  const toggle = async (userId, classObj, checked) => {
    const key = `${userId}-${classObj.id}`
    setToggling(key)
    try {
      await toggleEnrollment(userId, classObj, checked)
      const u = state.users.find(x => x.id === userId)
      toast(`${u?.name.split(' ')[0]} ${checked ? 'enrolled in' : 'removed from'} ${classObj.code}`, 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setToggling(null)
    }
  }

  const openProfile = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('studentProfile')
  }

  const classes = state.allClasses

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Class Enrollment</span>
        <div className="flex items-center gap-2 bg-surface2 border border-border rounded-lg px-3 py-1.5 ml-auto">
          <span className="text-text3 text-[13px]">⌕</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search student…"
            className="bg-transparent outline-none text-[13px] text-text1 w-48 placeholder:text-text3"
          />
        </div>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Student</th>
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Matric ID</th>
            {classes.map(c => (
              <th key={c.id} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-center border-b border-border">{c.code}</th>
            ))}
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Actions</th>
          </tr>
        </thead>
        <tbody>
          {students.length === 0 && (
            <tr>
              <td colSpan={3 + classes.length} className="px-5 py-6 text-center text-[13px] text-text3">
                {state.users.length === 0 ? 'Loading…' : 'No students found'}
              </td>
            </tr>
          )}
          {students.map(u => {
            const enrolledIds = new Set(u.classes.map(c => c.id))
            return (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-5 py-3 border-b border-border">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0" style={{ background: u.color }}>
                      {avatarInitials(u.name)}
                    </div>
                    <span className="text-[13px] text-text1">{u.name}</span>
                  </div>
                </td>
                <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text2">{u.matric ?? '—'}</td>
                {classes.map(c => {
                  const key = `${u.id}-${c.id}`
                  return (
                    <td key={c.id} className="px-5 py-3 border-b border-border text-center">
                      <input
                        type="checkbox"
                        checked={enrolledIds.has(c.id)}
                        disabled={toggling === key}
                        onChange={e => toggle(u.id, c, e.target.checked)}
                        className="w-3.5 h-3.5 accent-accent cursor-pointer disabled:opacity-40"
                      />
                    </td>
                  )
                })}
                <td className="px-5 py-3 border-b border-border">
                  <button
                    onClick={() => openProfile(u.id)}
                    className="text-[13px] text-text2 hover:text-text1 border border-border rounded-md px-2.5 py-1 bg-transparent hover:bg-surface2 transition-all"
                  >
                    ✎ Edit
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
