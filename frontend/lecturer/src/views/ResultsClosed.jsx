import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { QUIZZES } from '../data/mockData'

export default function ResultsClosed() {
  const { navigate } = useLecturer()
  const quiz = QUIZZES[1]
  const BARS = [
    { opt: 'A', pct: 16, count: 4,  correct: false },
    { opt: 'B', pct: 8,  count: 2,  correct: false },
    { opt: 'C', pct: 8,  count: 2,  correct: false },
    { opt: 'D', pct: 72, count: 18, correct: true  },
  ]

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title="Quiz Results"
        onBack={() => navigate('quiz-list')}
        right={<span className="badge gray" style={{ marginLeft: 'auto' }}>Closed</span>}
      />
      <div className="scroll-body">
        <div className="card" style={{ margin: '12px 16px' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', lineHeight: 1.5 }}>{quiz.question}</div>
        </div>
        <div className="timer-block">
          <div className="timer-num ended">⏱ Time's Up</div>
          <div className="timer-label">Quiz ended · {quiz.timer} timer</div>
        </div>
        <div className="response-summary">
          <div className="resp-stat"><div className="n">22/25</div><div className="l">Answered</div></div>
          <div className="resp-stat"><div className="n" style={{ color: 'var(--green)' }}>{quiz.correct_count}</div><div className="l">Correct</div></div>
          <div className="resp-stat"><div className="n" style={{ color: 'var(--red)' }}>{quiz.wrong_count}</div><div className="l">Incorrect</div></div>
          <div className="resp-stat"><div className="n" style={{ color: 'var(--gray-400)' }}>{quiz.unanswered_count}</div><div className="l">Unanswered</div></div>
        </div>
        <div className="chart-bars">
          <div className="card-label" style={{ marginBottom: 10 }}>Final Distribution</div>
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
          <button className="btn btn-primary btn-full" onClick={() => navigate('breakdown')}>
            <i className="fa fa-list"></i> View Individual Breakdown
          </button>
        </div>
      </div>
    </>
  )
}
