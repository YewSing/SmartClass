import { useState } from 'react'
import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import { login } from '../services/api'

export default function Login() {
  const { dispatch, openModal } = useStudent()
  const [email, setEmail] = useState('u23001234@siswa.um.edu.my')
  const [password, setPassword] = useState('password')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    setLoading(true)
    try {
      await login(email, password)
      dispatch({ type: 'LOGIN' })
    } catch {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '844px', background: 'linear-gradient(160deg,#E5F3FF 0%,#F5F6F8 55%)' }}>
      <StatusBar time="9:41" />
      <div className="login-top">
        <div className="app-logo"><i className="fa fa-graduation-cap"></i></div>
        <div className="app-name">SmartClass</div>
        <div className="app-tagline">Student Portal · University of Malaya<br />Faculty of Computer Science &amp; IT</div>
      </div>
      <div className="login-form">
        <h2>Welcome back</h2>
        <div className="sub">Sign in with your student credentials</div>
        <div className="form-group">
          <label className="form-label">Matric email</label>
          <div className="input-wrap">
            <i className="fa fa-envelope lead"></i>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
        </div>
        <div className="form-group">
          <label className="form-label">Password</label>
          <div className="input-wrap">
            <i className="fa fa-lock lead"></i>
            <input
              type={showPw ? 'text' : 'password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
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
          disabled={loading}
        >
          {loading ? <i className="fa fa-spinner fa-spin"></i> : <><i className="fa fa-sign-in-alt"></i> Sign In</>}
        </button>
        <div className="login-note" style={{ marginTop: 14 }}>
          <i className="fa fa-info-circle"></i> Accounts are provisioned by administrators only
        </div>
      </div>
    </div>
  )
}
