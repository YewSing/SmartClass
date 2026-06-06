import { useState } from 'react'
import { useAdmin } from '../context/AdminContext'

export default function Login() {
  const { login, loadUsers, toast } = useAdmin()
  const [email, setEmail] = useState('admin@um.edu.my')
  const [pass, setPass] = useState('Admin@1234')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const handleLogin = async () => {
    if (!email) { toast('Enter your email', 'error'); return }
    setErr('')
    setLoading(true)
    try {
      await login(email, pass)
      await loadUsers()
      toast('Welcome back, Admin', 'success')
    } catch (e) {
      setErr(e.message || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-accent-lt via-bg to-bg z-[200] flex items-center justify-center">
      <div className="w-[400px] bg-surface border border-border rounded-2xl p-10 shadow-2xl">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent to-accent2 flex items-center justify-center font-sans text-lg font-bold text-white">
            SC
          </div>
          <div>
            <div className="font-sans text-[22px] font-bold text-text1">SmartClass</div>
            <div className="text-[12.5px] text-text3 mt-0.5">Admin Panel — UM FCSIT</div>
          </div>
        </div>

        {err && (
          <div className="mb-3 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-[13px] text-red-700">
            {err}
          </div>
        )}

        <div className="space-y-3.5">
          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-medium text-text2">Email / Staff ID</label>
            <div className="relative">
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                className="w-full bg-surface2 border border-border rounded-lg px-3 py-2.5 pr-8 text-[13.5px] text-text1 outline-none focus:border-accent transition-colors"
                placeholder="admin@um.edu.my"
              />
              {email && (
                <button onClick={() => setEmail('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-text3 hover:text-text1 text-[12px] leading-none">✕</button>
              )}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-medium text-text2">Password</label>
            <input
              type="password"
              value={pass}
              onChange={e => setPass(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              className="bg-surface2 border border-border rounded-lg px-3 py-2.5 text-[13.5px] text-text1 outline-none focus:border-accent transition-colors"
              placeholder="••••••••"
            />
          </div>
        </div>

        <button
          onClick={handleLogin}
          disabled={loading}
          className="w-full mt-4 py-2.5 bg-accent hover:bg-accent-dk text-white font-semibold text-[14px] rounded-lg transition-colors disabled:opacity-60"
        >
          {loading ? 'Signing in…' : 'Sign In to Admin Panel'}
        </button>

        <p className="text-[11px] text-text3 text-center mt-4">
          ⚠ Access restricted to administrators only
        </p>
      </div>
    </div>
  )
}
