export default function StatusBar({ time = '9:41' }) {
  return (
    <div className="status-bar">
      <span className="status-time">{time}</span>
      <div className="status-icons">
        <i className="fa fa-signal"></i>
        <i className="fa fa-wifi"></i>
        <i className="fa fa-battery-full"></i>
      </div>
    </div>
  )
}
