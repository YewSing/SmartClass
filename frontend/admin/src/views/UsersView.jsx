import { useState } from 'react'
import { useAdmin } from '../context/AdminContext'
import { avatarInitials } from '../components/ui/Avatar'
import { RoleBadge, StatusBadge } from '../components/ui/Badge'
import Button from '../components/ui/Button'

export default function UsersView() {
  const { state, dispatch, openModal } = useAdmin()
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')

  const filtered = state.users.filter(u =>
    (!search ||
      u.name.toLowerCase().includes(search.toLowerCase()) ||
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      String(u.matric ?? u.staffId ?? '').toLowerCase().includes(search.toLowerCase())
    ) &&
    (!roleFilter || u.role === roleFilter)
  )

  const openProfile = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('studentProfile')
  }

  const openDelete = (id) => {
    dispatch({ type: 'SELECT_USER', payload: id })
    openModal('confirmDelete')
  }

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">All Users</span>
        <div className="flex items-center gap-2 bg-surface2 border border-border rounded-lg px-3 py-1.5 ml-auto">
          <span className="text-text3 text-[13px]">⌕</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search name, ID…"
            className="bg-transparent outline-none text-[13px] text-text1 w-48 placeholder:text-text3"
          />
        </div>
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          className="bg-surface2 border border-border rounded-lg px-2.5 py-1.5 text-[13px] text-text2 outline-none"
        >
          <option value="">All Roles</option>
          <option>Student</option>
          <option>Lecturer</option>
          <option>Admin</option>
        </select>
        <Button variant="primary" size="sm" onClick={() => openModal('createUser')}>＋ Create User</Button>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            {['User', 'ID / Staff No.', 'Role', 'Contact', 'Status', 'Actions'].map(h => (
              <th key={h} className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.length ? filtered.map(u => (
            <tr key={u.id} className="hover:bg-gray-50">
              <td className="px-5 py-3 border-b border-border">
                <div className="flex items-center gap-2.5">
                  <div className="w-[30px] h-[30px] rounded-full flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0" style={{ background: u.color }}>
                    {avatarInitials(u.name)}
                  </div>
                  <div>
                    <div className="text-[13.5px] font-medium text-text1">{u.name}</div>
                    <div className="text-[11px] text-text3">{u.email}</div>
                  </div>
                </div>
              </td>
              <td className="px-5 py-3 border-b border-border font-sans text-[12px] text-text1">{u.matric ?? u.staffId ?? `#${u.id}`}</td>
              <td className="px-5 py-3 border-b border-border"><RoleBadge role={u.role} /></td>
              <td className="px-5 py-3 border-b border-border text-[12.5px] text-text2">{u.phone}</td>
              <td className="px-5 py-3 border-b border-border"><StatusBadge status={u.status} /></td>
              <td className="px-5 py-3 border-b border-border">
                <div className="flex gap-1.5">
                  <Button variant="ghost" size="sm" onClick={() => openProfile(u.id)}>✎ Edit</Button>
                  <Button variant="danger" size="sm" onClick={() => openDelete(u.id)}>✕</Button>
                </div>
              </td>
            </tr>
          )) : (
            <tr><td colSpan={6} className="text-center py-12 text-text3">
              <div className="text-3xl mb-3">◌</div>
              <div className="text-[14px] font-medium text-text2 mb-1">No users found</div>
              <div className="text-[12.5px]">Try adjusting your search or filter</div>
            </td></tr>
          )}
        </tbody>
      </table>

      <div className="flex items-center justify-between px-5 py-3.5 border-t border-border text-[12.5px] text-text3">
        <span>Showing <strong className="text-text2">{filtered.length}</strong> of <strong className="text-text2">{state.users.length}</strong> users</span>
      </div>
    </div>
  )
}
