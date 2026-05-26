import { useState } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { ANALYTICS_ATT_BARS, ANALYTICS_ATT_LABELS, ANALYTICS_PAR_BARS, ANALYTICS_PAR_LABELS, AT_RISK } from '../data/mockData'

const MAX_H = 110

export default function Analytics() {
  const { navigate, openModal } = useLecturer()
  const [tab, setTab] = useState('att')

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title="Analytics & Reports"
        sub="WIA2005 — Sem 2 2024/25"
        right={<button className="btn btn-primary btn-sm" onClick={() => openModal('export')}><i className="fa fa-download"></i> Export</button>}
      />
      <div className="tabs-row" style={{ flexShrink: 0 }}>
        {[['att', 'Attendance'], ['par', 'Participation'], ['env', 'Environment']].map(([id, label]) => (
          <div key={id} className={`tab${tab === id ? ' active' : ''}`} onClick={() => setTab(id)}>{label}</div>
        ))}
      </div>
      <div className="filter-row">
        <select style={{ flex: 1.4, padding: '7px 10px', fontSize: 12 }}><option>WIA2005 — Soft. Eng.</option><option>WIA2004 — Data Mining</option></select>
        <select style={{ flex: 1, padding: '7px 10px', fontSize: 12 }}><option>This month</option><option>Last 30 days</option><option>Sem 2 2024/25</option></select>
      </div>
      <div className="scroll-body">
        {tab === 'att' && (
          <>
            <div className="stat-row-grid" style={{ marginTop: 12 }}>
              <div className="stat-chip"><div className="n">88.4%</div><div className="l">Avg attendance rate</div></div>
              <div className="stat-chip"><div className="n">12</div><div className="l">Sessions held</div></div>
            </div>
            <div className="stat-row-grid">
              <div className="stat-chip"><div className="n" style={{ color: 'var(--red)' }}>3</div><div className="l">Students at-risk (&lt;80%)</div></div>
              <div className="stat-chip"><div className="n">26</div><div className="l">Enrolled</div></div>
            </div>
            <div className="chart-card">
              <h3>Attendance per Session (students present)</h3>
              <div className="mini-chart">
                {ANALYTICS_ATT_BARS.map((h, i) => (
                  <div key={i} className="bar-col">
                    <div className="bar-vis blue" style={{ height: h }}></div>
                    <div className="lbl-x">{ANALYTICS_ATT_LABELS[i]}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="chart-card">
              <h3>Students at risk (&lt;80% attendance)</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {AT_RISK.map(r => (
                  <div key={r.name} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ fontSize: 13, color: 'var(--text)', flex: 1 }}>{r.name}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: r.color }}>{r.pct}</div>
                  </div>
                ))}
              </div>
            </div>
          </>
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
