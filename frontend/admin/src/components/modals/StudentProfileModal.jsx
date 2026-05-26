import { useState, useEffect } from 'react'
import { useAdmin } from '../../context/AdminContext'
import { CLASS_META } from '../../data/users'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import { RoleBadge, StatusBadge } from '../ui/Badge'

export default function StudentProfileModal() {
  const { state, dispatch, closeModal, openModal, toast } = useAdmin()
  const [editName, setEditName] = useState('')
  const [editPhone, setEditPhone] = useState('')

  const user = state.users.find(u => u.id === state.selectedUserId)

  useEffect(() => {
    if (user) { setEditName(user.name); setEditPhone(user.phone) }
  }, [user?.id])

  if (state.modal?.type !== 'studentProfile' || !user) return null

  const initials = user.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()

  const saveEdits = () => {
    dispatch({ type: 'UPDATE_USER', payload: { id: user.id, name: editName || user.name, phone: editPhone || user.phone } })
    toast('Profile updated', 'success')
  }

  const removeFromClass = (classCode) => {
    dispatch({ type: 'TOGGLE_ENROLLMENT', payload: { userId: user.id, classCode, enrolled: false } })
    toast(`Removed ${user.name.split(' ')[0]} from ${classCode}`, 'info')
  }

  return (
    <Modal
      title="Student Profile"
      subtitle="UC-30 — Manage Student Class Enrollment & Face Data"
      onClose={closeModal}
      size="lg"
      footer={
        <>
          <Button variant="danger" size="sm" onClick={() => openModal('confirmDelete')}>Delete Account</Button>
          <Button variant="ghost" className="ml-auto" onClick={closeModal}>Close</Button>
        </>
      }
    >
      <div className="grid grid-cols-[280px_1fr] gap-4">
        {/* Left — profile card */}
        <div className="space-y-3.5">
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <div className="bg-gradient-to-br from-accent-lt to-accent2-lt px-6 pt-7 pb-5 flex flex-col items-center text-center border-b border-border">
              <div
                className="w-18 h-18 rounded-full flex items-center justify-center text-[26px] font-bold text-white mb-3"
                style={{ background: `linear-gradient(135deg, ${user.color}, ${user.color}aa)`, width: 72, height: 72 }}
              >
                {initials}
              </div>
              <div className="text-base font-semibold text-text1">{user.name}</div>
              <div className="text-[11px] text-text3 mt-0.5 font-sans tracking-wide">{user.id}</div>
              <div className="mt-2.5"><RoleBadge role={user.role} /></div>
            </div>
            <div className="p-4 space-y-0">
              {[
                ['Email', user.email],
                ['Phone', user.phone],
                ['Department', user.dept],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between py-2 border-b border-border text-[13px] last:border-0">
                  <span className="text-text3 font-medium">{k}</span>
                  <span className="text-text1 text-right text-[12px]">{v}</span>
                </div>
              ))}
              <div className="flex justify-between py-2 text-[13px]">
                <span className="text-text3 font-medium">Status</span>
                <StatusBadge status={user.status} />
              </div>
            </div>
          </div>

          {/* Face data */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text3 mb-2">Face Recognition Data</p>
            <div className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-[13px] mb-2 border ${user.face ? 'bg-sc-green-lt text-sc-green-dk border-[#b6e8d4]' : 'bg-sc-orange-lt text-sc-orange-dk border-[#f5d5b2]'}`}>
              <span>{user.face ? '✓' : '⚠'}</span>
              <span>{user.face ? `Face data enrolled — ${user.faceSamples} samples (${user.faceDate})` : 'Face data not enrolled — student will not be detected'}</span>
            </div>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" className="flex-1" onClick={() => openModal('faceEnroll')}>⊙ Enroll Face Data</Button>
              {user.face && (
                <Button variant="danger" size="sm" className="flex-1" onClick={() => openModal('confirmRemoveFace')}>✕ Remove Face Data</Button>
              )}
            </div>
          </div>
        </div>

        {/* Right — classes + edit */}
        <div className="space-y-3.5">
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3.5 border-b border-border">
              <span className="text-[13.5px] font-semibold text-text1">Enrolled Classes</span>
            </div>
            {user.classes.length ? user.classes.map(c => (
              <div key={c} className="flex items-center justify-between px-4 py-3 border-b border-border last:border-0 text-[13px]">
                <div>
                  <span className="font-sans text-[12px] text-accent mr-2">{c}</span>
                  <span className="text-text1">{CLASS_META[c]?.name}</span>
                  <div className="text-[11px] text-text3 mt-0.5">{CLASS_META[c]?.lecturer}</div>
                </div>
                <button onClick={() => removeFromClass(c)} className="text-text3 hover:text-sc-red text-sm transition-colors px-1">✕</button>
              </div>
            )) : (
              <div className="px-4 py-3.5 text-[13px] text-text3">No classes assigned</div>
            )}
          </div>

          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <div className="px-4 py-3.5 border-b border-border">
              <span className="text-[13.5px] font-semibold text-text1">Edit Details</span>
            </div>
            <div className="p-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-[12px] font-medium text-text2">Full Name</label>
                  <input value={editName} onChange={e => setEditName(e.target.value)} className="bg-surface2 border border-border rounded-lg px-3 py-2 text-[13.5px] text-text1 outline-none focus:border-accent" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[12px] font-medium text-text2">Phone</label>
                  <input type="tel" value={editPhone} onChange={e => setEditPhone(e.target.value)} className="bg-surface2 border border-border rounded-lg px-3 py-2 text-[13.5px] text-text1 outline-none focus:border-accent" />
                </div>
              </div>
              <div className="flex justify-end">
                <Button variant="primary" size="sm" onClick={saveEdits}>Save Changes</Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  )
}
