import { useAdmin } from '../context/AdminContext'
import { avatarInitials } from '../components/ui/Avatar'
import { StatusBadge } from '../components/ui/Badge'
import Button from '../components/ui/Button'

export default function LecturersView() {
  const { state, dispatch, openModal } = useAdmin()
  const staff = state.users.filter(u => u.role === 'Lecturer')

  const openProfile = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('studentProfile')
  }

  const openDelete = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('confirmDelete')
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Lecturer Accounts</span>
        <Button variant="primary" size="sm" className="ml-auto" onClick={() => openModal('createUser')}>＋ Add Lecturer</Button>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            {['Lecturer', 'Staff ID', 'Department', 'Assigned Classes', 'Status', 'Actions'].map(h => (
              <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {staff.map(u => (
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
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text1">{u.id}</td>
              <td className="px-5 py-3 border-b border-border text-[12.5px] text-text2">{u.dept}</td>
              <td className="px-5 py-3 border-b border-border text-[12.5px] text-text2">
                {u.classes.length ? u.classes.map(c => c.code).join(', ') : <span className="text-text3">—</span>}
              </td>
              <td className="px-5 py-3 border-b border-border"><StatusBadge status={u.status} /></td>
              <td className="px-5 py-3 border-b border-border">
                <div className="flex gap-1.5">
                  <Button variant="ghost" size="sm" onClick={() => openProfile(u.id)}>✎ Edit</Button>
                  <Button variant="danger" size="sm" onClick={() => openDelete(u.id)}>✕</Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
