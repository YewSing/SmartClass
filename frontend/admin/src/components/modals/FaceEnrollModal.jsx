import { useState } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

export default function FaceEnrollModal() {
  const { state, dispatch, closeModal, toast } = useAdmin()
  const [count, setCount] = useState(0)
  const [done, setDone] = useState(false)

  const user = state.users.find(u => u.id === state.selectedUserId)

  if (state.modal?.type !== 'faceEnroll' || !user) return null

  const capture = () => {
    const next = count + 1
    setCount(next)
    if (next >= 5) setDone(true)
  }

  const finalize = () => {
    dispatch({ type: 'ENROLL_FACE', payload: user.id })
    closeModal()
    setCount(0)
    setDone(false)
    toast(`Face data enrolled for ${user.name.split(' ')[0]}`, 'success')
  }

  const handleClose = () => { closeModal(); setCount(0); setDone(false) }

  const statusText = done
    ? '✓ All 5 samples captured — saving embedding…'
    : count > 0
    ? `Sample ${count} captured. ${5 - count} more needed.`
    : 'Position face within the frame, then capture'

  return (
    <Modal
      title="Face Data Enrollment"
      subtitle="UC-08 / FR-059 — Capture face samples for recognition"
      onClose={handleClose}
      footer={
        <>
          <Button variant="ghost" onClick={handleClose}>Cancel</Button>
          <Button variant="primary" onClick={done ? finalize : capture}>
            {done ? '✓ Save Enrollment' : '⊙ Capture Sample'}
          </Button>
        </>
      }
    >
      <div className="text-center mb-3.5">
        <span className="text-[12px] text-text3">Student: <span className="text-text1 font-medium">{user.name}</span></span>
      </div>

      <div className="bg-surface2 border border-dashed border-border rounded-xl p-5 flex flex-col items-center gap-3 text-center">
        {/* Camera preview */}
        <div className="w-44 h-44 rounded-xl bg-surface3 border-2 border-border flex flex-col items-center justify-center relative overflow-hidden">
          <div className="w-24 h-28 border-2 border-accent rounded-[60px] relative opacity-60">
            <span className="absolute -top-0.5 -left-0.5 w-4 h-4 border-t-[3px] border-l-[3px] border-accent rounded-tl" />
            <span className="absolute -bottom-0.5 -right-0.5 w-4 h-4 border-b-[3px] border-r-[3px] border-accent rounded-br" />
          </div>
          <div className="text-[11px] text-text3 mt-2">Camera feed</div>
        </div>

        {/* Status + dots */}
        <div>
          <p className="text-[13px] text-text2 mb-1.5">{statusText}</p>
          <p className="text-[11px] text-text3 mb-1.5">Samples collected</p>
          <div className="flex gap-1.5 justify-center">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className={`w-2.5 h-2.5 rounded-full border-[1.5px] transition-all ${
                  i < count ? 'bg-sc-green border-sc-green' :
                  i === count && !done ? 'bg-accent border-accent animate-pulse' :
                  'bg-surface3 border-border'
                }`}
              />
            ))}
          </div>
        </div>

        <p className="text-[11.5px] text-text3 max-w-[260px] leading-relaxed">
          NFR-01: Raw images are discarded immediately after embedding extraction. Only mathematical vectors are stored.
        </p>

        {/* Progress bar */}
        <div className="w-full">
          <div className="flex justify-between text-[11px] text-text3 mb-1">
            <span>Enrollment progress</span>
            <span>{count} / 5</span>
          </div>
          <div className="h-1 bg-surface3 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-accent to-accent2 transition-all duration-300"
              style={{ width: `${(count / 5) * 100}%` }}
            />
          </div>
        </div>
      </div>
    </Modal>
  )
}
