import { useState, useEffect } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { ANALYTICS_PAR_BARS, ANALYTICS_PAR_LABELS } from '../data/mockData'

const MAX_H = 110

function rateColor(rate) {
  return rate < 70 ? 'var(--red)' : 'var(--orange)'
}

export default function Analytics() {
  const { state, openModal, loadAnalytics, loadAllClasses } = useLecturer()
  const { allClasses, analytics, analyticsLoading } = state
  const [tab, setTab] = useState('att')
  const [selectedOccId, setSelectedOccId] = useState(null)

  useEffect(() => {
    if (!allClasses.length) loadAllClasses()
  }, [])

  useEffect(() => {
    if (allClasses.length && !selectedOccId) {
      setSelectedOccId(allClasses[0].id)
    }
  }, [allClasses])

  useEffect(() => {
    if (selectedOccId) loadAnalytics(selectedOccId)
  }, [selectedOccId])

  const selectedClass = allClasses.find(c => c.id === selectedOccId)

  const sessions = analytics?.sessions ?? []
  const enrolled = analytics?.enrolled_count || 1
  const barHeights = sessions.map(s => Math.round((s.present_count / enrolled) * MAX_H))
  const barLabels = sessions.map(s => s.label.replace('Week ', 'W'))

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title="Analytics & Reports"
        sub={selectedClass ? `${selectedClass.code} — ${selectedClass.name}` : ''}
        right={<button className="btn btn-primary btn-sm" onClick={() => openModal('export')}><i className="fa fa-download"></i> Export</button>}
      />
      <div className="tabs-row" style={{ flexShrink: 0 }}>
        {[['att', 'Attendance'], ['par', 'Participation'], ['env', 'Environment']].map(([id, label]) => (
          <div key={id} className={`tab${tab === id ? ' active' : ''}`} onClick={() => setTab(id)}>{label}</div>
        ))}
      </div>
      <div className="filter-row">
        <select
          style={{ flex: 1.4, padding: '7px 10px', fontSize: 12 }}
          value={selectedOccId ?? ''}
          onChange={e => setSelectedOccId(Number(e.target.value))}
        >
          {allClasses.map(c => (
            <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
          ))}
        </select>
        <select style={{ flex: 1, padding: '7px 10px', fontSize: 12 }}>
          <option>This semester</option>
        </select>
      </div>
      <div className="scroll-body">
        {tab === 'att' && (
          analyticsLoading ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-hint)', fontSize: 13 }}>Loading…</div>
          ) : !analytics ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-hint)', fontSize: 13 }}>No data available</div>
          ) : (
            <>
              <div className="stat-row-grid" style={{ marginTop: 12 }}>
                <div className="stat-chip"><div className="n">{analytics.avg_attendance_rate}%</div><div className="l">Avg attendance rate</div></div>
                <div className="stat-chip"><div className="n">{analytics.sessions_held}</div><div className="l">Sessions held</div></div>
              </div>
              <div className="stat-row-grid">
                <div className="stat-chip"><div className="n" style={{ color: 'var(--red)' }}>{analytics.at_risk_students.length}</div><div className="l">Students at-risk (&lt;80%)</div></div>
                <div className="stat-chip"><div className="n">{analytics.enrolled_count}</div><div className="l">Enrolled</div></div>
              </div>
              {sessions.length > 0 ? (
                <div className="chart-card">
                  <h3>Attendance per Session (students present)</h3>
                  <div className="mini-chart">
                    {barHeights.map((h, i) => (
                      <div key={i} className="bar-col">
                        <div className="bar-vis blue" style={{ height: h }}></div>
                        <div className="lbl-x">{barLabels[i]}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="chart-card" style={{ color: 'var(--text-hint)', fontSize: 13 }}>
                  No closed sessions yet.
                </div>
              )}
              <div className="chart-card">
                <h3>Students at risk (&lt;80% attendance)</h3>
                {analytics.at_risk_students.length === 0 ? (
                  <div style={{ fontSize: 13, color: 'var(--text-hint)' }}>No at-risk students.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {analytics.at_risk_students.map(r => (
                      <div key={r.student_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ fontSize: 13, color: 'var(--text)', flex: 1 }}>{r.name}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-hint)' }}>{r.present}/{r.total}</div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: rateColor(r.rate) }}>{r.rate}%</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )
        )}
        {tab === 'par' && (
          <>
            <div className="stat-row-grid" style={{ marginTop: 12 }}>
              <div className="stat-chip"><div className="n">79%</div><div className="l">Avg response rate</div></div>
              <div className="stat-chip"><div className="n">68%</div><div className="l">Avg quiz score</div></div>
            </div>
            <div className="stat-row-grid">
              <div className="stat-chip"><div className="n">32</div><div className="l">Quizzes &amp; polls run</div></div>
              <div className="stat-chip"><div className="n" style={{ color: 'var(--green)' }}>+8%</div><div className="l">Score trend vs last sem</div></div>
            </div>
            <div className="chart-card">
              <h3>Response rate per session</h3>
              <div className="mini-chart">
                {ANALYTICS_PAR_BARS.map((h, i) => (
                  <div key={i} className="bar-col">
                    <div className="bar-vis green" style={{ height: h }}></div>
                    <div className="lbl-x">{ANALYTICS_PAR_LABELS[i]}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="chart-card">
              <h3>Average score trend</h3>
              <svg viewBox="0 0 300 90" style={{ width: '100%', height: 90 }}>
                <polyline points="10,75 60,60 110,50 160,55 210,38 270,30 290,34" fill="none" stroke="#12A564" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                {[[10,75],[60,60],[110,50],[160,55],[210,38],[270,30],[290,34]].map(([x,y],i) => <circle key={i} cx={x} cy={y} r="3.5" fill="#12A564" />)}
              </svg>
              <div style={{ fontSize: 11, color: 'var(--text-hint)', textAlign: 'center', marginTop: 2 }}>Average % correct over weeks (↑ trend)</div>
            </div>
          </>
        )}
        {tab === 'env' && (
          <>
            <div className="stat-row-grid" style={{ marginTop: 12 }}>
              <div className="stat-chip"><div className="n">25.8°C</div><div className="l">Avg temperature</div></div>
              <div className="stat-chip"><div className="n">1180</div><div className="l">Avg CO₂ (ppm)</div></div>
            </div>
            <div className="chart-card">
              <h3>Temperature history (°C)</h3>
              <svg viewBox="0 0 300 90" style={{ width: '100%', height: 90 }}>
                <polyline points="10,55 60,50 110,58 160,44 210,52 270,46 290,42" fill="none" stroke="#1B6EF3" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                {[[10,55],[60,50],[110,58],[160,44],[210,52],[270,46],[290,42]].map(([x,y],i) => <circle key={i} cx={x} cy={y} r="3.5" fill="#1B6EF3" />)}
              </svg>
            </div>
            <div className="chart-card">
              <h3>CO₂ history (ppm)</h3>
              <svg viewBox="0 0 300 90" style={{ width: '100%', height: 90 }}>
                <line x1="10" y1="35" x2="290" y2="35" stroke="#f5c5c5" strokeWidth="1" strokeDasharray="4,3" />
                <text x="210" y="31" fontSize="9" fill="#E03A3A">1500 ppm limit</text>
                <polyline points="10,72 60,65 110,52 160,68 210,44 270,58 290,50" fill="none" stroke="#E03A3A" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                {[[10,72],[60,65],[110,52],[160,68],[210,44],[270,58],[290,50]].map(([x,y],i) => <circle key={i} cx={x} cy={y} r="3.5" fill="#E03A3A" />)}
              </svg>
            </div>
          </>
        )}
        <div style={{ height: 20 }}></div>
      </div>
    </>
  )
}
