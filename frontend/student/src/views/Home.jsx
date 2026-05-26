import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import { ENROLLED_CLASSES } from '../data/mockData'

export default function Home() {
  const { navigate } = useStudent()

  const getFooterStat = (cls) => {
    if (cls.status === 'present') {
      return (
        <div className="class-card-footer-stat" style={{ color: 'var(--green-dk)' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }}></span>
          Present today
        </div>
      )
    }
    if (cls.status === 'warning') {
      return (
        <div className="class-card-footer-stat" style={{ color: 'var(--orange-dk)' }}>
          <i className="fa fa-exclamation-circle" style={{ fontSize: 12, color: 'var(--orange)' }}></i>
          {cls.attendedCount}/{cls.totalSessions} attended
        </div>
      )
    }
    return (
      <div className="class-card-footer-stat" style={{ color: 'var(--text-sub)' }}>
        Next: {cls.nextSchedule}
      </div>
    )
  }

  const getAttendanceStat = (cls) => {
    const color = cls.status === 'warning' ? 'var(--orange-dk)' : 'var(--text-sub)'
    const icon  = cls.status === 'warning' ? 'fa-exclamation-circle' : 'fa-check-circle'
    const iconColor = cls.status === 'warning' ? 'var(--orange)' : 'var(--green)'
    return (
      <div className="class-card-footer-stat" style={{ color }}>
        <i className={`fa ${icon}`} style={{ fontSize: 12, color: iconColor }}></i>
        {cls.attendedCount}/{cls.totalSessions} attended
      </div>
    )
  }

  const liveClass = ENROLLED_CLASSES.find(c => c.liveSession)

  return (
    <>
      <StatusBar time="10:07" />
      <div className="scroll-body">
        <div className="greeting-banner">
          <div className="greeting-text">Good morning,</div>
          <div className="greeting-name">Amirul Chow</div>
          <div className="greeting-sub">Sem 2 2024/25 &nbsp;·&nbsp; 4 enrolled classes</div>
        </div>

        {liveClass && (
          <div style={{ background: 'var(--green-lt)', borderBottom: '1px solid #9DE8C5', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="live-dot"></div>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--green-dk)' }}>
              {liveClass.code} session is live right now
            </span>
            <span style={{ fontSize: 12, color: 'var(--green-dk)', marginLeft: 'auto' }}>
              {liveClass.liveTime}
            </span>
          </div>
        )}

        <div className="section-header" style={{ paddingTop: 14 }}>
          <span className="section-title">My Classes</span>
        </div>

        {ENROLLED_CLASSES.map(cls => (
          <div key={cls.code} className="class-card tappable-card" onClick={() => navigate('attendance')}>
            <div className="class-card-accent" style={{ background: cls.accentColor }}></div>
            <div className="class-card-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div className="class-code">{cls.code}</div>
                {cls.liveSession && (
                  <div className="live-chip"><div className="live-dot"></div>Live Session</div>
                )}
              </div>
              <div className="class-title">{cls.name}</div>
              <div className="class-meta-row">
                <div className="class-meta-item"><i className="fa fa-user"></i> {cls.lecturer}</div>
                <div className="class-meta-item"><i className="fa fa-map-marker-alt"></i> {cls.venue}</div>
              </div>
            </div>
            <div className="class-card-footer">
              {getFooterStat(cls)}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {cls.status !== 'present' && getAttendanceStat(cls)}
                <i className="fa fa-chevron-right" style={{ fontSize: 12, color: 'var(--gray-400)' }}></i>
              </div>
            </div>
          </div>
        ))}

        <div style={{ height: 16 }}></div>
      </div>
    </>
  )
}
