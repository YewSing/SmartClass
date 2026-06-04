import { useEffect, useState, useCallback } from 'react'
import { useAdmin } from '../../context/AdminContext'
import * as api from '../../services/api'

function OccurrenceTypeBadge({ type }) {
  const isLec = type === 'LECTURE'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${isLec ? 'bg-accent-lt text-accent' : 'bg-green-500/20 text-green-600'}`}>
      {isLec ? 'Lecture' : 'Tutorial'}
    </span>
  )
}

function RosterPanel({ occurrence, onClose }) {
  const { state, toast } = useAdmin()
  const [roster, setRoster] = useState([])
  const [rosterSearch, setRosterSearch] = useState('')
  const [addSearch, setAddSearch] = useState('')
  const [busy, setBusy] = useState(null)

  const reload = useCallback(async () => {
    try {
      const students = await api.getOccurrenceStudents(occurrence.id)
      setRoster(students)
    } catch (e) {
      toast(e.message, 'error')
    }
  }, [occurrence.id, toast])

  useEffect(() => { reload() }, [reload])

  const rosterIds = new Set(roster.map(s => s.user_id))

  const filteredRoster = roster.filter(s =>
    s.name.toLowerCase().includes(rosterSearch.toLowerCase()) ||
    s.matric_no.includes(rosterSearch)
  )

  const allStudents = (state.users ?? []).filter(u => u.role === 'Student')
  const addable = allStudents.filter(u =>
    !rosterIds.has(u.id) && (
      u.name.toLowerCase().includes(addSearch.toLowerCase()) ||
      (u.matric ?? '').includes(addSearch)
    )
  )

  const handleRemove = async (studentUserId) => {
    setBusy(studentUserId)
    try {
      await api.unenrollFromOccurrence(occurrence.id, studentUserId)
      await reload()
      toast('Student removed from occurrence', 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(null)
    }
  }

  const handleAdd = async (studentUserId) => {
    setBusy(studentUserId)
    try {
      await api.enrollInOccurrence(occurrence.id, studentUserId)
      await reload()
      toast('Student enrolled in occurrence', 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(null)
    }
  }

  const occ = occurrence
  const scheduleLabel = `${occ.day_of_week} ${occ.start_time}–${occ.end_time}`

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 mb-4">
        <button onClick={onClose} className="text-text3 hover:text-text1 transition-colors">
          <i className="fa-solid fa-arrow-left" />
        </button>
        <div>
          <div className="flex items-center gap-2">
            <OccurrenceTypeBadge type={occ.type} />
            {occ.label && <span className="text-text1 font-semibold text-[13px]">{occ.label}</span>}
          </div>
          <p className="text-[12px] text-text3 mt-0.5">{scheduleLabel} · {occ.room}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 flex-1 min-h-0">
        {/* Enrolled students */}
        <div className="flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-text3 uppercase tracking-[0.07em]">
              Enrolled ({roster.length})
            </span>
          </div>
          <input
            value={rosterSearch}
            onChange={e => setRosterSearch(e.target.value)}
            placeholder="Search enrolled…"
            className="mb-2 px-3 py-1.5 rounded-lg bg-surface2 border border-border text-[13px] text-text1 placeholder:text-text3 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <div className="flex-1 overflow-y-auto space-y-1">
            {filteredRoster.map(s => (
              <div key={s.user_id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface2 border border-border hover:border-text3 transition-colors">
                <div>
                  <p className="text-[13px] text-text1 leading-tight">{s.name}</p>
                  <p className="text-[11px] text-text3">{s.matric_no}</p>
                </div>
                <button
                  disabled={busy === s.user_id}
                  onClick={() => handleRemove(s.user_id)}
                  className="text-text3 hover:text-red-500 transition-colors disabled:opacity-40 ml-2 flex-shrink-0"
                >
                  <i className="fa-solid fa-xmark" />
                </button>
              </div>
            ))}
            {filteredRoster.length === 0 && (
              <p className="text-[12px] text-text3 text-center py-4">No students enrolled.</p>
            )}
          </div>
        </div>

        {/* Add students */}
        <div className="flex flex-col min-h-0">
          <span className="text-[11px] font-semibold text-text3 uppercase tracking-[0.07em] mb-2">
            Add Student
          </span>
          <input
            value={addSearch}
            onChange={e => setAddSearch(e.target.value)}
            placeholder="Search by name or matric…"
            className="mb-2 px-3 py-1.5 rounded-lg bg-surface2 border border-border text-[13px] text-text1 placeholder:text-text3 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <div className="flex-1 overflow-y-auto space-y-1">
            {addSearch.length < 2 ? (
              <p className="text-[12px] text-text3 text-center py-4">Type to search students.</p>
            ) : addable.length === 0 ? (
              <p className="text-[12px] text-text3 text-center py-4">No matches.</p>
            ) : (
              addable.slice(0, 30).map(u => (
                <div key={u.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-surface2 border border-border hover:border-text3 transition-colors">
                  <div>
                    <p className="text-[13px] text-text1 leading-tight">{u.name}</p>
                    <p className="text-[11px] text-text3">{u.matric}</p>
                  </div>
                  <button
                    disabled={busy === u.id}
                    onClick={() => handleAdd(u.id)}
                    className="text-text3 hover:text-green-600 transition-colors disabled:opacity-40 ml-2 flex-shrink-0"
                  >
                    <i className="fa-solid fa-plus" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CourseDetailModal() {
  const { state, closeModal } = useAdmin()
  const modal = state.modal
  const isOpen = modal?.type === 'courseDetail'

  const [occurrences, setOccurrences] = useState([])
  const [selectedOcc, setSelectedOcc] = useState(null)
  const { toast } = useAdmin()

  useEffect(() => {
    if (!isOpen) {
      setOccurrences([])
      setSelectedOcc(null)
      return
    }
    api.getCourseOccurrences(modal.data.courseId)
      .then(setOccurrences)
      .catch(e => toast(e.message, 'error'))
  }, [isOpen, modal?.data?.courseId])

  useEffect(() => {
    if (!isOpen) return
    const handler = (e) => { if (e.key === 'Escape') closeModal() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, closeModal])

  if (!isOpen) return null

  const { courseCode, courseName } = modal.data

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeModal() }}
    >
      <div className="bg-surface border border-border rounded-2xl w-full max-w-3xl mx-4 flex flex-col max-h-[85vh] shadow-xl">
        {/* Modal header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-border">
          <div>
            <p className="text-[11px] font-semibold text-accent uppercase tracking-widest mb-0.5">{courseCode}</p>
            <h2 className="text-[15px] font-bold text-text1">{courseName}</h2>
          </div>
          <button onClick={closeModal} className="text-text3 hover:text-text1 transition-colors mt-1">
            <i className="fa-solid fa-xmark text-lg" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 min-h-0">
          {selectedOcc ? (
            <RosterPanel occurrence={selectedOcc} onClose={() => setSelectedOcc(null)} />
          ) : (
            <div className="space-y-3">
              {occurrences.length === 0 ? (
                <p className="text-[13px] text-text3 text-center py-8">Loading occurrences…</p>
              ) : (
                occurrences.map(occ => (
                  <div key={occ.id} className="flex items-center justify-between p-4 rounded-xl bg-surface2 border border-border hover:border-text3 transition-colors">
                    <div className="flex items-start gap-3">
                      <OccurrenceTypeBadge type={occ.type} />
                      <div>
                        {occ.label && (
                          <p className="text-[13px] font-semibold text-text1 leading-tight">{occ.label}</p>
                        )}
                        <p className="text-[12px] text-text3 mt-0.5">
                          {occ.day_of_week} · {occ.start_time}–{occ.end_time} · {occ.room ?? '—'}
                        </p>
                        <p className="text-[12px] text-text3 mt-0.5">
                          {occ.lecturer_name} · {occ.enrolled_count} students
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedOcc(occ)}
                      className="text-[13px] text-text2 hover:text-text1 border border-border rounded-md px-2.5 py-1 bg-transparent hover:bg-surface transition-all flex-shrink-0"
                    >
                      Manage Students
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
