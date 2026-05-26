import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { SESSION_PERFS } from '../data/mockData'

export default function PartSessionPerf() {
  const { state, goBack, openModal } = useStudent()
  const { navData } = state
  const perfKey = navData?.perfKey ?? 'today'
  const perf = SESSION_PERFS[perfKey] ?? SESSION_PERFS.today

  const handleQuestionClick = (q) => {
    if (q.type === 'poll') {
      openModal('poll-detail', { key: q.modalKey })
    } else {
      openModal('quiz-detail', { key: q.modalKey })
    }
  }

  return (
    <>
      <StatusBar time="10:11" />
      <Topbar title="Session Summary" onBack={goBack} />
      <div className="scroll-body">
        <div className="sess-perf-hero" style={perf.heroStyle ?? {}}>
          <div className="sess-perf-class">{perf.classLabel}</div>
          <div className="sess-perf-title">{perf.title}</div>
          <div className="sess-perf-date"><i className="fa fa-calendar" style={{ fontSize: 10 }}></i> {perf.date}</div>
          <div className="sess-perf-stats">
            {[['correct','Correct'],['wrong','Wrong'],['skipped','Skipped'],['score','Score']].map(([k,l]) => (
              <div key={k} className="sess-perf-chip"><div className="n">{perf.stats[k]}</div><div className="l">{l}</div></div>
            ))}
          </div>
        </div>

        <div className="perf-score-card">
          <div className="perf-score-title">Your score this session</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
            <span style={{ fontSize: 26, fontWeight: 700, color: perf.scoreColor }}>{perf.scoreValue}</span>
            <span style={{ fontSize: 12, color: 'var(--text-sub)' }}>Class avg: {perf.classAvg}</span>
          </div>
          <div className="perf-score-bar-wrap">
            <div className="perf-score-bar-fill" style={{
              width: perf.scoreWidth,
              ...(perf.scoreFill ? { background: perf.scoreFill } : {}),
            }}></div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: 'var(--text-hint)' }}>
            <span>0%</span><span>Class avg {perf.classAvg}</span><span>100%</span>
          </div>
        </div>

        {perf.warning && (
          <div style={{ margin: '0 16px 12px', background: 'var(--yellow-lt)', border: '1px solid var(--yellow)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', display: 'flex', gap: 8 }}>
            <i className="fa fa-exclamation-triangle" style={{ color: 'var(--yellow)', marginTop: 1, flexShrink: 0 }}></i>
            <span style={{ fontSize: 12, color: 'var(--yellow-dk)', lineHeight: 1.5 }}>{perf.warning}</span>
          </div>
        )}

        <div className="section-header"><span className="section-title">Questions &amp; Responses</span></div>

        {perf.questions.map((q, i) => (
          <div key={i} className="perf-quiz-row" onClick={() => handleQuestionClick(q)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
              <div className={`qr-type-chip ${q.type}`} style={{ margin: 0 }}>
                <i className={`fa ${q.type === 'quiz' ? 'fa-question-circle' : 'fa-chart-bar'}`} style={{ fontSize: 9 }}></i>
                {q.typeLabel}
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-hint)' }}>{q.meta}</span>
            </div>
            <div className="perf-quiz-q">{q.question}</div>
            <div className="perf-result-row">
              <span className={`perf-answer-pill ${q.answerPill.cls === 'no-answer' ? '' : q.answerPill.cls}`}
                style={q.answerPill.cls === 'no-answer' ? { background: 'var(--gray-100)', color: 'var(--gray-500)', border: '1px solid var(--border)' } : {}}>
                {q.answerPill.label}
              </span>
              {q.correctRef && (
                <>
                  <i className="fa fa-arrow-right" style={{ fontSize: 10, color: 'var(--gray-300)', margin: '0 2px' }}></i>
                  <span className="perf-answer-pill correct-ref">{q.correctRef}</span>
                </>
              )}
              <div className="perf-time-badge" style={q.timeBadgeColor ? { color: q.timeBadgeColor } : {}}>
                {q.timeBadgeIcon && <i className={`fa ${q.timeBadgeIcon}`} style={{ fontSize: 10 }}></i>}
                {q.timeBadge}
              </div>
              <i className="fa fa-chevron-right" style={{ color: 'var(--gray-300)', fontSize: 11, marginLeft: 'auto' }}></i>
            </div>
          </div>
        ))}

        <div style={{ height: 24 }}></div>
      </div>
    </>
  )
}
