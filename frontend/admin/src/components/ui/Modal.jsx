import { useEffect } from 'react'

export default function Modal({ title, subtitle, children, footer, onClose, size = 'md' }) {
  const widths = { sm: 'w-[380px]', md: 'w-[480px]', lg: 'w-[600px]' }

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 bg-black/55 backdrop-blur-sm z-50 flex items-center justify-center"
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.() }}
    >
      <div className={`bg-surface border border-border rounded-2xl ${widths[size]} max-w-[95vw] max-h-[90vh] overflow-y-auto shadow-2xl animate-slideUp`}>
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-border">
          <div>
            <div className="text-[15px] font-semibold text-text1">{title}</div>
            {subtitle && <div className="text-[12px] text-text3 mt-0.5">{subtitle}</div>}
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md bg-surface2 border border-border text-text2 hover:bg-surface3 hover:text-text1 flex items-center justify-center text-base transition-all"
          >
            ✕
          </button>
        </div>

        <div className="px-6 py-5">{children}</div>

        {footer && (
          <div className="px-6 py-4 border-t border-border flex gap-2.5 justify-end">{footer}</div>
        )}
      </div>

      <style>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .animate-slideUp { animation: slideUp 0.2s ease; }
      `}</style>
    </div>
  )
}
