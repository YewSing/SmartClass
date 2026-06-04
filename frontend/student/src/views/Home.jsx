import { useEffect } from 'react'
import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'

export default function Home() {
  const { state, navigate, loadClasses } = useStudent()
  const { classes, student } = state

  useEffect(() => { loadClasses() }, [loadClasses])

  const firstName = student?.name?.split(' ')[0] ?? 'there'

  return (
    <>
      <StatusBar time="10:07" />
      <div className="scroll-body">
        <div className="greeting-banner">
          <div className="greeting-text">Good morning,</div>
          <div className="greeting-name">{firstName}</div>
          <div className="greeting-sub">
            {classes.length > 0 ? `${classes.length} enrolled class${classes.length !== 1 ? 'es' : ''}` : 'Loading classes…'}
          </div>
        </div>

        <div className="section-header" style={{ paddingTop: 14 }}>
          <span className="section-title">My Classes</span>
        </div>

        {classes.map(cls => (
          <div key={cls.code} className="class-card tappable-card" onClick={() => navigate('attendance')}>
            <div className="class-card-accent" style={{ background: cls.accentColor }}></div>
            <div className="class-card-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div className="class-code">{cls.code}</div>
              </div>
              <div className="class-title">{cls.name}</div>
              <div className="class-meta-row">
                {cls.venue && <div className="class-meta-item"><i className="fa fa-map-marker-alt"></i> {cls.venue}</div>}
              </div>
            </div>
            <div className="class-card-footer">
              <div className="class-card-footer-stat" style={{ color: 'var(--text-sub)' }}>
                Tap to view attendance
              </div>
              <i className="fa fa-chevron-right" style={{ fontSize: 12, color: 'var(--gray-400)' }}></i>
            </div>
          </div>
        ))}

        {classes.length === 0 && (
          <div style={{ padding: '40px 24px', textAlign: 'center', color: 'var(--text-sub)', fontSize: 14 }}>
            No enrolled classes found.
          </div>
        )}

        <div style={{ height: 16 }}></div>
      </div>
    </>
  )
}
