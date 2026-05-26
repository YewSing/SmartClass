import { useEffect } from 'react'
import { useStudent } from '../../context/StudentContext'

function ToastItem({ toast }) {
  const { dispatch } = useStudent()
  useEffect(() => {
    const t = setTimeout(() => dispatch({ type: 'DISMISS_TOAST', payload: toast.id }), 3000)
    return () => clearTimeout(t)
  }, [toast.id, dispatch])

  const bg = toast.variant === 'success' ? 'var(--green)' : toast.variant === 'error' ? 'var(--red)' : 'var(--gray-800)'
  return (
    <div style={{
      background: bg, color: '#fff', padding: '12px 16px', borderRadius: 'var(--radius-sm)',
      fontSize: 13, fontWeight: 600, boxShadow: '0 4px 16px rgba(0,0,0,.2)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
    }}>
      <span>{toast.message}</span>
      <button onClick={() => dispatch({ type: 'DISMISS_TOAST', payload: toast.id })}
        style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', fontSize: 14, opacity: .7 }}>
        <i className="fa fa-times"></i>
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const { state } = useStudent()
  if (!state.toasts.length) return null
  return (
    <div style={{
      position: 'absolute', bottom: 80, left: 16, right: 16, zIndex: 200,
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      {state.toasts.map(t => <ToastItem key={t.id} toast={t} />)}
    </div>
  )
}
