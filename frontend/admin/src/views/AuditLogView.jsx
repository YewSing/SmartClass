import { AUDIT_LOG } from '../data/users'

export default function AuditLogView() {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Audit Log</span>
        <div className="flex items-center gap-2 bg-surface2 border border-border rounded-lg px-3 py-1.5 ml-auto">
          <span className="text-text3 text-[13px]">⌕</span>
          <input placeholder="Filter log…" className="bg-transparent outline-none text-[13px] text-text1 w-48 placeholder:text-text3" />
        </div>
        <select className="bg-surface2 border border-border rounded-lg px-2.5 py-1.5 text-[13px] text-text2 outline-none">
          <option>All Actions</option>
          <option>User Management</option>
          <option>Attendance Override</option>
          <option>Face Enrollment</option>
        </select>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            {['Timestamp', 'Actor', 'Action', 'Target', 'Details'].map(h => (
              <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {AUDIT_LOG.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-5 py-3 border-b border-border font-sans text-[11px] text-text3">{row.ts}</td>
              <td className="px-5 py-3 border-b border-border text-[13.5px] text-text2">{row.actor}</td>
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text2">{row.action}</td>
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text2">{row.target}</td>
              <td className="px-5 py-3 border-b border-border text-[11.5px] text-text3">{row.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="px-5 py-3.5 border-t border-border">
        <span className="text-[11px] text-text3">🔒 Immutable — NFR-05: Audit records cannot be modified or deleted</span>
      </div>
    </div>
  )
}
