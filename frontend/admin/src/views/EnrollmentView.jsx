import { useAdmin } from '../context/AdminContext'
import { avatarInitials } from '../components/ui/Avatar'
import { ALL_CLASSES } from '../data/users'

export default function EnrollmentView() {
  const { state, dispatch, toast } = useAdmin()
  const students = state.users.filter(u => u.role === 'Student')

  const toggle = (userId, classCode, checked) => {
    dispatch({ type: 'TOGGLE_ENROLLMENT', payload: { userId, classCode, enrolled: checked } })
    const u = state.users.find(x => x.id === userId)
    toast(`${u?.name.split(' ')[0]} ${checked ? 'enrolled in' : 'removed from'} ${classCode}`, 'success')
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Class Enrollment</span>
        <div className="flex items-center gap-2 bg-surface2 border border-border rounded-lg px-3 py-1.5 ml-auto">
          <span className="text-text3 text-[13px]">⌕</span>
          <input placeholder="Search student or class…" className="bg-transparent outline-none text-[13px] text-text1 w-48 placeholder:text-text3" />
        </div>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Student</th>
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Matric ID</th>
            {ALL_CLASSES.map(c => (
              <th key={c} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-center border-b border-border">{c}</th>
            ))}
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Actions</th>
          </tr>
        </thead>
        <tbody>
          {students.map(u => (
            <tr key={u.id} className="hover:bg-gray-50">
              <td className="px-5 py-3 border-b border-border">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0" style={{ background: u.color }}>
                    {avatarInitials(u.name)}
                  </div>
                  <span className="text-[13px] text-text1">{u.name}</span>
                </div>
              </td>
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text2">{u.id}</td>
              {ALL_CLASSES.map(c => (
                <td key={c} className="px-5 py-3 border-b border-border text-center">
                  <input
                    type="checkbox"
                    checked={u.classes.includes(c)}
                    onChange={e => toggle(u.id, c, e.target.checked)}
                    className="w-3.5 h-3.5 accent-accent cursor-pointer"
                  />
                </td>
              ))}
              <td className="px-5 py-3 border-b border-border">
                <button className="text-[13px] text-text2 hover:text-text1 border border-border rounded-md px-2.5 py-1 bg-transparent hover:bg-surface2 transition-all">✎ Edit</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
