import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { BREAKDOWN_ROWS } from '../data/mockData'

export default function Breakdown() {
  const { navigate } = useLecturer()
  return (
    <>
      <StatusBar time="10:14" />
      <Topbar title="Response Breakdown" onBack={() => navigate('results-closed')} />
      <div className="scroll-body">
        <div className="question-banner">
          <div className="q">What does SOLID stand for in object-oriented design principles?</div>
          <div className="correct-ans">
            <i className="fa fa-check-circle" style={{ color: 'var(--green)', fontSize: 14, flexShrink: 0, marginTop: 1 }}></i>
            <span>Correct: D — Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion</span>
          </div>
        </div>
        <div className="breakdown-summary">
          <div className="bkdn-stat correct-s"><div className="n">18</div><div className="l">Correct</div></div>
          <div className="bkdn-stat wrong-s"><div className="n">4</div><div className="l">Incorrect</div></div>
          <div className="bkdn-stat unans-s"><div className="n">3</div><div className="l">Unanswered</div></div>
        </div>
        <div className="breakdown-table">
          <div style={{ padding: '10px 14px', background: 'var(--gray-50)', borderBottom: '1px solid var(--border)', display: 'flex', fontSize: 11, fontWeight: 700, color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '.05em' }}>
            <span style={{ flex: 1 }}>Student</span>
            <span style={{ width: 60, textAlign: 'center' }}>Answer</span>
            <span style={{ width: 30, textAlign: 'center' }}>Result</span>
          </div>
          {BREAKDOWN_ROWS.map((r, i) => (
            <div key={i} className="bkdn-row">
              <div className="name">{r.name}</div>
              <div className="answer">{r.answer}</div>
              <div className="result-icon">
                {r.correct === true  ? '✅' : r.correct === false ? '❌' : <span style={{ color: 'var(--gray-300)' }}>⬜</span>}
              </div>
            </div>
          ))}
        </div>
        <div style={{ height: 24 }}></div>
      </div>
    </>
  )
}
