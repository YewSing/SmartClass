import { useEffect } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'

export default function AttendanceSessions() {
  const { state, navigate, loadSessions, selectSession } = useLecturer()
  const { sessions } = state

  useEffect(() => { loadSessions() }, [loadSessions])

  const handleSessionClick = (session) => {
    selectSession(session)
    navigate('attendance-detail')
  }

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar title="Attendance" sub="All sessions" />
      <div className="scroll-body" style={{ background: 'var(--bg)' }}>
        {sessions.length === 0 ? (
          <div style={{ padding: '40px 24px', textAlign: 'center', color: 'var(--text-sub)', fontSize: 14 }}>
            No sessions yet. Open a session from the dashboard.
          </div>
        ) : (
          <>
            <div style={{ padding: '10px 16px 4px', fontSize: 12, color: 'var(--text-sub)' }}>
              {sessions.length} session{sessions.length !== 1 ? 's' : ''}
            </div>
            {sessions.map(s => (
              <div key={s.id} className="session-item" onClick={() => handleSessionClick(s)}>
                <div className="session-date-block" style={{ background: s.open ? 'var(--green-lt)' : 'var(--gray-100)' }}>
                  <div className="d" style={{ color: s.open ? 'var(--green)' : 'var(--gray-600)' }}>{s.day}</div>
                  <div className="m" style={{ color: s.open ? 'var(--green-dk)' : 'var(--gray-500)' }}>{s.month}</div>
                </div>
                <div className="session-info">
                  <div className="title">{s.class_code} — {s.class_name}</div>
                  <div className="sub">
                    {s.open
                      ? <>{s.time} &nbsp;·&nbsp; <span className="badge green dot" style={{ fontSize: 10, padding: '2px 6px' }}>Open now</span></>
                      : <>{s.time}{s.duration ? ` · (${s.duration})` : ''}</>}
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
          </>
        )}
        <div style={{ height: 16 }}></div>
      </div>
    </>
  )
}
