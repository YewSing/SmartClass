import { useState } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'

const DEFAULT_OPTIONS = ['Class Diagram', 'Use Case Diagram', 'Sequence Diagram', 'Activity Diagram']

export default function CreateQuiz() {
  const { navigate } = useLecturer()
  const [question, setQuestion] = useState('Which UML diagram best represents the sequence of operations in a use case?')
  const [options, setOptions] = useState(DEFAULT_OPTIONS)
  const [correct, setCorrect] = useState(2)
  const [timer, setTimer] = useState('30s')

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar title="Create Quiz / Poll" sub="Leave answers unmarked for poll mode" onBack={() => navigate('quiz-list')} />
      <div className="scroll-body" style={{ padding: 16 }}>
        <div className="form-group">
          <label className="form-label">Question</label>
          <textarea rows={3} placeholder="Enter your question…" value={question} onChange={e => setQuestion(e.target.value)} />
        </div>
        <div className="form-label" style={{ marginBottom: 10 }}>
          Answer Options <span style={{ fontSize: 11, color: 'var(--text-hint)', fontWeight: 400 }}>· tap ✓ to mark correct answer</span>
        </div>
        {options.map((opt, i) => (
          <div key={i} className="answer-option">
            <div className="option-label">{String.fromCharCode(65 + i)}</div>
            <input type="text" value={opt} style={{ flex: 1 }} onChange={e => setOptions(prev => prev.map((o, j) => j === i ? e.target.value : o))} />
            <div className={`correct-toggle${correct === i ? ' active' : ''}`} onClick={() => setCorrect(i)}>
              <i className="fa fa-check"></i>
            </div>
          </div>
        ))}
        <div className="form-group" style={{ marginTop: 16 }}>
          <label className="form-label">Time Limit</label>
          <div className="time-pill-group">
            {['15s', '30s', '60s'].map(t => (
              <button key={t} className={`time-pill${timer === t ? ' active' : ''}`} onClick={() => setTimer(t)}>{t}</button>
            ))}
          </div>
        </div>
        <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '6px 0 16px' }} />
        <div className="btn-row">
          <button className="btn btn-outline btn-full" onClick={() => navigate('quiz-list')}><i className="fa fa-save"></i> Save Draft</button>
          <button className="btn btn-primary btn-full" onClick={() => navigate('quiz-list')}><i className="fa fa-paper-plane"></i> Push to Desks</button>
        </div>
        <div style={{ height: 24 }}></div>
      </div>
    </>
  )
}
