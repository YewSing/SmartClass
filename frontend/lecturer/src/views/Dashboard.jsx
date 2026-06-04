import { useEffect, useMemo, useState } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import { QUIZZES } from '../data/mockData'

const DAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function nowHHMM() {
  const n = new Date()
  return `${String(n.getHours()).padStart(2, '0')}:${String(n.getMinutes()).padStart(2, '0')}`
}

function computeNextClass(allClasses) {
  if (!allClasses.length) return null
  const todayIdx = (new Date().getDay() + 6) % 7  // 0=Mon … 6=Sun
  const hhmm = nowHHMM()

  return allClasses
    .map(c => {
      const dayIdx = DAY_ORDER.indexOf(c.day_of_week)
      let daysAway = (dayIdx - todayIdx + 7) % 7
      if (daysAway === 0 && c.end_time < hhmm) daysAway = 7   // already finished today
      if (daysAway === 0 && c.start_time <= hhmm) return null  // currently ongoing
      return { ...c, daysAway }
    })
    .filter(Boolean)
    .sort((a, b) => a.daysAway - b.daysAway || a.start_time.localeCompare(b.start_time))[0] ?? null
}

function nextLabel(c) {
  if (!c) return ''
  const when = c.daysAway === 0 ? 'Today' : c.daysAway === 1 ? 'Tomorrow' : c.day_of_week
  return `${when} · ${c.start_time}–${c.end_time}`
}

export default function Dashboard() {
  const { state, navigate, openModal, loadClasses, loadAllClasses, loadSessions, doOpenSession, doCloseSession } = useLecturer()
  const { sessions, classes, allClasses, lecturer } = state
  const [toggling, setToggling] = useState(false)

  useEffect(() => {
    loadClasses()
    loadSessions()
    loadAllClasses()
  }, [loadClasses, loadSessions, loadAllClasses])

  const activeSession = sessions.find(s => s.open)
  const sessionOpen   = Boolean(activeSession)
  const firstClass    = classes[0]           // only set when a class is currently ongoing
  const nextClass     = useMemo(() => computeNextClass(allClasses), [allClasses])

  const handleToggleSession = async () => {
    if (toggling) return
    setToggling(true)
    try {
      if (sessionOpen) {
        await doCloseSession(activeSession.id)
      } else if (firstClass) {
        await doOpenSession(firstClass.id)
      }
    } catch { /* toast shown in context */ } finally {
      setToggling(false)
    }
  }

  const badgeClass = sessionOpen ? 'badge green dot' : firstClass ? 'badge yellow dot' : 'badge gray dot'
  const badgeText  = sessionOpen ? 'Session Open'    : firstClass ? 'Class Ongoing'    : 'No Class Now'

  const headerTitle = firstClass
    ? `${firstClass.code} — ${firstClass.name}`
    : nextClass
      ? `${nextClass.code} — ${nextClass.name}`
      : 'No classes this week'

  const headerMeta = firstClass
    ? `${firstClass.day_of_week} ${firstClass.start_time}–${firstClass.end_time}${firstClass.room ? ` · ${firstClass.room}` : ''}`
    : nextClass
      ? `Next: ${nextLabel(nextClass)}`
      : ''

  return (
    <div className="scroll-body">
      <StatusBar time="10:14" />

      <div className="app-header">
        <div className="app-brand">
          <div className="logo-icon"><i className="fa fa-graduation-cap"></i></div>
          <span className="brand-name">SmartClass</span>
        </div>
        <div className="profile-btn" onClick={() => navigate('profile')}>
          {lecturer?.initials ?? 'ME'}
        </div>
      </div>

      <div className="dash-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 6 }}>
          <div>
            <div className="class-name">{headerTitle}</div>
            <div className="class-meta">{headerMeta}</div>
          </div>
          <span className={badgeClass}>{badgeText}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
          {sessionOpen
            ? <div style={{ fontSize: 12, color: 'var(--text-sub)' }}><i className="fa fa-clock" style={{ fontSize: 11 }}></i> Opened {activeSession.time}</div>
            : <div style={{ fontSize: 12, color: 'var(--text-sub)' }}>{firstClass ? 'Ready to open' : 'No active session'}</div>}
          <button
            className={`session-toggle-btn ${sessionOpen ? 'can-close' : 'can-open'}`}
            onClick={handleToggleSession}
            disabled={toggling || (!sessionOpen && !firstClass)}
            style={(!sessionOpen && !firstClass) ? { opacity: 0.45, cursor: 'not-allowed' } : undefined}
          >
            <i className={`fa ${sessionOpen ? 'fa-stop-circle' : 'fa-play-circle'}`}></i>
            {toggling ? ' …' : sessionOpen ? ' Close Session' : ' Open Session'}
          </button>
        </div>
      </div>

      {sessionOpen ? (
        <>
          <div className="section-header"><span className="section-title">Attendance</span></div>
          <div className="card tappable-card" onClick={() => navigate('attendance-sessions')} style={{ marginBottom: 10 }}>
            <div className="attend-stats">
              <div className="attend-stat present"><div className="num">{activeSession.present}</div><div className="lbl">Present</div></div>
              <div className="attend-stat absent"><div className="num">{activeSession.absent}</div><div className="lbl">Absent</div></div>
              <div className="attend-stat unid"><div className="num">{activeSession.unid}</div><div className="lbl">Unidentified</div></div>
            </div>
            <div className="attend-card-footer"><i className="fa fa-chevron-right" style={{ fontSize: 10 }}></i> Tap to view full attendance</div>
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
      ) : firstClass ? (
        /* ── Class is ongoing but no session opened yet ── */
        <div className="no-session-state">
          <div className="no-session-icon" style={{ color: 'var(--green)' }}><i className="fa fa-chalkboard-teacher"></i></div>
          <div className="no-session-title">Class is in Progress</div>
          <div className="no-session-sub">
            {firstClass.code} is ongoing. Open a session to start attendance tracking.
          </div>
          <button className="btn btn-green btn-full" onClick={handleToggleSession} disabled={toggling}>
            <i className="fa fa-play-circle"></i> {toggling ? 'Opening…' : 'Open Session'}
          </button>
        </div>
      ) : (
        /* ── No class scheduled right now ── */
        <div className="no-session-state">
          <div className="no-session-icon"><i className="fa fa-hourglass-end"></i></div>
          <div className="no-session-title">No Class Right Now</div>
          {nextClass ? (
            <div style={{
              background: 'var(--gray-50)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '12px 14px',
              marginBottom: 16,
              textAlign: 'left',
              width: '100%',
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-hint)', marginBottom: 4 }}>
                Next Class
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>
                {nextClass.code} — {nextClass.name}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-sub)', display: 'flex', flexWrap: 'wrap', gap: '4px 12px', alignItems: 'center' }}>
                <span><i className="fa fa-calendar" style={{ fontSize: 11 }}></i> {nextLabel(nextClass)}</span>
                {nextClass.room && <span><i className="fa fa-map-marker-alt" style={{ fontSize: 11 }}></i> {nextClass.room}</span>}
              </div>
            </div>
          ) : (
            <div className="no-session-sub">No upcoming classes scheduled this week.</div>
          )}
          <button
            className="btn btn-green btn-full"
            disabled
            style={{ opacity: 0.45, cursor: 'not-allowed' }}
          >
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
            <div className="env-metric"><div className="val">—</div><div className="unit">pax</div><div className="lbl">Occupancy</div></div>
          </div>
        </div>
      </div>
      <div style={{ height: 20 }}></div>
    </div>
  )
}
