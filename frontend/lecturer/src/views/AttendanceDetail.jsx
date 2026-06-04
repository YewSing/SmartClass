import { useState, useEffect } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'

export default function AttendanceDetail() {
  const { state, navigate, openModal, loadStudents } = useLecturer()
  const { students, selectedSession } = state
  const [search, setSearch] = useState('')
  const [sortAZ, setSortAZ] = useState(true)

  useEffect(() => {
    if (selectedSession?.id) loadStudents(selectedSession.id)
  }, [selectedSession?.id, loadStudents])

  const filtered = [...students]
    .filter(s => s.name.toLowerCase().includes(search.toLowerCase()) || s.id.includes(search))
    .sort((a, b) => sortAZ ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name))

  const present = students.filter(s => s.status === 'present').length
  const absent  = students.filter(s => s.status === 'absent').length
  const unid    = students.filter(s => s.status === 'unidentified').length

  const sessionTitle = selectedSession
    ? `${selectedSession.class_code} — ${selectedSession.month} ${selectedSession.day}`
    : 'Attendance Detail'

  const sessionSub = selectedSession
    ? `${selectedSession.time}${selectedSession.open ? ' · Open' : selectedSession.duration ? ` · ${selectedSession.duration}` : ''}`
    : ''

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title={sessionTitle}
        sub={sessionSub}
        onBack={() => navigate('attendance-sessions')}
        right={selectedSession?.open ? <span className="badge green dot" style={{ marginLeft: 'auto' }}>Open</span> : null}
      />
      <div className="search-bar">
        <i className="fa fa-search"></i>
        <input type="text" placeholder="Search name or matric ID…" value={search} onChange={e => setSearch(e.target.value)} />
      </div>
      <div className="sort-row">
        <span className="sort-label">
          {students.length} enrolled &nbsp;·&nbsp; {present} present · {absent} absent{unid > 0 ? ` · ${unid} unidentified` : ''}
        </span>
        <button className="sort-btn" onClick={() => setSortAZ(v => !v)}>
          <i className={`fa ${sortAZ ? 'fa-sort-alpha-down' : 'fa-sort-alpha-up'}`}></i> {sortAZ ? 'A–Z' : 'Z–A'}
        </button>
      </div>
      <div className="scroll-body" style={{ background: 'var(--card)', borderTop: '1px solid var(--border)' }}>
        {filtered.map(s => (
          <div key={s.id} className="student-row" onClick={() => openModal('student', s)}>
            <div className="student-avatar" style={{ background: s.avatarBg, color: s.avatarColor }}>{s.initials}</div>
            <div>
              <div className="student-name">{s.name}</div>
              <div className="student-id">{s.id}</div>
            </div>
            <div className="student-row-right">
              {s.overridden && <span style={{ fontSize: 10, color: 'var(--text-hint)', marginRight: 4 }}>✎</span>}
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
