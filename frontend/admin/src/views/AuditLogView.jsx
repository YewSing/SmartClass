import { useState, useEffect } from 'react'
import { getAuditLog } from '../services/api'

export default function AuditLogView() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAuditLog()
      .then(data => setLogs(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const fmt = (iso) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleString('en', { dateStyle: 'short', timeStyle: 'medium' })
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Audit Log</span>
        <span className="text-[11px] text-text3 ml-1">({logs.length} entries)</span>
        <select className="bg-surface2 border border-border rounded-lg px-2.5 py-1.5 text-[13px] text-text2 outline-none ml-auto">
          <option>All Actions</option>
          <option>User Management</option>
          <option>Attendance Override</option>
          <option>Face Enrollment</option>
        </select>
      </div>

      {loading ? (
        <div className="px-5 py-8 text-center text-[13px] text-text3">Loading…</div>
      ) : logs.length === 0 ? (
        <div className="px-5 py-8 text-center text-[13px] text-text3">No audit entries yet.</div>
      ) : (
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-surface2">
              {['Timestamp', 'Actor', 'Action', 'Target', 'Details'].map(h => (
                <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map(row => (
              <tr key={row.id} className="hover:bg-gray-50">
                <td className="px-5 py-3 border-b border-border font-sans text-[11px] text-text3">{fmt(row.ts)}</td>
                <td className="px-5 py-3 border-b border-border text-[13.5px] text-text2">{row.actor?.name ?? '—'}</td>
                <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text2">{row.action}</td>
                <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text2">{row.target_type} #{row.target_id}</td>
                <td className="px-5 py-3 border-b border-border text-[11.5px] text-text3">
                  {row.new_val ? JSON.stringify(JSON.parse(row.new_val)).slice(0, 60) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="px-5 py-3.5 border-t border-border">
        <span className="text-[11px] text-text3">🔒 Immutable — NFR-05: Audit records cannot be modified or deleted</span>
      </div>
    </div>
  )
}
