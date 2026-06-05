import { useState, useEffect } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import { RoleBadge, StatusBadge } from '../ui/Badge'

function occurrenceLabel(o) {
  const typeLabel = o.type === 'LECTURE' ? 'Lecture' : (o.label ?? 'Tutorial')
  return `${typeLabel} · ${o.day_of_week} ${o.start_time}–${o.end_time}`
}

export default function StudentProfileModal() {
  const { state, updateUser, closeModal, openModal, loadAllClasses, toggleOccurrenceEnrollment, toast } = useAdmin()
  const [editName, setEditName] = useState('')
  const [editPhone, setEditPhone] = useState('')
  const [enrolling, setEnrolling] = useState(null)
  const [addSearch, setAddSearch] = useState('')

  const user = state.users.find(u => u.id === state.selectedUserId)

  useEffect(() => {
    if (user) { setEditName(user.name); setEditPhone(user.phone) }
  }, [user?.id])

  useEffect(() => {
    if (state.modal?.type === 'studentProfile') loadAllClasses()
  }, [state.modal?.type])

  if (state.modal?.type !== 'studentProfile' || !user) return null

  const initials = user.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()

  const saveEdits = async () => {
    try {
      await updateUser(user.id, { name: editName || user.name, phone: editPhone || user.phone })
      toast('Profile updated', 'success')
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const handleReactivate = async () => {
    try {
      await updateUser(user.id, { status: 'active' })
      toast(`Account reactivated: ${user.name}`, 'success')
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const handleToggle = async (occObj, enroll) => {
    setEnrolling(occObj.id)
    try {
      await toggleOccurrenceEnrollment(user.id, occObj, enroll)
      toast(
        enroll
          ? `Added to ${occObj.code} ${occObj.type === 'LECTURE' ? 'Lecture' : (occObj.label ?? 'Tutorial')}`
          : `Removed from ${occObj.code} ${occObj.type === 'LECTURE' ? 'Lecture' : (occObj.label ?? 'Tutorial')}`,
        'success'
      )
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setEnrolling(null)
    }
  }

  const grouped = {}
  for (const o of (user.occurrences ?? [])) {
    if (!grouped[o.course_code]) grouped[o.course_code] = { name: o.course_name, occs: [] }
    grouped[o.course_code].occs.push(o)
  }

  const enrolledIds = new Set((user.occurrences ?? []).map(o => o.id))
  const available = state.allClasses.filter(c =>
    !enrolledIds.has(c.id) && (
      addSearch.length < 2 ||
      c.code.toLowerCase().includes(addSearch.toLowerCase()) ||
      c.name.toLowerCase().includes(addSearch.toLowerCase())
    )
  )

  return (
    <Modal
      title={user.role === 'Lecturer' ? 'Lecturer Profile' : 'Student Profile'}
      subtitle="Manage User Enrollment & Face Data"
      onClose={closeModal}
      size="lg"
      footer={
        <>
          {user.status === 'Active'
            ? <Button variant="danger" size="sm" onClick={() => openModal('confirmDelete')}>Deactivate Account</Button>
            : <Button variant="primary" size="sm" onClick={handleReactivate}>Reactivate Account</Button>
          }
          <Button variant="ghost" className="ml-auto" onClick={closeModal}>Close</Button>
        </>
      }
    >
      <div className="space-y-4">

        {/* Section 1: User info + editable fields */}
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <div className="bg-gradient-to-br from-accent-lt to-accent2-lt px-6 py-5 flex items-center gap-4 border-b border-border">
            <div
              className="rounded-full flex items-center justify-center text-[24px] font-bold text-white flex-shrink-0"
              style={{ width: 64, height: 64, background: `linear-gradient(135deg, ${user.color}, ${user.color}aa)` }}
            >
              {initials}
            </div>
            <div>
              <div className="text-base font-semibold text-text1">{user.name}</div>
              <div className="text-[12px] text-text3 font-sans mt-0.5">{user.matric ?? user.staffId ?? `ID: ${user.id}`}</div>
              <div className="mt-2 flex items-center gap-2">
                <RoleBadge role={user.role} />
                <StatusBadge status={user.status} />
              </div>
            </div>
          </div>
          <div className="p-4">
            <div className="space-y-3 mb-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-text2">Full Name</label>
                <input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-[13.5px] text-text1 outline-none focus:border-accent"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-text2">Phone</label>
                <input
                  type="tel"
                  value={editPhone}
                  onChange={e => setEditPhone(e.target.value)}
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-[13.5px] text-text1 outline-none focus:border-accent"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-medium text-text2">Email</label>
                <input
                  value={user.email}
                  readOnly
                  className="bg-surface2 border border-border rounded-lg px-3 py-2 text-[13.5px] text-text3 outline-none cursor-not-allowed"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <Button variant="primary" size="sm" onClick={saveEdits}>Save Changes</Button>
            </div>
          </div>
        </div>

        {/* Section 2: Enrolled Occurrences */}
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3.5 border-b border-border">
            <span className="text-[13.5px] font-semibold text-text1">Enrolled Occurrences</span>
          </div>

          {Object.keys(grouped).length === 0 ? (
            <div className="px-4 py-3.5 text-[13px] text-text3">No occurrences assigned</div>
          ) : (
            Object.entries(grouped).map(([code, { name, occs }]) => (
              <div key={code} className="border-b border-border last:border-0">
                <div className="flex items-baseline gap-2 px-4 pt-3 pb-1.5">
                  <span className="font-sans text-[12px] font-bold text-accent">{code}</span>
                  <span className="text-[12px] text-text2">{name}</span>
                </div>
                {occs.map(o => (
                  <div key={o.id} className="flex items-center justify-between px-4 pb-2.5 text-[12.5px]">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${o.type === 'LECTURE' ? 'bg-blue-500/15 text-blue-400' : 'bg-green-500/15 text-green-400'}`}>
                        {o.type === 'LECTURE' ? 'Lec' : 'Tut'}
                      </span>
                      <span className="text-text2">{occurrenceLabel(o)}</span>
                    </div>
                    <button
                      onClick={() => handleToggle(o, false)}
                      disabled={enrolling === o.id}
                      className="text-text3 hover:text-sc-red text-sm transition-colors px-1 disabled:opacity-40"
                    >
                      {enrolling === o.id ? '…' : '✕'}
                    </button>
                  </div>
                ))}
              </div>
            ))
          )}

          <div className="px-4 py-3 border-t border-border">
            <p className="text-[11px] text-text3 mb-2 font-medium uppercase tracking-wide">Add Occurrence</p>
            <input
              value={addSearch}
              onChange={e => setAddSearch(e.target.value)}
              placeholder="Search by course code or name…"
              className="mb-2 w-full bg-surface2 border border-border rounded-lg px-3 py-1.5 text-[12.5px] text-text1 outline-none focus:border-accent placeholder:text-text3"
            />
            {addSearch.length >= 2 && (
              <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
                {available.length === 0 ? (
                  <p className="text-[11.5px] text-text3">No matches.</p>
                ) : (
                  available.slice(0, 20).map(c => (
                    <button
                      key={c.id}
                      onClick={() => handleToggle(c, true)}
                      disabled={enrolling === c.id}
                      className="px-2.5 py-1 text-[11px] rounded-lg border border-dashed border-accent text-accent hover:bg-accent-lt transition-colors disabled:opacity-40"
                    >
                      {enrolling === c.id ? '…' : `+ ${c.code} ${c.type === 'LECTURE' ? 'Lec' : (c.label ?? 'Tut')}`}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Section 3: Face Recognition Data — students only */}
        {user.role !== 'Lecturer' && (
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <div className="px-4 py-3.5 border-b border-border">
              <span className="text-[13.5px] font-semibold text-text1">Face Recognition Data</span>
            </div>
            <div className="p-4 space-y-3">
              <div className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-[13px] border ${user.face ? 'bg-sc-green-lt text-sc-green-dk border-[#b6e8d4]' : 'bg-sc-orange-lt text-sc-orange-dk border-[#f5d5b2]'}`}>
                <span>{user.face ? '✓' : '⚠'}</span>
                <span>{user.face ? `Face data enrolled — ${user.faceSamples} samples (${user.faceDate})` : 'Face data not enrolled — student will not be detected'}</span>
              </div>
              <div className="flex gap-2">
                <Button variant="primary" size="sm" onClick={() => openModal('faceEnroll')}>⊙ Enroll Face Data</Button>
                {user.face && (
                  <Button variant="danger" size="sm" onClick={() => openModal('confirmRemoveFace')}>✕ Remove Face Data</Button>
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </Modal>
  )
}
