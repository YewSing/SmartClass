import { useState } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

export default function FaceReviewPromoteModal() {
  const { state, dispatch, closeModal, toast } = useAdmin()
  const [selectedUserId, setSelectedUserId] = useState('')

  if (state.modal?.type !== 'faceReviewPromote') return null

  const { reviewId } = state.modal.data ?? {}
  const entry = state.unrecognisedQueue.find(e => e.id === reviewId)
  const students = state.users.filter(u => u.role === 'Student' && !u.face)

  if (!entry) return null

  const handleClose = () => { closeModal(); setSelectedUserId('') }

  const handleConfirm = () => {
    if (!selectedUserId) return
    const student = state.users.find(u => u.id === selectedUserId)
    dispatch({ type: 'PROMOTE_REVIEW', payload: { reviewId, userId: selectedUserId } })
    closeModal()
    setSelectedUserId('')
    toast(`Face enrolled for ${student?.name.split(' ')[0]} from review queue`, 'success')
  }

  return (
    <Modal
      title="Identify & Enroll Face"
      subtitle="UC-08 (alt flow) — Promote unrecognised face to student enrollment"
      onClose={handleClose}
      footer={
        <>
          <Button variant="ghost" onClick={handleClose}>Cancel</Button>
          <Button variant="primary" onClick={handleConfirm} disabled={!selectedUserId}>
            ⊙ Confirm Enrollment
          </Button>
        </>
      }
    >
      {/* Entry metadata */}
      <div className="bg-surface2 border border-border rounded-xl p-4 mb-5 space-y-1.5">
        <div className="flex justify-between text-[13px]">
          <span className="text-text3">Entry ID</span>
          <span className="text-text1 font-medium font-sans">{entry.id}</span>
        </div>
        <div className="flex justify-between text-[13px]">
          <span className="text-text3">Timestamp</span>
          <span className="text-text2 font-sans">{entry.ts}</span>
        </div>
        <div className="flex justify-between text-[13px]">
          <span className="text-text3">Camera</span>
          <span className="text-text2">{entry.camera}</span>
        </div>
        <div className="flex justify-between text-[13px]">
          <span className="text-text3">Session</span>
          <span className="text-text2">{entry.session}</span>
        </div>
        <div className="flex justify-between text-[13px]">
          <span className="text-text3">Best confidence score</span>
          <span className="text-sc-orange font-semibold">{Math.round(entry.confidence * 100)}% (below threshold)</span>
        </div>
        <div className="flex justify-between text-[13px]">
          <span className="text-text3">Occurrences</span>
          <span className="text-text2">{entry.occurrences} detection{entry.occurrences > 1 ? 's' : ''}</span>
        </div>
      </div>

      {/* Face placeholder */}
      <div className="flex flex-col items-center mb-5">
        <div className="w-24 h-24 rounded-xl bg-surface3 border-2 border-dashed border-border flex flex-col items-center justify-center mb-2">
          <div className="text-3xl opacity-30">👤</div>
          <div className="text-[10px] text-text3 mt-1">Captured face</div>
        </div>
        <p className="text-[11.5px] text-text3 text-center max-w-[280px]">
          NFR-01: Raw image is not stored. The embedding captured from this face will be linked to the selected student.
        </p>
      </div>

      {/* Student selector */}
      <div>
        <label className="block text-[12.5px] font-semibold text-text2 mb-1.5">
          Assign to student <span className="text-red-500">*</span>
        </label>
        {students.length === 0 ? (
          <p className="text-[13px] text-text3 bg-surface2 border border-border rounded-lg px-3 py-2.5">
            All students without face data have already been enrolled.
          </p>
        ) : (
          <select
            value={selectedUserId}
            onChange={e => setSelectedUserId(e.target.value)}
            className="w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-[13px] text-text1 outline-none focus:border-accent"
          >
            <option value="">— Select a student —</option>
            {students.map(u => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.id}) · {u.classes.join(', ') || 'No class'}
              </option>
            ))}
          </select>
        )}
      </div>
    </Modal>
  )
}
