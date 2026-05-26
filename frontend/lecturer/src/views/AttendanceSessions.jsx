import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { SESSIONS } from '../data/mockData'

export default function AttendanceSessions() {
  const { navigate } = useLecturer()
  return (
    <>
      <StatusBar time="10:14" />
      <Topbar title="Attendance" sub="WIA2005 — Software Engineering" />
      <div className="filter-row" style={{ flexShrink: 0 }}>
        <select style={{ flex: 1, padding: '7px 10px', fontSize: 12 }}>
          <option>WIA2005 — Soft. Eng.</option>
          <option>WIA2004 — Data Mining</option>
        </select>
        <select style={{ flex: 1, padding: '7px 10px', fontSize: 12 }}>
          <option>All sessions</option>
          <option>This month</option>
          <option>Sem 2 2024/25</option>
        </select>
      </div>
      <div className="scroll-body" style={{ background: 'var(--bg)' }}>
        <div style={{ padding: '10px 16px 4px', fontSize: 12, color: 'var(--text-sub)' }}>12 sessions · Sem 2 2024/25</div>
        {SESSIONS.map(s => (
          <div key={s.id} className="session-item" onClick={() => navigate('attendance-detail')}>
            <div className="session-date-block" style={{ background: s.open ? 'var(--green-lt)' : 'var(--gray-100)' }}>
              <div className="d" style={{ color: s.open ? 'var(--green)' : 'var(--gray-600)' }}>{s.day}</div>
              <div className="m" style={{ color: s.open ? 'var(--green-dk)' : 'var(--gray-500)' }}>{s.month}</div>
            </div>
            <div className="session-info">
              <div className="title">Week {s.week} — Session {s.session}</div>
              <div className="sub">
                {s.open
                  ? <>{s.time} &nbsp;·&nbsp; <span className="badge green dot" style={{ fontSize: 10, padding: '2px 6px' }}>Open now</span></>
                  : <>{s.time}{s.duration ? ` – (${s.duration})` : ''}</>}
              </div>
              <div className="session-stats-row">
                <span className="sess-chip" style={{ background: 'var(--green-lt)', color: 'var(--green-dk)' }}>{s.present} Present</span>
                <span className="sess-chip" style={{ background: 'var(--red-lt)', color: 'var(--red-dk)' }}>{s.absent} Absent</span>
                {s.unid > 0 && <span className="sess-chip" style={{ background: 'var(--orange-lt)', color: 'var(--orange-dk)' }}>{s.unid} Unidentified</span>}
              </div>
            </div>
            <i className="fa fa-chevron-right" style={{ color: 'var(--gray-300)', fontSize: 13 }}></i>
          </div>
        ))}
        <div style={{ height: 16 }}></div>
      </div>
    </>
  )
}
