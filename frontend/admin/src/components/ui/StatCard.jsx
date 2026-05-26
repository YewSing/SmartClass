export default function StatCard({ label, value, sub, accentColor = '#1B6EF3' }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-[18px] relative overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-0.5" style={{ background: accentColor }} />
      <div className="text-[11px] text-text3 font-medium uppercase tracking-[0.07em] mb-2">{label}</div>
      <div className="font-sans text-[28px] font-bold text-text1 leading-none">{value}</div>
      {sub && <div className="text-[11.5px] text-text3 mt-1.5">{sub}</div>}
    </div>
  )
}
