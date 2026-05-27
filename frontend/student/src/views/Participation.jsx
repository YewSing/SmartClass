import { useState } from 'react'
import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import { PART_SUMMARY, PARTICIPATION_GROUPS } from '../data/mockData'

export default function Participation() {
  const { navigate, openModal } = useStudent()
  const [collapsed, setCollapsed] = useState({})
  const [activeFilter, setActiveFilter] = useState('All Classes')

  const toggleGroup = (id) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))

  const handleItemClick = (item) => {
    if (item.type === 'poll') {
      openModal('poll-detail', { key: item.modalKey })
    } else {
      openModal('quiz-detail', { key: item.modalKey })
    }
  }

  const filters = ['All Classes', 'WIA2005', 'WIA2004', 'WIA2003']

  return (
    <>
      <StatusBar time="10:11" />
      <div style={{ padding: '12px 16px 10px', background: 'var(--card)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)' }}>My Participation</div>
        <div style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 2 }}>Quiz &amp; poll history · All classes</div>
      </div>

      <div className="part-summary">
        <div className="part-chip correct-c"><div className="n">{PART_SUMMARY.correct}</div><div className="l">Correct</div></div>
        <div className="part-chip wrong-c"><div className="n">{PART_SUMMARY.wrong}</div><div className="l">Wrong</div></div>
        <div className="part-chip unans-c"><div className="n">{PART_SUMMARY.skipped}</div><div className="l">Skipped</div></div>
        <div className="part-chip rate-c"><div className="n">{PART_SUMMARY.score}</div><div className="l">Score</div></div>
      </div>

      <div className="class-filter-row" style={{ flexShrink: 0 }}>
        {filters.map(f => (
          <button key={f} className={`filter-pill${activeFilter === f ? ' active' : ''}`} onClick={() => setActiveFilter(f)}>
            {f}
          </button>
        ))}
      </div>

      <div className="scroll-body">
        {(activeFilter === 'All Classes' ? PARTICIPATION_GROUPS : PARTICIPATION_GROUPS.filter(g => g.label.includes(activeFilter))).map(group => (
          <div key={group.id}>
            <div
              className={`session-group-header-row${collapsed[group.id] ? ' collapsed' : ''}`}
              style={{ marginTop: group.id !== 'today' ? 4 : 0 }}
              onClick={() => toggleGroup(group.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div className="session-group-label">{group.label}</div>
                <i className="fa fa-chevron-down toggle-arrow" style={{ fontSize: 9, color: 'var(--text-sub)' }}></i>
              </div>
              <button
                className="session-perf-btn"
                onClick={(e) => { e.stopPropagation(); navigate('part-session-perf', { perfKey: group.perfKey }) }}
              >
                <i className="fa fa-chart-bar"></i> Summary
              </button>
            </div>

            {!collapsed[group.id] && group.items.map(item => (
              <div key={item.id} className="quiz-response-row" onClick={() => handleItemClick(item)}>
                <div className={`qr-type-chip ${item.type}`}>
                  <i className={`fa ${item.type === 'quiz' ? 'fa-question-circle' : 'fa-chart-bar'}`} style={{ fontSize: 9 }}></i>
                  {item.typeLabel}
                </div>
                <div className="qr-question">{item.question}</div>
                <div className="qr-answer-row" style={{ marginBottom: item.type === 'poll' ? 6 : 0 }}>
                  {item.myAnswer ? (
                    <span className={`qr-answer-pill my-ans ${item.myAnswerClass}`}>{item.myAnswer}</span>
                  ) : (
                    <span className="qr-answer-pill" style={{ background: 'var(--gray-100)', color: 'var(--gray-500)', border: '1px solid var(--border)' }}>— No answer</span>
                  )}
                  {item.correctAnswer && item.type === 'quiz' && (
                    <>
                      <i className="fa fa-arrow-right qr-arrow"></i>
                      <span className="qr-answer-pill correct-ans">{item.correctAnswer}</span>
                    </>
                  )}
                  {item.resultIcon && (
                    <i className={`fa ${item.resultIcon} qr-result-icon`} style={{ color: item.resultColor, marginLeft: 'auto', marginRight: 6 }}></i>
                  )}
                  <i className="fa fa-chevron-right" style={{ color: 'var(--gray-300)', fontSize: 11 }}></i>
                </div>
                {item.type === 'poll' && item.pollBars && (
                  <div className="poll-dist-bar">
                    {item.pollBars.map(bar => (
                      <div key={bar.opt} className="poll-bar-row">
                        <span className="poll-bar-opt">{bar.opt}</span>
                        <div className="poll-bar-track">
                          <div className={`poll-bar-fill${bar.isMyChoice ? ' my-choice' : ''}`} style={{ width: `${bar.pct}%` }}></div>
                        </div>
                        <span className="poll-bar-pct" style={bar.isMyChoice ? { color: 'var(--student-accent)', fontWeight: 700 } : {}}>{bar.pct}%</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="qr-meta" style={item.metaColor ? { color: item.metaColor } : {}}>
                  <i className="fa fa-clock" style={{ fontSize: 10 }}></i> {item.meta}
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
