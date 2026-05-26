import { useState } from 'react'
import { useAdmin } from '../context/AdminContext'

export default function Login() {
  const { dispatch, toast } = useAdmin()
  const [email, setEmail] = useState('admin@um.edu.my')
  const [pass, setPass] = useState('password')

  const handleLogin = () => {
    if (!email) { toast('Enter your email', 'error'); return }
    dispatch({ type: 'LOGIN' })
    toast('Welcome back, Admin User', 'success')
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

        <div className="space-y-3.5">
          <div className="flex flex-col gap-1.5">
            <label className="text-[12px] font-medium text-text2">Email / Staff ID</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
              className="bg-surface2 border border-border rounded-lg px-3 py-2.5 text-[13.5px] text-text1 outline-none focus:border-accent transition-colors"
              placeholder="admin@um.edu.my"
            />
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
          className="w-full mt-4 py-2.5 bg-accent hover:bg-accent-dk text-white font-semibold text-[14px] rounded-lg transition-colors"
        >
          Sign In to Admin Panel
        </button>

        <p className="text-[11px] text-text3 text-center mt-4">
          ⚠ Access restricted to administrators only (NFR-03, NFR-04)
        </p>
      </div>
    </div>
  )
}
