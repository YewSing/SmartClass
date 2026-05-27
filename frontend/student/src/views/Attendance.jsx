import { useState } from 'react'
import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import { ATT_SUMMARY, ATTENDANCE_GROUPS } from '../data/mockData'

const STATUS_BADGE = {
  present: <span className="badge green dot">Present</span>,
  late:    <span className="badge orange dot">Late</span>,
  absent:  <span className="badge red dot">Absent</span>,
  unid:    <span className="badge orange dot">Unidentified</span>,
}

export default function Attendance() {
  const { navigate, openModal } = useStudent()
  const [collapsed, setCollapsed] = useState({})
  const [activeFilter, setActiveFilter] = useState('All Classes')

  const toggleGroup = (id) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))

  const handleRowClick = (session) => {
    navigate('att-session-detail', { session: session.detail, variant: session.variant })
  }

  const handleReport = (e, session) => {
    e.stopPropagation()
    openModal('report-issue', { sessionLabel: `Lec 8 — Requirements Eng. · 29 Apr 2025` })
  }

  const filters = ['All Classes', 'WIA2005', 'WIA2004', 'WIA2003', 'WIX2001']

  return (
    <>
      <StatusBar time="10:09" />
      <div style={{ padding: '12px 16px 10px', background: 'var(--card)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)' }}>My Attendance</div>
        <div style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 2 }}>All enrolled classes · Sem 2 2024/25</div>
      </div>

      <div className="attend-summary-bar">
        <div className="att-sum-chip present"><div className="n">{ATT_SUMMARY.present}</div><div className="l">Present</div></div>
        <div className="att-sum-chip absent"><div className="n">{ATT_SUMMARY.absent}</div><div className="l">Absent</div></div>
        <div className="att-sum-chip late"><div className="n">{ATT_SUMMARY.late}</div><div className="l">Late</div></div>
        <div className="att-sum-chip rate"><div className="n">{ATT_SUMMARY.rate}</div><div className="l">Rate</div></div>
      </div>

      <div className="class-filter-row">
        {filters.map(f => (
          <button key={f} className={`filter-pill${activeFilter === f ? ' active' : ''}`} onClick={() => setActiveFilter(f)}>
            {f}
          </button>
        ))}
      </div>

      <div className="scroll-body">
        {(activeFilter === 'All Classes' ? ATTENDANCE_GROUPS : ATTENDANCE_GROUPS.filter(g => g.label.includes(activeFilter))).map(group => (
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
                  {session.canReport && (
                    <div style={{ marginTop: 5 }}>
                      <button className="report-btn" onClick={(e) => handleReport(e, session)}>
                        <i className="fa fa-flag" style={{ fontSize: 10 }}></i> Report issue
                      </button>
                    </div>
                  )}
                </div>
                <div className="session-att-right">
                  {STATUS_BADGE[session.status]}
                  {session.isLive && (
                    <div className="live-chip" style={{ padding: '2px 7px', fontSize: 10 }}>
                      <div className="live-dot" style={{ width: 5, height: 5 }}></div>Live
                    </div>
                  )}
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
