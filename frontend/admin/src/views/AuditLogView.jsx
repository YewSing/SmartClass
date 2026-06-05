import { useState, useEffect } from 'react'
import { getAuditLog } from '../services/api'
import { useAdmin } from '../context/AdminContext'
import Pagination from '../components/ui/Pagination'

// ── Action display metadata ────────────────────────────────────────────────────
const ACTION_META = {
  USER_CREATE:         { label: 'Created account',      category: 'User Management',   cls: 'bg-green-50 text-green-700 border-green-200' },
  USER_UPDATE:         { label: 'Updated profile',       category: 'User Management',   cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  USER_DEACTIVATE:     { label: 'Deactivated account',  category: 'User Management',   cls: 'bg-red-50 text-red-600 border-red-200' },
  PASSWORD_RESET:      { label: 'Reset password',        category: 'User Management',   cls: 'bg-surface2 text-text3 border-border' },
  ENROLL_ADD:          { label: 'Added to class',        category: 'Class Enrollment',  cls: 'bg-green-50 text-green-700 border-green-200' },
  ENROLL_REMOVE:       { label: 'Removed from class',   category: 'Class Enrollment',  cls: 'bg-red-50 text-red-600 border-red-200' },
  FACE_ENROLL:         { label: 'Registered face data', category: 'Face Registration', cls: 'bg-green-50 text-green-700 border-green-200' },
  FACE_REMOVE:         { label: 'Removed face data',    category: 'Face Registration', cls: 'bg-red-50 text-red-600 border-red-200' },
  FACE_REVIEW_DISMISS: { label: 'Dismissed face alert', category: 'Face Registration', cls: 'bg-surface2 text-text3 border-border' },
  FACE_PROMOTE:        { label: 'Resolved face alert',  category: 'Face Registration', cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  ATTENDANCE_OVERRIDE: { label: 'Overrode attendance',  category: 'Attendance',        cls: 'bg-sc-orange-lt text-sc-orange border-sc-orange/30' },
}

const TARGET_LABELS = {
  face_review_entry: 'Review entry',
  attendance_record: 'Attendance record',
}

const CATEGORIES = ['All Actions', 'User Management', 'Class Enrollment', 'Face Registration', 'Attendance']

// ── Helpers ────────────────────────────────────────────────────────────────────
function formatTarget(type, id, users) {
  if (type === 'user' || type === 'student') {
    const found = users.find(u => u.id === parseInt(id))
    if (found) return found.name
  }
  return `${TARGET_LABELS[type] ?? type} #${id}`
}

function humanKey(k) { return k.replace(/_/g, ' ') }

function formatDetails(action, old_val_str, new_val_str) {
  try {
    const nv = new_val_str ? JSON.parse(new_val_str) : null
    const ov = old_val_str ? JSON.parse(old_val_str) : null
    switch (action) {
      case 'USER_CREATE':
        return nv ? `${nv.role} · ${nv.email}` : null
      case 'USER_UPDATE': {
        if (!nv) return null
        const parts = Object.entries(nv)
          .filter(([k]) => k !== 'password_hash')
          .map(([k, v]) => `${humanKey(k)}: ${v}`)
        return parts.length ? parts.join(' · ') : null
      }
      case 'ENROLL_ADD':
        return nv?.occurrence_id ? `Occurrence #${nv.occurrence_id}` : null
      case 'ENROLL_REMOVE':
        return ov?.occurrence_id ? `Occurrence #${ov.occurrence_id}` : null
      case 'FACE_PROMOTE': {
        if (!nv) return null
        const parts = [`Student #${nv.student_user_id}`]
        if (nv.mark_present) parts.push('marked present')
        return parts.join(' · ')
      }
      case 'ATTENDANCE_OVERRIDE':
        return ov?.status && nv?.status ? `${ov.status} → ${nv.status}` : null
      default:
        return null
    }
  } catch { return null }
}

// ── Component ──────────────────────────────────────────────────────────────────
export default function AuditLogView() {
  const { state } = useAdmin()
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('All Actions')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  useEffect(() => {
    getAuditLog(1, 200)
      .then(data => setLogs(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // Reset to page 1 when filter or page size changes
  useEffect(() => { setPage(1) }, [filter, pageSize])

  const fmt = (iso) =>
    iso ? new Date(iso).toLocaleString('en-MY', { dateStyle: 'short', timeStyle: 'medium', timeZone: 'Asia/Kuala_Lumpur' }) : '—'

  const filtered = filter === 'All Actions'
    ? logs
    : logs.filter(row => (ACTION_META[row.action]?.category ?? 'Other') === filter)

  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Audit Log</span>
        <span className="text-[11px] text-text3 ml-1">({filtered.length} entries)</span>
        <select
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="bg-surface2 border border-border rounded-lg px-2.5 py-1.5 text-[13px] text-text2 outline-none ml-auto"
        >
          {CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="px-5 py-8 text-center text-[13px] text-text3">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="px-5 py-8 text-center text-[13px] text-text3">No audit entries yet.</div>
      ) : (
        <>
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-surface2">
                {['Timestamp', 'Actor', 'Action', 'Target', 'Details'].map(h => (
                  <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginated.map(row => {
                const meta = ACTION_META[row.action]
                const details = formatDetails(row.action, row.old_val, row.new_val)
                return (
                  <tr key={row.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 border-b border-border font-sans text-[11px] text-text3 whitespace-nowrap">{fmt(row.ts)}</td>
                    <td className="px-5 py-3 border-b border-border text-[13px] text-text2">{row.actor?.name ?? '—'}</td>
                    <td className="px-5 py-3 border-b border-border">
                      <span className={`inline-flex text-[11.5px] font-semibold px-2 py-0.5 rounded-full border ${meta?.cls ?? 'bg-surface2 text-text3 border-border'}`}>
                        {meta?.label ?? row.action}
                      </span>
                    </td>
                    <td className="px-5 py-3 border-b border-border text-[13px] text-text2">
                      {formatTarget(row.target_type, row.target_id, state.users)}
                    </td>
                    <td className="px-5 py-3 border-b border-border text-[11.5px] text-text3">
                      {details ?? '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <Pagination
            total={filtered.length}
            page={page}
            pageSize={pageSize}
            onPage={setPage}
            onPageSize={setPageSize}
          />
        </>
      )}

    </div>
  )
}
