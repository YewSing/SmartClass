import { useEffect, useState } from 'react'
import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'

const STATUS_BADGE = {
  present: <span className="badge green dot">Present</span>,
  late:    <span className="badge orange dot">Late</span>,
  absent:  <span className="badge red dot">Absent</span>,
  unid:    <span className="badge orange dot">Unidentified</span>,
}

export default function Attendance() {
  const { state, navigate, openModal, loadAttendanceSummary, loadAttendanceGroups } = useStudent()
  const { attendanceSummary, attendanceGroups } = state
  const [collapsed, setCollapsed] = useState({})
  const [activeFilter, setActiveFilter] = useState('All Classes')

  useEffect(() => {
    loadAttendanceSummary()
    loadAttendanceGroups()
  }, [loadAttendanceSummary, loadAttendanceGroups])

  const toggleGroup = (id) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))

  const handleRowClick = (session) => {
    navigate('att-session-detail', { session: session.detail, variant: session.variant })
  }

  const summary = attendanceSummary ?? { present: 0, absent: 0, late: 0, rate: '—' }
  const filters = ['All Classes', ...attendanceGroups.map(g => g.id.toUpperCase())]
  const visibleGroups = activeFilter === 'All Classes'
    ? attendanceGroups
    : attendanceGroups.filter(g => g.label.toUpperCase().includes(activeFilter))

  return (
    <>
      <StatusBar time="10:09" />
      <div style={{ padding: '12px 16px 10px', background: 'var(--card)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)' }}>My Attendance</div>
        <div style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 2 }}>All enrolled classes</div>
      </div>

      <div className="attend-summary-bar">
        <div className="att-sum-chip present"><div className="n">{summary.present}</div><div className="l">Present</div></div>
        <div className="att-sum-chip absent"><div className="n">{summary.absent}</div><div className="l">Absent</div></div>
        <div className="att-sum-chip late"><div className="n">{summary.late}</div><div className="l">Late</div></div>
        <div className="att-sum-chip rate"><div className="n">{summary.rate}</div><div className="l">Rate</div></div>
      </div>

      <div className="class-filter-row">
        {filters.map(f => (
          <button key={f} className={`filter-pill${activeFilter === f ? ' active' : ''}`} onClick={() => setActiveFilter(f)}>
            {f}
          </button>
        ))}
      </div>

      <div className="scroll-body">
        {visibleGroups.length === 0 ? (
          <div style={{ padding: '40px 24px', textAlign: 'center', color: 'var(--text-sub)', fontSize: 14 }}>
            No attendance records yet.
          </div>
        ) : visibleGroups.map(group => (
          <div key={group.id}>
            <div
              className={`session-group-header-row${collapsed[group.id] ? ' collapsed' : ''}`}
              onClick={() => toggleGroup(group.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div className="session-group-label">{group.label}</div>
                <i className="fa fa-chevron-down toggle-arrow" style={{ fontSize: 9, color: 'var(--text-sub)' }}></i>
              </div>
            </div>

            {!collapsed[group.id] && group.sessions.map(session => (
              <div key={session.id} className="session-att-row" onClick={() => handleRowClick(session)}>
                <div className="session-date-block" style={{ background: session.dateBg }}>
                  <div className="d" style={{ color: session.dateColor }}>{session.day}</div>
                  <div className="m" style={{ color: session.dateColor }}>{session.month}</div>
                </div>
                <div className="session-att-info">
                  <div className="title">{session.title}</div>
                  <div className="sub">{session.sub}</div>
                </div>
                <div className="session-att-right">
                  {STATUS_BADGE[session.status]}
                </div>
              </div>
            ))}
          </div>
        ))}
        <div style={{ height: 16 }}></div>
      </div>
    </>
  )
}
