import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import { QUIZZES } from '../data/mockData'

export default function Dashboard() {
  const { state, dispatch, navigate, openModal } = useLecturer()
  const { sessionOpen } = state

  const badgeClass = sessionOpen ? 'badge green dot' : 'badge gray dot'
  const badgeText  = sessionOpen ? 'Session Open' : 'Session Closed'

  return (
    <div className="scroll-body">
      <StatusBar time="10:14" />

      <div className="app-header">
        <div className="app-brand">
          <div className="logo-icon"><i className="fa fa-graduation-cap"></i></div>
          <span className="brand-name">SmartClass</span>
        </div>
        <div className="profile-btn" onClick={() => navigate('profile')}>TW</div>
      </div>

      <div className="dash-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 6 }}>
          <div>
            <div className="class-name">WIA2005 — Software Engineering</div>
            <div className="class-meta">Sem 2 2024/25 &nbsp;·&nbsp; DK 6, BLI Building</div>
          </div>
          <span className={badgeClass}>{badgeText}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
          {sessionOpen
            ? <div style={{ fontSize: 12, color: 'var(--text-sub)' }}><i className="fa fa-clock" style={{ fontSize: 11 }}></i> Opened 10:05 AM &nbsp;·&nbsp; 75 min remaining</div>
            : <div style={{ fontSize: 12, color: 'var(--text-sub)' }}>Last session: Today · 8:00 AM – 9:50 AM</div>}
          <button
            className={`session-toggle-btn ${sessionOpen ? 'can-close' : 'can-open'}`}
            onClick={() => dispatch({ type: 'TOGGLE_SESSION' })}
          >
            <i className={`fa ${sessionOpen ? 'fa-stop-circle' : 'fa-play-circle'}`}></i>
            {sessionOpen ? ' Close Session' : ' Open Session'}
          </button>
        </div>
      </div>

      {sessionOpen ? (
        <>
          <div className="section-header"><span className="section-title">Attendance</span></div>
          <div className="card tappable-card" onClick={() => navigate('attendance-sessions')} style={{ marginBottom: 10 }}>
            <div className="attend-stats">
              <div className="attend-stat present"><div className="num">22</div><div className="lbl">Present</div></div>
              <div className="attend-stat absent"><div className="num">3</div><div className="lbl">Absent</div></div>
              <div className="attend-stat unid"><div className="num">1</div><div className="lbl">Unidentified</div></div>
            </div>
            <div className="attend-card-footer"><i className="fa fa-chevron-right" style={{ fontSize: 10 }}></i> Tap to view full attendance</div>
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div className="card-label" style={{ margin: 0 }}>Confusion Rate</div>
              <button className="btn btn-sm btn-outline" onClick={() => openModal('confusion-reset')}>
                <i className="fa fa-redo"></i> Reset
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div className="confusion-num yellow">34%</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>Moderate Confusion</div>
                <div style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 2 }}>8 of 22 students flagged confusion</div>
              </div>
            </div>
            <div className="confusion-bar"><div className="confusion-fill" style={{ width: '34%', background: 'var(--yellow)' }}></div></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: 10, color: 'var(--green-dk)' }}>0%</span>
              <span style={{ fontSize: 10, color: 'var(--yellow-dk)' }}>20%</span>
              <span style={{ fontSize: 10, color: 'var(--red-dk)' }}>50%</span>
              <span style={{ fontSize: 10, color: 'var(--text-hint)' }}>100%</span>
            </div>
          </div>

          <div className="section-header" style={{ paddingTop: 4 }}><span className="section-title">Quiz &amp; Poll</span></div>
          <div className="create-quiz-btn" onClick={() => navigate('create-quiz')}>
            <div className="icon"><i className="fa fa-plus"></i></div>
            <div><div className="t">Create Quiz / Poll</div><div className="s">Push instantly to all student desks</div></div>
            <i className="fa fa-chevron-right" style={{ color: 'var(--blue)', marginLeft: 'auto', fontSize: 13 }}></i>
          </div>
          {QUIZZES.map(q => (
            <div key={q.id} className="quiz-card-item" onClick={() => openModal('quiz', q)}>
              <div className="qci-top">
                <div className="qci-q">{q.question}</div>
                <span className={`badge ${q.status === 'active' ? 'blue' : q.status === 'closed' ? 'gray' : 'yellow'}`}>
                  {q.status.charAt(0).toUpperCase() + q.status.slice(1)}
                </span>
              </div>
              <div className="qci-meta"><i className="fa fa-clock" style={{ fontSize: 11 }}></i> Today, {q.time}{q.timer ? ` · ${q.timer} timer` : ''}</div>
            </div>
          ))}
        </>
      ) : (
        <div className="no-session-state">
          <div className="no-session-icon"><i className="fa fa-hourglass-end"></i></div>
          <div className="no-session-title">No Active Session</div>
          <div className="no-session-sub">Session-bound data — attendance, confusion rate, and quizzes — will appear here once you open a session.</div>
          <div className="last-session-chip">
            <div className="l">Last session</div>
            <div className="v">Today · 8:00 AM – 9:50 AM &nbsp;(110 min)</div>
            <div style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 2 }}>Attendance: 24 present · 2 absent</div>
          </div>
          <button className="btn btn-green btn-full" onClick={() => dispatch({ type: 'TOGGLE_SESSION' })}>
            <i className="fa fa-play-circle"></i> Open Session
          </button>
        </div>
      )}

      <div style={{ paddingTop: 4 }}>
        <div className="section-header" style={{ paddingTop: 8, paddingBottom: 6 }}>
          <span className="section-title">Environment</span>
          <span style={{ fontSize: 11, color: 'var(--text-hint)', fontStyle: 'italic' }}>Always live · not session-bound</span>
        </div>
        <div className="env-strip" onClick={() => navigate('environment')}>
          <div className="env-strip-top">
            <span className="env-strip-title">Live Sensors — DK 6</span>
            <span className="env-strip-arrow"><i className="fa fa-chevron-right"></i></span>
          </div>
          <div className="env-metrics">
            <div className="env-metric"><div className="val">26.4</div><div className="unit">°C</div><div className="lbl">Temp</div></div>
            <div className="env-metric"><div className="val">1240</div><div className="unit">ppm</div><div className="lbl">CO₂</div></div>
            <div className="env-metric"><div className="val">420</div><div className="unit">lux</div><div className="lbl">Light</div></div>
            <div className="env-metric"><div className="val">23</div><div className="unit">pax</div><div className="lbl">Occupancy</div></div>
          </div>
        </div>
      </div>
      <div style={{ height: 20 }}></div>
    </div>
  )
}
