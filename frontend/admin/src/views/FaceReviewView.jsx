import { useEffect, useState } from 'react'
import { useAdmin } from '../context/AdminContext'
import Button from '../components/ui/Button'
import Pagination from '../components/ui/Pagination'

function MatchBadge({ confidence }) {
  if (confidence === null) return <span className="text-[12px] text-text3">—</span>
  const pct = Math.round(confidence * 100)
  if (confidence >= 0.65)
    return <span className="inline-flex items-center gap-1 text-[11.5px] font-semibold px-2 py-0.5 rounded-full bg-green-50 border border-green-200 text-green-700">{pct}% strong</span>
  if (confidence >= 0.40)
    return <span className="inline-flex items-center gap-1 text-[11.5px] font-semibold px-2 py-0.5 rounded-full bg-sc-orange-lt border border-sc-orange/30 text-sc-orange">{pct}% possible</span>
  return <span className="inline-flex items-center gap-1 text-[11.5px] font-semibold px-2 py-0.5 rounded-full bg-red-50 border border-red-200 text-red-600">{pct}% weak</span>
}

export default function FaceReviewView() {
  const { state, dismissReview, openModal, toast, loadReviewQueue } = useAdmin()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const queue = state.unrecognisedQueue

  useEffect(() => {
    loadReviewQueue()
  }, [loadReviewQueue])

  // Reset to first page when queue length changes (new entries or dismissals)
  useEffect(() => { setPage(1) }, [queue.length, pageSize])

  const paginated = queue.slice((page - 1) * pageSize, page * pageSize)

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

  return (
    <div className="space-y-5">
      {/* Banner */}
      <div className="bg-surface border border-border rounded-xl px-5 py-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-sc-orange-lt flex items-center justify-center text-lg flex-shrink-0">⚠</div>
        <div>
          <div className="text-[14px] font-semibold text-text1">Unrecognised Face Review Queue</div>
          <div className="text-[12px] text-text3 mt-0.5">
            {queue.length} {queue.length === 1 ? 'face' : 'faces'} flagged by the recognition pipeline.
            Each entry shows the closest registered student match — confirm identity and optionally mark attendance to resolve.
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
          <>
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface2">
                  {['#', 'Flagged At', 'Closest Match', 'Match Score', 'Class / Session', 'Seen', 'Actions'].map(h => (
                    <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-4 py-2.5 text-left border-b border-border">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paginated.map(entry => (
                  <tr key={entry.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 border-b border-border font-sans text-[12px] text-text3">{entry.id}</td>
                    <td className="px-4 py-3 border-b border-border font-sans text-[12px] text-text2 whitespace-nowrap">{entry.ts}</td>
                    <td className="px-4 py-3 border-b border-border">
                      {entry.closestMatchName
                        ? <span className="text-[13px] font-medium text-text1">{entry.closestMatchName}</span>
                        : <span className="text-[12px] text-text3 italic">No registered faces</span>
                      }
                    </td>
                    <td className="px-4 py-3 border-b border-border">
                      <MatchBadge confidence={entry.closestMatchConfidence} />
                    </td>
                    <td className="px-4 py-3 border-b border-border">
                      {entry.className
                        ? (
                          <div>
                            <div className="text-[12.5px] font-medium text-text1">{entry.className}</div>
                            {entry.sessionDate && (
                              <div className="text-[11px] text-text3 mt-0.5">{entry.sessionDate}</div>
                            )}
                          </div>
                        )
                        : <span className="text-[12px] text-text3">—</span>
                      }
                    </td>
                    <td className="px-4 py-3 border-b border-border text-[13px] font-semibold text-text2">
                      {entry.occurrences}×
                    </td>
                    <td className="px-4 py-3 border-b border-border">
                      <div className="flex gap-1.5">
                        <Button variant="primary" size="sm" onClick={() => handlePromote(entry)}>
                          Resolve
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
            <Pagination
              total={queue.length}
              page={page}
              pageSize={pageSize}
              onPage={setPage}
              onPageSize={setPageSize}
            />
          </>
        )}
      </div>
    </div>
  )
}
