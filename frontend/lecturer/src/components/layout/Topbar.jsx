export default function Topbar({ title, sub, onBack, right }) {
  return (
    <div className="topbar">
      {onBack && (
        <button className="back-btn" onClick={onBack}>
          <i className="fa fa-arrow-left"></i>
        </button>
      )}
      <div style={{ flex: 1 }}>
        <div className="topbar-title">{title}</div>
        {sub && <div className="topbar-sub">{sub}</div>}
      </div>
      {right}
    </div>
  )
}
