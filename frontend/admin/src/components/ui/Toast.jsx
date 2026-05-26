import { useAdmin } from '../../context/AdminContext'

const STYLES = {
  success: { bar: 'border-l-sc-green', icon: '✓' },
  error:   { bar: 'border-l-sc-red',   icon: '✕' },
  info:    { bar: 'border-l-accent',   icon: 'ℹ' },
}

export default function ToastContainer() {
  const { state } = useAdmin()

  return (
    <div className="fixed bottom-6 right-6 z-[500] flex flex-col gap-2">
      {state.toasts.map(t => {
        const s = STYLES[t.type] ?? STYLES.info
        return (
          <div
            key={t.id}
            className={`flex items-center gap-2.5 px-4 py-3 bg-surface border border-border rounded-xl text-[13px] shadow-lg border-l-[3px] ${s.bar} max-w-xs animate-slideInRight`}
          >
            <span className="text-sm">{s.icon}</span>
            <span className="text-text1">{t.msg}</span>
          </div>
        )
      })}
      <style>{`
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(20px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        .animate-slideInRight { animation: slideInRight 0.25s ease; }
      `}</style>
    </div>
  )
}
