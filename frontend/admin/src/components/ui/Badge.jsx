const ROLE_STYLES = {
  student:  'bg-accent-lt text-accent-dk',
  lecturer: 'bg-accent2-lt text-accent2-dk',
  admin:    'bg-sc-yellow-lt text-sc-yellow',
}

const STATUS_STYLES = {
  active:   'bg-sc-green-lt text-sc-green-dk',
  inactive: 'bg-surface3 text-text2',
}

export function RoleBadge({ role }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-[5px] text-[11px] font-semibold tracking-wide ${ROLE_STYLES[role.toLowerCase()] ?? 'bg-surface3 text-text2'}`}>
      {role}
    </span>
  )
}

export function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-[5px] text-[11px] font-semibold tracking-wide ${STATUS_STYLES[status.toLowerCase()] ?? 'bg-surface3 text-text2'}`}>
      {status}
    </span>
  )
}

export function FaceBadge({ enrolled }) {
  return enrolled
    ? <span className="inline-flex items-center gap-1 text-[11px] font-medium text-sc-green-dk">✓ Enrolled</span>
    : <span className="inline-flex items-center gap-1 text-[11px] font-medium text-text3">— Not enrolled</span>
}

export function NavBadge({ count, color }) {
  return (
    <span
      className="ml-auto text-[10px] font-semibold text-white px-1.5 py-0.5 rounded-full"
      style={{ background: color ?? '#1B6EF3' }}
    >
      {count}
    </span>
  )
}
