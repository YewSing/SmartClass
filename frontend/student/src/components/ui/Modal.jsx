import { useState } from 'react'
import { useStudent } from '../../context/StudentContext'

function Sheet({ children }) {
  return (
    <div className="modal-sheet">
      <div className="modal-handle"></div>
      {children}
    </div>
  )
}

function ForgotPasswordModal({ onClose }) {
  return (
    <Sheet>
      <div className="modal-title">Reset Password</div>
      <div style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 14 }}>
        Enter your university email and we'll send a reset link.
      </div>
      <div className="form-group">
        <input type="email" placeholder="u2300xxxx@siswa.um.edu.my" />
      </div>
      <button className="btn btn-primary btn-full" onClick={onClose}>
        <i className="fa fa-paper-plane"></i> Send Reset Link
      </button>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
    </Sheet>
  )
}

function ReportIssueModal({ data, onClose, navigate }) {
  const [selected, setSelected] = useState('present')
  const reasons = [
    { id: 'present',    label: 'I was physically present in class' },
    { id: 'no-detect',  label: 'Face recognition did not detect me' },
    { id: 'obstruction', label: 'I had a seating obstruction (hat/glasses)' },
    { id: 'other',      label: 'Other' },
  ]
  return (
    <Sheet>
      <div className="modal-title">Report Attendance Issue</div>
      {data && (
        <div style={{
          background: 'var(--orange-lt)', border: '1px solid #F7C8A0',
          borderRadius: 'var(--radius-sm)', padding: '10px 14px', marginBottom: 14,
          fontSize: 13, color: 'var(--orange-dk)', fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <i className="fa fa-calendar-day"></i>
          {data.sessionLabel}
        </div>
      )}
      <div style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 12 }}>
        Your attendance was marked as <strong style={{ color: 'var(--orange-dk)' }}>Unidentified</strong>. Select the reason:
      </div>
      {reasons.map(r => (
        <div
          key={r.id}
          className={`report-reason-option${selected === r.id ? ' selected' : ''}`}
          onClick={() => setSelected(r.id)}
        >
          <div className="rr-radio"></div>
          <div className="rr-text">{r.label}</div>
        </div>
      ))}
      <div className="form-group" style={{ marginTop: 10 }}>
        <label className="form-label">Additional notes (optional)</label>
        <textarea rows={3} placeholder="Describe the situation…"></textarea>
      </div>
      <div className="btn-row">
        <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
        <button
          className="btn btn-full"
          style={{ background: 'var(--orange)', color: '#fff' }}
          onClick={() => { onClose(); navigate('att-report-status') }}
        >
          <i className="fa fa-flag"></i> Submit Report
        </button>
      </div>
    </Sheet>
  )
}

function QuizDetailModal({ data, onClose }) {
  if (!data) return null
  const isCorrect = data.result === 'correct'
  const isWrong   = data.result === 'wrong'
  const isExpired = data.result === 'expired'

  const headerBg    = isCorrect ? 'var(--green-lt)' : isWrong ? 'var(--red-lt)' : 'var(--orange-lt)'
  const headerIcon  = isCorrect ? 'fa-check' : isWrong ? 'fa-times' : 'fa-exclamation-triangle'
  const headerColor = isCorrect ? 'var(--green)' : isWrong ? 'var(--red)' : 'var(--orange)'
  const titleText   = isCorrect ? 'Correct Answer!' : isWrong ? 'Incorrect' : 'Time Expired'

  return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: headerBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <i className={`fa ${headerIcon}`} style={{ color: headerColor, fontSize: 16 }}></i>
        </div>
        <div>
          <div className="modal-title" style={{ margin: 0 }}>{titleText}</div>
          <div style={{ fontSize: 12, color: 'var(--text-sub)' }}>{data.context}</div>
        </div>
      </div>

      {isExpired && (
        <div style={{ background: 'var(--yellow-lt)', border: '1px solid var(--yellow)', color: 'var(--yellow-dk)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', marginBottom: 14, fontSize: 12, fontWeight: 600, lineHeight: 1.4, display: 'flex', alignItems: 'center', gap: 8 }}>
          <i className="fa fa-info-circle"></i> No response was recorded. Correct answer is shown below.
        </div>
      )}

      <div style={{ background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)', padding: '12px 14px', marginBottom: 14, fontSize: 13, fontWeight: 600, color: 'var(--text)', lineHeight: 1.5 }}>
        {data.question}
      </div>

      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>Answer Options</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          {data.options.map((opt, i) => {
            const letter = String.fromCharCode(65 + i)
            const isCorrectOpt = i === data.correctIndex
            const isMyOpt      = i === data.myIndex
            const wrongMyOpt   = isMyOpt && !isCorrectOpt

            let bg     = 'var(--gray-50)'
            let border = '1px solid var(--border)'
            let textColor = 'var(--text)'
            let labelColor = 'var(--text-sub)'
            let icon  = null

            if (isCorrectOpt) {
              bg = 'var(--green-lt)'; border = '1.5px solid var(--green)'; textColor = 'var(--green-dk)'; labelColor = 'var(--green-dk)'; icon = 'fa-check-circle'
            } else if (wrongMyOpt) {
              bg = 'var(--red-lt)'; border = '1.5px solid var(--red)'; textColor = 'var(--red-dk)'; labelColor = 'var(--red-dk)'; icon = 'fa-times-circle'
            }

            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 'var(--radius-sm)', background: bg, border }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: labelColor, width: 16 }}>{letter}</span>
                <span style={{ fontSize: 13, fontWeight: isCorrectOpt ? 700 : 400, color: textColor }}>{opt}</span>
                {icon && <i className={`fa ${icon}`} style={{ color: isCorrectOpt ? 'var(--green)' : 'var(--red)', marginLeft: 'auto' }}></i>}
              </div>
            )
          })}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        {data.stats.map((s, i) => (
          <div key={i} style={{ flex: 1, background: s.bg, borderRadius: 'var(--radius-sm)', padding: 10, textAlign: 'center', border: s.border }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: s.labelColor }}>{s.label}</div>
          </div>
        ))}
      </div>
      <button className="btn btn-outline btn-full" onClick={onClose}>Close</button>
    </Sheet>
  )
}

function PollDetailModal({ data, onClose }) {
  if (!data) return null
  return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--purple-lt)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <i className="fa fa-chart-bar" style={{ color: 'var(--purple)', fontSize: 16 }}></i>
        </div>
        <div>
          <div className="modal-title" style={{ margin: 0 }}>Poll Results</div>
          <div style={{ fontSize: 12, color: 'var(--text-sub)' }}>{data.context}</div>
        </div>
      </div>

      <div style={{ background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)', padding: '12px 14px', marginBottom: 14, fontSize: 13, fontWeight: 600, color: 'var(--text)', lineHeight: 1.5 }}>
        {data.question}
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>Class Distribution &amp; Your Choice</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {data.options.map((opt, i) => {
            const letter = String.fromCharCode(65 + i)
            const isSelected = opt.isMyChoice
            return (
              <div key={i} style={isSelected ? { background: 'var(--student-accent-lt)', padding: '8px 10px', borderRadius: 8, border: '1px dashed var(--student-accent)' } : {}}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                  <span style={{ color: isSelected ? 'var(--student-accent-dk)' : 'var(--text)', fontWeight: isSelected ? 700 : 600 }}>
                    {letter} — {opt.label}
                    {isSelected && <span className="badge blue" style={{ fontSize: 9, padding: '1px 6px', marginLeft: 6 }}>Your Choice</span>}
                  </span>
                  <span style={{ color: isSelected ? 'var(--student-accent-dk)' : 'var(--text-sub)', fontWeight: 700 }}>{opt.pct}%</span>
                </div>
                <div style={{ height: 8, background: isSelected ? 'var(--gray-200)' : 'var(--gray-100)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: `${opt.pct}%`, height: '100%', background: isSelected ? 'var(--student-accent)' : 'var(--student-accent-lt)', borderRadius: 4 }}></div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        {data.stats.map((s, i) => (
          <div key={i} style={{ flex: 1, background: s.bg, borderRadius: 'var(--radius-sm)', padding: 10, textAlign: 'center', border: s.border }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: s.labelColor }}>{s.label}</div>
          </div>
        ))}
      </div>
      <button className="btn btn-outline btn-full" onClick={onClose}>Close</button>
    </Sheet>
  )
}

function SignOutModal({ onClose, dispatch }) {
  return (
    <Sheet>
      <div className="modal-title">Sign Out</div>
      <div style={{ fontSize: 14, color: 'var(--text-sub)', marginBottom: 18, lineHeight: 1.5 }}>
        Are you sure you want to sign out?
      </div>
      <div className="btn-row">
        <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
        <button className="btn btn-red btn-full" onClick={() => dispatch({ type: 'LOGOUT' })}>
          <i className="fa fa-sign-out-alt"></i> Sign Out
        </button>
      </div>
    </Sheet>
  )
}

// Pre-built modal data for quiz/poll details
const MODAL_DATA = {
  'quiz-correct-scrum': {
    result: 'correct', context: 'WIA2005 · Lec 12 · 10:12 AM',
    question: 'Which software development model uses iterative development with fixed-length sprints?',
    options: ['Waterfall', 'Scrum', 'Kanban', 'V-Model'],
    correctIndex: 1, myIndex: 1,
    stats: [
      { value: '8s',  color: 'var(--green)',    labelColor: 'var(--green-dk)',  bg: 'var(--green-lt)',  border: 'none',                         label: 'Your time'    },
      { value: '19s', color: 'var(--text)',      labelColor: 'var(--text-sub)', bg: 'var(--gray-50)',   border: '1px solid var(--border)',      label: 'Class avg'    },
      { value: '4/5', color: 'var(--blue)',      labelColor: 'var(--blue-dk)',  bg: 'var(--blue-lt)',   border: 'none',                         label: 'Answered'     },
      { value: '60%', color: 'var(--green)',     labelColor: 'var(--green-dk)', bg: 'var(--green-lt)',  border: 'none',                         label: 'Class correct' },
    ],
  },
  'quiz-wrong-solid': {
    result: 'wrong', context: 'WIA2005 · Lec 11 · 10:08 AM',
    question: 'What does SOLID stand for in object-oriented design?',
    options: ['Single Responsibility only', 'Single, Open, Liskov, Interface, Dependency', 'Static, Open, Lean, Integrated, Dynamic', 'None of the above'],
    correctIndex: 1, myIndex: 0,
    stats: [
      { value: '42s', color: 'var(--orange)',    labelColor: 'var(--orange-dk)', bg: 'var(--orange-lt)', border: 'none',                         label: 'Your time'    },
      { value: '31s', color: 'var(--text)',      labelColor: 'var(--text-sub)',  bg: 'var(--gray-50)',   border: '1px solid var(--border)',      label: 'Class avg'    },
      { value: '5/5', color: 'var(--blue)',      labelColor: 'var(--blue-dk)',   bg: 'var(--blue-lt)',   border: 'none',                         label: 'Answered'     },
      { value: '40%', color: 'var(--green)',     labelColor: 'var(--green-dk)',  bg: 'var(--green-lt)',  border: 'none',                         label: 'Class correct' },
    ],
  },
  'quiz-correct-uml': {
    result: 'correct', context: 'WIA2005 · Lec 11 · 10:32 AM',
    question: 'Which UML diagram best represents a sequence of system operations?',
    options: ['Class Diagram', 'Use Case Diagram', 'Sequence Diagram', 'Activity Diagram'],
    correctIndex: 2, myIndex: 2,
    stats: [
      { value: '11s', color: 'var(--green)',    labelColor: 'var(--green-dk)',  bg: 'var(--green-lt)', border: 'none',                         label: 'Your time'    },
      { value: '22s', color: 'var(--text)',     labelColor: 'var(--text-sub)', bg: 'var(--gray-50)',  border: '1px solid var(--border)',      label: 'Class avg'    },
      { value: '5/5', color: 'var(--blue)',     labelColor: 'var(--blue-dk)',  bg: 'var(--blue-lt)',  border: 'none',                         label: 'Answered'     },
      { value: '70%', color: 'var(--green)',    labelColor: 'var(--green-dk)', bg: 'var(--green-lt)', border: 'none',                         label: 'Class correct' },
    ],
  },
  'quiz-expired-3nf': {
    result: 'expired', context: 'WIA2004 · Lec 11 · 2:18 PM',
    question: 'Which normal form eliminates transitive dependencies?',
    options: ['1NF', '2NF', '3NF (Correct Answer)', 'BCNF'],
    correctIndex: 2, myIndex: -1,
    stats: [
      { value: '—',   color: 'var(--red)',       labelColor: 'var(--red-dk)',   bg: 'var(--red-lt)',   border: 'none',                         label: 'Your time'    },
      { value: '18s', color: 'var(--text)',      labelColor: 'var(--text-sub)', bg: 'var(--gray-50)',  border: '1px solid var(--border)',      label: 'Class avg'    },
      { value: '4/5', color: 'var(--blue)',      labelColor: 'var(--blue-dk)',  bg: 'var(--blue-lt)',  border: 'none',                         label: 'Answered'     },
      { value: '65%', color: 'var(--green)',     labelColor: 'var(--green-dk)', bg: 'var(--green-lt)', border: 'none',                         label: 'Class correct' },
    ],
  },
}

const POLL_DATA = {
  'poll-sprint': {
    context: 'WIA2005 · Lec 12 · 10:35 AM',
    question: 'Which part of sprint planning do you find most confusing?',
    options: [
      { label: 'User Stories', pct: 15, isMyChoice: false },
      { label: 'Estimation',   pct: 28, isMyChoice: false },
      { label: 'Story points', pct: 45, isMyChoice: true  },
      { label: 'Velocity',     pct: 12, isMyChoice: false },
    ],
    stats: [
      { value: 'C',    color: 'var(--purple)',    labelColor: 'var(--purple-dk)', bg: 'var(--purple-lt)', border: 'none',                    label: 'Your answer' },
      { value: '45%',  color: 'var(--text)',      labelColor: 'var(--text-sub)',  bg: 'var(--gray-50)',   border: '1px solid var(--border)', label: 'Plurality'   },
      { value: '48/50', color: 'var(--blue)',     labelColor: 'var(--blue-dk)',   bg: 'var(--blue-lt)',   border: 'none',                    label: 'Voted'       },
    ],
  },
}

export default function ModalRouter() {
  const { state, dispatch, closeModal, navigate } = useStudent()
  const { modal } = state
  if (!modal) return null

  const overlay = (content) => (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && closeModal()}>
      {content}
    </div>
  )

  switch (modal.type) {
    case 'forgot-password':
      return overlay(<ForgotPasswordModal onClose={closeModal} />)
    case 'report-issue':
      return overlay(<ReportIssueModal data={modal.data} onClose={closeModal} navigate={navigate} />)
    case 'quiz-detail':
      return overlay(<QuizDetailModal data={MODAL_DATA[modal.data?.key]} onClose={closeModal} />)
    case 'poll-detail':
      return overlay(<PollDetailModal data={POLL_DATA[modal.data?.key]} onClose={closeModal} />)
    case 'signout':
      return overlay(<SignOutModal onClose={closeModal} dispatch={dispatch} />)
    default:
      return null
  }
}
