import { useState } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'

export default function Login() {
  const { login, openModal, state } = useLecturer()
  const [email, setEmail] = useState('ahmad.lecturer@um.edu.my')
  const [password, setPassword] = useState('Lecturer@1234')
  const [showPw, setShowPw] = useState(false)
  const [localErr, setLocalErr] = useState('')

  const handleLogin = async () => {
    setLocalErr('')
    try {
      await login(email, password)
    } catch (e) {
      setLocalErr(e.message || 'Invalid credentials')
    }
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'linear-gradient(160deg,#EBF2FF 0%,#F5F6F8 55%)' }}>
      <StatusBar />
      <div className="login-top">
        <div className="app-logo"><i className="fa fa-graduation-cap"></i></div>
        <div className="app-name">SmartClass</div>
        <div className="app-tagline">Lecturer Portal · University of Malaya<br />Faculty of Computer Science &amp; IT</div>
      </div>
      <div className="login-form">
        <h2>Welcome back</h2>
        <div className="sub">Sign in with your university credentials</div>
        {localErr && (
          <div style={{ background: 'var(--red-lt)', color: 'var(--red-dk)', borderRadius: 8, padding: '8px 12px', fontSize: 13, marginBottom: 12 }}>
            {localErr}
          </div>
        )}
        <div className="form-group">
          <label className="form-label">Email address</label>
          <div className="input-wrap">
            <i className="fa fa-envelope lead"></i>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Password</label>
          <div className="input-wrap">
            <i className="fa fa-lock lead"></i>
            <input type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} />
            <button className="input-icon-btn" onClick={() => setShowPw(v => !v)}>
              <i className={`fa ${showPw ? 'fa-eye' : 'fa-eye-slash'}`}></i>
            </button>
          </div>
        </div>
        <div className="forgot-link" onClick={() => openModal('forgot-password')}>Forgot password?</div>
        <button
          className="btn btn-primary btn-full"
          style={{ padding: 13 }}
          onClick={handleLogin}
          disabled={state.loading}
        >
          {state.loading
            ? <><i className="fa fa-spinner fa-spin"></i> Signing in…</>
            : <><i className="fa fa-sign-in-alt"></i> Sign In</>}
        </button>
        <div className="login-note" style={{ marginTop: 14 }}>
          <i className="fa fa-info-circle"></i> Accounts are provisioned by administrators only
        </div>
      </div>
    </div>
  )
}
