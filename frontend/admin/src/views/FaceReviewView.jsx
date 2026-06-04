import { useAdmin } from '../context/AdminContext'
import Button from '../components/ui/Button'

export default function FaceReviewView() {
  const { state, dismissReview, openModal, toast } = useAdmin()
  const queue = state.unrecognisedQueue

  const handleDismiss = async (id) => {
    try {
      await dismissReview(id)
      toast('Review entry dismissed', 'info')
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const handlePromote = (entry) => {
    openModal('faceReviewPromote', { reviewId: entry.id })
  }

  const confidenceCls = (c) =>
    c >= 0.4 ? 'text-sc-orange' : 'text-red-500'

  return (
    <div className="space-y-5">
      {/* Banner */}
      <div className="bg-surface border border-border rounded-xl px-5 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-sc-orange-lt flex items-center justify-center text-lg flex-shrink-0">⚠</div>
        <div>
          <div className="text-[14px] font-semibold text-text1">Unrecognised Face Review Queue</div>
          <div className="text-[12px] text-text3 mt-0.5">
            UC-07 / FR-005 — {queue.length} {queue.length === 1 ? 'face' : 'faces'} flagged by the recognition pipeline.
            Identify each face to promote it to enrollment, or dismiss if not a student.
          </div>
        </div>
        {queue.length > 0 && (
          <span className="ml-auto text-[13px] font-semibold text-sc-orange bg-sc-orange-lt border border-sc-orange/30 rounded-full px-3 py-1 flex-shrink-0">
            {queue.length} pending
          </span>
        )}
      </div>

      {/* Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        {queue.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="text-4xl mb-3">✓</div>
            <div className="text-[14px] font-medium text-text2 mb-1">Review queue is empty</div>
            <div className="text-[12.5px] text-text3">All flagged faces have been reviewed</div>
          </div>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-surface2">
                {['Entry ID', 'Timestamp', 'Camera Source', 'Session', 'Confidence', 'Occurrences', 'Actions'].map(h => (
                  <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {queue.map(entry => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text3">{entry.id}</td>
                  <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text2">{entry.ts}</td>
                  <td className="px-5 py-3 border-b border-border text-[13px] text-text2">{entry.camera}</td>
                  <td className="px-5 py-3 border-b border-border text-[13px] text-text2">{entry.session}</td>
                  <td className="px-5 py-3 border-b border-border">
                    <span className={`text-[13px] font-semibold ${confidenceCls(entry.confidence)}`}>
                      {Math.round(entry.confidence * 100)}%
                    </span>
                    <span className="text-[11px] text-text3 ml-1">below threshold</span>
                  </td>
                  <td className="px-5 py-3 border-b border-border text-[13px] text-text2">
                    {entry.occurrences}×
                  </td>
                  <td className="px-5 py-3 border-b border-border">
                    <div className="flex gap-1.5">
                      <Button variant="primary" size="sm" onClick={() => handlePromote(entry)}>
                        ⊙ Identify & Enroll
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDismiss(entry.id)}>
                        Dismiss
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
