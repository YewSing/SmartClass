import { useState, useEffect } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

function ConfidenceBadge({ confidence }) {
  if (confidence === null || confidence === undefined) return null
  const pct = Math.round(confidence * 100)
  if (confidence >= 0.65)
    return <span className="text-[12px] font-semibold px-2.5 py-1 rounded-full bg-green-50 border border-green-200 text-green-700">{pct}% — Strong match</span>
  if (confidence >= 0.40)
    return <span className="text-[12px] font-semibold px-2.5 py-1 rounded-full bg-sc-orange-lt border border-sc-orange/30 text-sc-orange">{pct}% — Possible match</span>
  return <span className="text-[12px] font-semibold px-2.5 py-1 rounded-full bg-red-50 border border-red-200 text-red-600">{pct}% — Weak guess</span>
}

function cardBorder(confidence) {
  if (confidence == null) return 'border-border bg-surface2'
  if (confidence >= 0.65) return 'border-green-200 bg-green-50/40'
  if (confidence >= 0.40) return 'border-sc-orange/30 bg-sc-orange-lt/30'
  return 'border-red-200 bg-red-50/40'
}

export default function FaceReviewPromoteModal() {
  const { state, promoteReview, closeModal, toast } = useAdmin()
  const [step, setStep] = useState(1)
  const [selectedUserId, setSelectedUserId] = useState('')
  const [markPresent, setMarkPresent] = useState(true)
  const [loading, setLoading] = useState(false)

  const isOpen = state.modal?.type === 'faceReviewPromote'
  const reviewId = isOpen ? (state.modal.data?.reviewId ?? null) : null
  const entry = reviewId !== null ? (state.unrecognisedQueue.find(e => e.id === reviewId) ?? null) : null

  // Must be before any early returns (Rules of Hooks)
  useEffect(() => {
    if (entry) {
      setStep(1)
      setMarkPresent(true)
      if (entry.closestMatchId) setSelectedUserId(String(entry.closestMatchId))
    }
  }, [entry?.id])

  if (!isOpen || !entry) return null

  const students = state.users.filter(u => u.role === 'Student')
  const selectedStudent = students.find(u => String(u.id) === selectedUserId)
  const hasSession = entry.session !== '—'

  const handleClose = () => {
    closeModal()
    setSelectedUserId('')
    setStep(1)
    setMarkPresent(true)
  }

  const handleResolve = async () => {
    if (!selectedUserId) return
    const numericId = parseInt(selectedUserId, 10)
    const student = students.find(u => u.id === numericId)
    setLoading(true)
    try {
      await promoteReview(reviewId, numericId, markPresent && hasSession)
      closeModal()
      setSelectedUserId('')
      const action = markPresent && hasSession ? 'registered and marked present' : 'registered'
      toast(`${student?.name.split(' ')[0]} ${action}`, 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  // ── Step progress indicator ────────────────────────────────────────────────
  const stepBar = (
    <div className="flex items-center gap-1.5 mb-5">
      <div className="h-1 flex-1 rounded-full bg-accent" />
      <div className={`h-1 flex-1 rounded-full ${step >= 2 ? 'bg-accent' : 'bg-border'}`} />
    </div>
  )

  // ── Step 1: Confirm Identity ───────────────────────────────────────────────
  if (step === 1) {
    return (
      <Modal
        title="Resolve Unrecognised Face"
        subtitle="Step 1 of 2 — Confirm student identity"
        onClose={handleClose}
        footer={
          <>
            <Button variant="ghost" onClick={handleClose}>Cancel</Button>
            <Button variant="primary" onClick={() => setStep(2)} disabled={!selectedUserId}>
              Next →
            </Button>
          </>
        }
      >
        {stepBar}

        {/* AI Suggested Match card */}
        <div className={`border rounded-xl p-4 mb-5 ${cardBorder(entry.closestMatchConfidence)}`}>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-text3 mb-3">
            AI Closest Match
          </div>
          {entry.closestMatchName ? (
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-surface3 border border-border flex items-center justify-center flex-shrink-0">
                <i className="fa-solid fa-circle-user text-[20px] text-text3" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-semibold text-text1 truncate mb-1">{entry.closestMatchName}</div>
                <ConfidenceBadge confidence={entry.closestMatchConfidence} />
                <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-text3">
                  {entry.className && (
                    <span><i className="fa-solid fa-chalkboard mr-1" />{entry.className}{entry.sessionDate ? ` · ${entry.sessionDate}` : ''}</span>
                  )}
                  <span>👁 Seen {entry.occurrences}× total</span>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-[13px] text-text3 italic">No enrolled faces in the system to compare against.</p>
          )}
        </div>

        {/* Student selector */}
        <div>
          <label className="block text-[12.5px] font-semibold text-text2 mb-1.5">
            Assign to student <span className="text-red-500">*</span>
          </label>
          {students.length === 0 ? (
            <p className="text-[13px] text-text3 bg-surface2 border border-border rounded-lg px-3 py-2.5">No students found.</p>
          ) : (
            <select
              value={selectedUserId}
              onChange={e => setSelectedUserId(e.target.value)}
              className="w-full bg-surface2 border border-border rounded-lg px-3 py-2 text-[13px] text-text1 outline-none focus:border-accent"
            >
              <option value="">— Select a student —</option>
              {students.map(u => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          )}
        </div>
      </Modal>
    )
  }

  // ── Step 2: Mark Attendance ────────────────────────────────────────────────
  return (
    <Modal
      title="Resolve Unrecognised Face"
      subtitle="Step 2 of 2 — Mark session attendance"
      onClose={handleClose}
      footer={
        <>
          <Button variant="ghost" onClick={() => setStep(1)}>← Back</Button>
          <Button variant="primary" onClick={handleResolve} disabled={loading}>
            {loading ? 'Resolving…' : '⊙ Resolve'}
          </Button>
        </>
      }
    >
      {stepBar}

      {/* Confirmed student */}
      <div className="bg-surface2 border border-border rounded-xl px-4 py-3 mb-5 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-base flex-shrink-0">✓</div>
        <div>
          <div className="text-[13px] font-semibold text-text1">{selectedStudent?.name}</div>
          <div className="text-[11.5px] text-text3">Identity confirmed</div>
        </div>
      </div>

      {/* Attendance toggle */}
      <div className={`border rounded-xl p-4 ${hasSession ? 'border-border bg-surface2' : 'border-border bg-surface3 opacity-60'}`}>
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            id="mark-present"
            checked={markPresent && hasSession}
            onChange={e => setMarkPresent(e.target.checked)}
            disabled={!hasSession}
            className="mt-0.5 w-4 h-4 accent-accent flex-shrink-0"
          />
          <label htmlFor="mark-present" className={`flex-1 ${hasSession ? 'cursor-pointer' : 'cursor-not-allowed'}`}>
            <div className="text-[13px] font-medium text-text1">Mark as present for this session</div>
            {hasSession ? (
              <div className="text-[11.5px] text-text3 mt-0.5">
                {entry.className
                  ? <><i className="fa-solid fa-chalkboard mr-1" />{entry.className}{entry.sessionDate ? ` · ${entry.sessionDate}` : ''}</>
                  : <>Session {entry.session}</>
                }
              </div>
            ) : (
              <div className="text-[11.5px] text-text3 mt-0.5">No session context — face was detected outside a tracked session</div>
            )}
          </label>
        </div>
      </div>

      {selectedStudent?.face && (
        <div className="flex items-start gap-2 mt-4 bg-sc-orange-lt border border-sc-orange/30 rounded-lg px-3 py-2.5 text-[12px] text-sc-orange">
          <span className="flex-shrink-0 mt-0.5">⚠</span>
          <span>This student already has face data. Registration will replace it with the captured embedding.</span>
        </div>
      )}
    </Modal>
  )
}
