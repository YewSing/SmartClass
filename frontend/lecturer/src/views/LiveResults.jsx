import { useState, useEffect } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { QUIZZES } from '../data/mockData'

export default function LiveResults() {
  const { navigate } = useLecturer()
  const [secs, setSecs] = useState(14)
  const quiz = QUIZZES[0]

  useEffect(() => {
    const t = setInterval(() => setSecs(s => s > 0 ? s - 1 : 30), 1000)
    return () => clearInterval(t)
  }, [])

  const mm = String(Math.floor(secs / 60)).padStart(2, '0')
  const ss = String(secs % 60).padStart(2, '0')
  const BARS = [
    { opt: 'A', pct: 20, count: 1, correct: false },
    { opt: 'B', pct: 60, count: 3, correct: true  },
    { opt: 'C', pct: 20, count: 1, correct: false },
    { opt: 'D', pct: 0,  count: 0, correct: false },
  ]

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title="Live Results"
        onBack={() => navigate('quiz-list')}
        right={<span className="badge blue dot" style={{ marginLeft: 'auto' }}>Active</span>}
      />
      <div className="scroll-body">
        <div className="card" style={{ margin: '12px 16px' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', lineHeight: 1.5 }}>{quiz.question}</div>
        </div>
        <div className="timer-block">
          <div className="timer-num">{mm}:{ss}</div>
          <div className="timer-label">Time remaining</div>
        </div>
        <div className="response-summary">
          <div className="resp-stat"><div className="n">4/5</div><div className="l">Answered</div></div>
          <div className="resp-stat"><div className="n" style={{ color: 'var(--green)' }}>3</div><div className="l">Correct</div></div>
          <div className="resp-stat"><div className="n" style={{ color: 'var(--red)' }}>1</div><div className="l">Incorrect</div></div>
          <div className="resp-stat"><div className="n" style={{ color: 'var(--gray-400)' }}>1</div><div className="l">Unanswered</div></div>
        </div>
        <div className="chart-bars">
          <div className="card-label" style={{ marginBottom: 10 }}>Answer Distribution</div>
          {BARS.map(b => (
            <div key={b.opt} className="bar-row">
              <div className={`bar-opt ${b.correct ? 'correct' : 'wrong'}`}>{b.opt}</div>
              <div className="bar-track">
                <div className={`bar-fill ${b.correct ? 'correct-f' : 'wrong-f'}`} style={{ width: `${b.pct}%` }}>
                  {b.pct > 0 && <span className={b.correct ? 'bar-pct-c' : 'bar-pct-w'}>{b.pct}%</span>}
                </div>
              </div>
              <span className="bar-count">{b.count}</span>
            </div>
          ))}
        </div>
        <div style={{ padding: 16 }}>
          <button className="btn btn-danger btn-full" onClick={() => navigate('quiz-list')}>
            <i className="fa fa-stop"></i> Close Early
          </button>
        </div>
      </div>
    </>
  )
}
