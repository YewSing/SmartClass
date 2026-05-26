import { useState } from 'react'
import { useLecturer } from '../../context/LecturerContext'

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
      <div className="form-group"><input type="email" placeholder="your@um.edu.my" /></div>
      <button className="btn btn-primary btn-full" onClick={onClose}>
        <i className="fa fa-paper-plane"></i> Send Reset Link
      </button>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
    </Sheet>
  )
}

function ConfusionResetModal({ onClose }) {
  return (
    <Sheet>
      <div className="modal-title">Reset Confusion Counter</div>
      <div style={{ fontSize: 14, color: 'var(--text-sub)', marginBottom: 14, lineHeight: 1.5 }}>
        This will reset the confusion counter to 0%. Students' "I Don't Understand" signals will be cleared. Historical IDU logs are preserved.
      </div>
      <div style={{ background: 'var(--yellow-lt)', border: '1px solid var(--yellow)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', marginBottom: 16, fontSize: 13, color: 'var(--yellow-dk)' }}>
        <i className="fa fa-exclamation-triangle"></i> Current rate: <strong>34%</strong> · 8 signals this session
      </div>
      <div className="btn-row">
        <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary btn-full" onClick={onClose}><i className="fa fa-redo"></i> Confirm Reset</button>
      </div>
    </Sheet>
  )
}

function QuizModal({ quiz, onClose, navigate }) {
  if (!quiz) return null
  if (quiz.status === 'active') return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span className="badge blue dot">Active</span>
        <span style={{ fontSize: 12, color: 'var(--text-sub)' }}>Today, {quiz.time} · {quiz.timer}</span>
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', lineHeight: 1.5, marginBottom: 12 }}>{quiz.question}</div>
      <div style={{ background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)', padding: 12, marginBottom: 12, fontSize: 13, color: 'var(--text)', lineHeight: 2.1 }}>
        {quiz.options.map((o, i) => <div key={i}>{String.fromCharCode(65+i)}. {i === quiz.correct ? <strong>{o} ✓</strong> : o}</div>)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <div className="status-dot green"></div>
        <span style={{ fontSize: 13, color: 'var(--text-sub)' }}>Answered: {quiz.answered} / {quiz.total} students</span>
      </div>
      <div className="btn-row">
        <button className="btn btn-danger btn-full" onClick={onClose}><i className="fa fa-stop"></i> Close Early</button>
        <button className="btn btn-primary btn-full" onClick={() => { onClose(); navigate('live-results') }}><i className="fa fa-chart-bar"></i> Live Results</button>
      </div>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Dismiss</button>
    </Sheet>
  )

  if (quiz.status === 'closed') return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span className="badge gray">Closed</span>
        <span style={{ fontSize: 12, color: 'var(--text-sub)' }}>Today, {quiz.time} · {quiz.timer}</span>
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', lineHeight: 1.5, marginBottom: 12 }}>{quiz.question}</div>
      <div style={{ background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)', padding: 12, marginBottom: 12, display: 'flex', gap: 14, textAlign: 'center' }}>
        <div style={{ flex: 1 }}><div style={{ fontSize: 20, fontWeight: 700, color: 'var(--green)' }}>{quiz.correct_count}</div><div style={{ fontSize: 11, color: 'var(--green-dk)', fontWeight: 700 }}>Correct</div></div>
        <div style={{ flex: 1 }}><div style={{ fontSize: 20, fontWeight: 700, color: 'var(--red)' }}>{quiz.wrong_count}</div><div style={{ fontSize: 11, color: 'var(--red-dk)', fontWeight: 700 }}>Incorrect</div></div>
        <div style={{ flex: 1 }}><div style={{ fontSize: 20, fontWeight: 700, color: 'var(--gray-400)' }}>{quiz.unanswered_count}</div><div style={{ fontSize: 11, color: 'var(--gray-500)', fontWeight: 700 }}>Unanswered</div></div>
      </div>
      <div className="btn-row">
        <button className="btn btn-outline btn-full" onClick={() => { onClose(); navigate('results-closed') }}><i className="fa fa-chart-bar"></i> View Results</button>
        <button className="btn btn-primary btn-full" onClick={() => { onClose(); navigate('breakdown') }}><i className="fa fa-list"></i> Breakdown</button>
      </div>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Dismiss</button>
    </Sheet>
  )

  return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span className="badge yellow">Draft</span>
        <span style={{ fontSize: 12, color: 'var(--text-sub)' }}>Today, {quiz.time}</span>
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', lineHeight: 1.5, marginBottom: 12 }}>{quiz.question}</div>
      <div style={{ background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)', padding: 12, marginBottom: 14, fontSize: 13, color: 'var(--text)', lineHeight: 2.1 }}>
        {quiz.options.map((o, i) => <div key={i}>{String.fromCharCode(65+i)}. {i === quiz.correct ? <strong>{o} ✓</strong> : o}</div>)}
      </div>
      <button className="btn btn-primary btn-full" style={{ marginBottom: 8 }} onClick={onClose}><i className="fa fa-paper-plane"></i> Push to All Desks</button>
      <div className="btn-row">
        <button className="btn btn-outline btn-full" onClick={() => { onClose(); navigate('create-quiz') }}><i className="fa fa-edit"></i> Edit</button>
        <button className="btn btn-danger btn-full" onClick={onClose}><i className="fa fa-trash"></i> Delete</button>
      </div>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Dismiss</button>
    </Sheet>
  )
}

function StudentModal({ data, onClose }) {
  if (!data) return null
  const statusBadge = data.status === 'present'
    ? <span className="badge green dot">Present</span>
    : data.status === 'absent'
    ? <span className="badge red dot">Absent</span>
    : <span className="badge orange dot">Unidentified</span>
  const avatarStyle = data.status === 'present'
    ? { background: 'var(--blue-lt)', color: 'var(--blue-dk)' }
    : data.status === 'absent'
    ? { background: 'var(--red-lt)', color: 'var(--red-dk)' }
    : { background: 'var(--orange-lt)', color: 'var(--orange-dk)' }
  const initials = data.name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()
  return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div className="student-avatar" style={{ ...avatarStyle, width: 48, height: 48, fontSize: 16 }}>{initials}</div>
        <div>
          <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)' }}>{data.name}</div>
          <div style={{ fontSize: 13, color: 'var(--text-sub)' }}>{data.id} · WIA2005</div>
        </div>
      </div>
      <div style={{ background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: 'var(--text-sub)', marginBottom: 4, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.05em' }}>Current Status</div>
        {statusBadge}
      </div>
      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>Manual Override</div>
      <div style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 14 }}>This override is logged with your identity and timestamp.</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <button className="btn btn-green btn-full" onClick={onClose}><i className="fa fa-check"></i> Mark Present</button>
        <button className="btn btn-danger btn-full" onClick={onClose}><i className="fa fa-times"></i> Mark Absent</button>
      </div>
      <button className="btn btn-outline btn-full" style={{ marginBottom: 8 }} onClick={onClose}><i className="fa fa-clipboard"></i> Mark Excused</button>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
    </Sheet>
  )
}

function ExportModal({ onClose }) {
  const [selected, setSelected] = useState('pdf')
  return (
    <Sheet>
      <div className="modal-title">Export Report</div>
      <div style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 16 }}>WIA2005 · Attendance · This month</div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        {[{ id: 'pdf', icon: 'fa-file-pdf', iconColor: 'var(--red)', label: 'PDF', sub: 'Formatted report' },
          { id: 'csv', icon: 'fa-file-csv', iconColor: 'var(--green)', label: 'CSV', sub: 'Raw data spreadsheet' }].map(f => (
          <div key={f.id} onClick={() => setSelected(f.id)}
            style={{ flex: 1, border: selected === f.id ? '2px solid var(--blue)' : '1.5px solid var(--border)', borderRadius: 'var(--radius)', padding: 16, textAlign: 'center', cursor: 'pointer' }}>
            <i className={`fa ${f.icon}`} style={{ fontSize: 28, color: f.iconColor }}></i>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', marginTop: 6 }}>{f.label}</div>
            <div style={{ fontSize: 11, color: 'var(--text-sub)' }}>{f.sub}</div>
          </div>
        ))}
      </div>
      <button className="btn btn-primary btn-full" onClick={onClose}><i className="fa fa-download"></i> Export {selected.toUpperCase()}</button>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
    </Sheet>
  )
}

function OverrideLightsModal({ onClose }) {
  const [mode, setMode] = useState('Auto')
  const [on, setOn] = useState(true)
  return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--yellow-lt)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <i className="fa fa-lightbulb" style={{ fontSize: 18, color: 'var(--yellow)' }}></i>
        </div>
        <div className="modal-title" style={{ margin: 0 }}>Lights Override</div>
      </div>
      <div className="override-group">
        <div className="override-label">Control Mode</div>
        <div className="mode-pills">
          {['Auto', 'Manual'].map(m => (
            <button key={m} className={`mode-pill${mode === m ? ' active' : ''}`} onClick={() => setMode(m)}>{m}</button>
          ))}
        </div>
      </div>
      <div className="override-group">
        <div className="override-label">State</div>
        <div className="onoff-pills">
          <button className={`onoff-pill on${on ? ' active' : ''}`} onClick={() => setOn(true)}>ON</button>
          <button className={`onoff-pill off${!on ? ' active' : ''}`} onClick={() => setOn(false)}>OFF</button>
        </div>
      </div>
      <button className="btn btn-primary btn-full" onClick={onClose}><i className="fa fa-check"></i> Confirm Override</button>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
    </Sheet>
  )
}

function OverrideACModal({ onClose }) {
  const [mode, setMode] = useState('Auto')
  const [on, setOn] = useState(true)
  const [temp, setTemp] = useState(23)
  return (
    <Sheet>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--blue-lt)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <i className="fa fa-snowflake" style={{ fontSize: 18, color: 'var(--blue)' }}></i>
        </div>
        <div className="modal-title" style={{ margin: 0 }}>AC Override</div>
      </div>
      <div className="override-group">
        <div className="override-label">Control Mode</div>
        <div className="mode-pills">
          {['Auto', 'Manual'].map(m => (
            <button key={m} className={`mode-pill${mode === m ? ' active' : ''}`} onClick={() => setMode(m)}>{m}</button>
          ))}
        </div>
      </div>
      <div className="override-group">
        <div className="override-label">State</div>
        <div className="onoff-pills">
          <button className={`onoff-pill on${on ? ' active' : ''}`} onClick={() => setOn(true)}>ON</button>
          <button className={`onoff-pill off${!on ? ' active' : ''}`} onClick={() => setOn(false)}>OFF</button>
        </div>
      </div>
      <div className="override-group temp-slider-block">
        <div className="override-label">Target Temperature</div>
        <div className="temp-display">{temp} <span>°C</span></div>
        <input type="range" min={16} max={30} value={temp} step={1} onChange={e => setTemp(+e.target.value)} />
        <div className="temp-range-labels"><span>16°C (cool)</span><span>23°C</span><span>30°C (warm)</span></div>
        <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
          {[{ v: 18, label: '18°C', sub: 'Very cool', bg: 'var(--blue-lt)', color: 'var(--blue-dk)', subColor: 'var(--blue)' },
            { v: 23, label: '23°C', sub: 'Recommended', bg: 'var(--blue-lt)', color: 'var(--blue-dk)', subColor: 'var(--blue)', selected: true },
            { v: 26, label: '26°C', sub: 'Energy saving', bg: 'var(--yellow-lt)', color: 'var(--yellow-dk)', subColor: 'var(--yellow)' }].map(p => (
            <div key={p.v} onClick={() => setTemp(p.v)}
              style={{ flex: 1, background: p.bg, borderRadius: 'var(--radius-sm)', padding: 8, textAlign: 'center', cursor: 'pointer', border: temp === p.v ? '2px solid var(--blue)' : 'none' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: p.color }}>{p.label}</div>
              <div style={{ fontSize: 10, color: p.subColor }}>{p.sub}</div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ background: 'var(--blue-lt)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', marginBottom: 14, fontSize: 12, color: 'var(--blue-dk)' }}>
        <i className="fa fa-info-circle"></i> In Auto mode, AC activates when occupancy ≥ 5. Temperature setpoint applies in both modes.
      </div>
      <button className="btn btn-primary btn-full" onClick={onClose}><i className="fa fa-check"></i> Confirm Override</button>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
    </Sheet>
  )
}

function ChangePasswordModal({ onClose }) {
  return (
    <Sheet>
      <div className="modal-title"><i className="fa fa-lock" style={{ color: 'var(--blue)' }}></i> &nbsp;Change Password</div>
      <div style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 16 }}>Your new password must be at least 8 characters.</div>
      <div className="form-group"><label className="form-label">Current Password</label><div className="input-wrap"><i className="fa fa-lock lead"></i><input type="password" placeholder="Enter current password" /></div></div>
      <div className="form-group"><label className="form-label">New Password</label><div className="input-wrap"><i className="fa fa-key lead"></i><input type="password" placeholder="Enter new password" /></div></div>
      <div className="form-group"><label className="form-label">Confirm New Password</label><div className="input-wrap"><i className="fa fa-key lead"></i><input type="password" placeholder="Re-enter new password" /></div></div>
      <button className="btn btn-primary btn-full" onClick={onClose}><i className="fa fa-check"></i> Update Password</button>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Cancel</button>
    </Sheet>
  )
}

function SessionInfoModal({ onClose }) {
  return (
    <Sheet>
      <div className="modal-title"><i className="fa fa-clock" style={{ color: 'var(--green)' }}></i> &nbsp;Login Activity</div>
      <div style={{ background: 'var(--green-lt)', borderRadius: 'var(--radius-sm)', padding: '12px 14px', marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: 'var(--green-dk)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 4 }}>Current Session</div>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>Today, 24 May 2025</div>
        <div style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 2 }}>Logged in at 9:41 AM · Android App</div>
      </div>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 10 }}>Recent Activity</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {[{ date: '23 May 2025', sub: 'Android App · 8:05 AM' }, { date: '21 May 2025', sub: 'Android App · 10:02 AM' }].map(r => (
          <div key={r.date} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)' }}>
            <div><div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{r.date}</div><div style={{ fontSize: 12, color: 'var(--text-sub)' }}>{r.sub}</div></div>
            <span className="badge green">Success</span>
          </div>
        ))}
      </div>
      <hr className="modal-divider" />
      <button className="btn btn-outline btn-full" onClick={onClose}>Close</button>
    </Sheet>
  )
}

function SignOutModal({ onClose, dispatch }) {
  return (
    <Sheet>
      <div className="modal-title">Sign Out</div>
      <div style={{ fontSize: 14, color: 'var(--text-sub)', marginBottom: 18, lineHeight: 1.5 }}>
        Are you sure you want to sign out? Active sessions will continue running in the background.
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

export default function ModalRouter() {
  const { state, dispatch, closeModal, navigate } = useLecturer()
  const { modal } = state
  if (!modal) return null

  const overlay = (content) => (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && closeModal()}>
      {content}
    </div>
  )

  switch (modal.type) {
    case 'forgot-password':    return overlay(<ForgotPasswordModal onClose={closeModal} />)
    case 'confusion-reset':    return overlay(<ConfusionResetModal onClose={closeModal} />)
    case 'quiz':               return overlay(<QuizModal quiz={modal.data} onClose={closeModal} navigate={navigate} />)
    case 'student':            return overlay(<StudentModal data={modal.data} onClose={closeModal} />)
    case 'export':             return overlay(<ExportModal onClose={closeModal} />)
    case 'override-lights':    return overlay(<OverrideLightsModal onClose={closeModal} />)
    case 'override-ac':        return overlay(<OverrideACModal onClose={closeModal} />)
    case 'change-password':    return overlay(<ChangePasswordModal onClose={closeModal} />)
    case 'session-info':       return overlay(<SessionInfoModal onClose={closeModal} />)
    case 'signout':            return overlay(<SignOutModal onClose={closeModal} dispatch={dispatch} />)
    default:                   return null
  }
}
