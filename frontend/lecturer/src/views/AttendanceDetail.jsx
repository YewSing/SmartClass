import { useState } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { STUDENTS } from '../data/mockData'

export default function AttendanceDetail() {
  const { navigate, openModal } = useLecturer()
  const [search, setSearch] = useState('')
  const [sortAZ, setSortAZ] = useState(true)

  const filtered = [...STUDENTS]
    .filter(s => s.name.toLowerCase().includes(search.toLowerCase()) || s.id.includes(search))
    .sort((a, b) => sortAZ ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name))

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title="Week 6 — Session 1"
        sub="24 May 2025 · 10:05 AM"
        onBack={() => navigate('attendance-sessions')}
        right={<span className="badge green dot" style={{ marginLeft: 'auto' }}>Open</span>}
      />
      <div className="search-bar">
        <i className="fa fa-search"></i>
        <input type="text" placeholder="Search name or matric ID…" value={search} onChange={e => setSearch(e.target.value)} />
      </div>
      <div className="sort-row">
        <span className="sort-label">26 enrolled &nbsp;·&nbsp; 22 present · 3 absent · 1 unidentified</span>
        <button className="sort-btn" onClick={() => setSortAZ(v => !v)}>
          <i className={`fa ${sortAZ ? 'fa-sort-alpha-down' : 'fa-sort-alpha-up'}`}></i> {sortAZ ? 'A–Z' : 'Z–A'}
        </button>
      </div>
      <div className="scroll-body" style={{ background: 'var(--card)', borderTop: '1px solid var(--border)' }}>
        {filtered.map(s => (
          <div key={s.id} className="student-row" onClick={() => openModal('student', { name: s.name, id: s.id, status: s.status })}>
            <div className="student-avatar" style={{ background: s.avatarBg, color: s.avatarColor }}>{s.initials}</div>
            <div>
              <div className="student-name">{s.name}</div>
              <div className="student-id">{s.id}</div>
            </div>
            <div className="student-row-right">
              {s.status === 'present'      && <span className="badge green dot">Present</span>}
              {s.status === 'absent'       && <span className="badge red dot">Absent</span>}
              {s.status === 'unidentified' && <span className="badge orange dot">Unidentified</span>}
            </div>
          </div>
        ))}
        <div style={{ height: 20 }}></div>
      </div>
    </>
  )
}
