import { useAdmin } from '../context/AdminContext'
import { avatarInitials } from '../components/ui/Avatar'
import { FaceBadge } from '../components/ui/Badge'
import Button from '../components/ui/Button'

export default function FaceDataView() {
  const { state, dispatch, openModal } = useAdmin()
  const students = state.users.filter(u => u.role === 'Student')

  const openEnroll = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('faceEnroll')
  }

  const openRemove = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('confirmRemoveFace')
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Face Enrollment Status</span>
        <select className="ml-auto bg-surface2 border border-border rounded-lg px-2.5 py-1.5 text-[13px] text-text2 outline-none">
          <option>All Students</option>
          <option>Enrolled</option>
          <option>Not Enrolled</option>
        </select>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            {['Student', 'Matric ID', 'Face Data Status', 'Enrolled On', 'Samples', 'Actions'].map(h => (
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
                  <span className="text-[13.5px] font-medium text-text1">{u.name}</span>
                </div>
              </td>
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text1">{u.id}</td>
              <td className="px-5 py-3 border-b border-border">
                {u.face
                  ? <FaceBadge enrolled />
                  : <span className="inline-flex items-center gap-1 text-[11px] font-medium text-sc-orange">⚠ Not enrolled</span>}
              </td>
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text3">{u.faceDate ?? '—'}</td>
              <td className="px-5 py-3 border-b border-border text-[12px] text-text2">{u.face ? `${u.faceSamples} / 5` : '—'}</td>
              <td className="px-5 py-3 border-b border-border">
                <div className="flex gap-1.5">
                  {!u.face
                    ? <Button variant="primary" size="sm" onClick={() => openEnroll(u.id)}>⊙ Enroll</Button>
                    : <>
                        <Button variant="ghost" size="sm" onClick={() => openEnroll(u.id)}>↺ Re-enroll</Button>
                        <Button variant="danger" size="sm" onClick={() => openRemove(u.id)}>✕ Remove</Button>
                      </>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
