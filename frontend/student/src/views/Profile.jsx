import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import { STUDENT, ENROLLED_CLASSES } from '../data/mockData'

const CLASS_ICONS = {
  WIA2005: { bg: 'var(--student-accent-lt)', icon: 'fa-book-open',     color: 'var(--student-accent)' },
  WIA2004: { bg: 'var(--purple-lt)',          icon: 'fa-database',      color: 'var(--purple)'         },
  WIA2003: { bg: 'var(--red-lt)',             icon: 'fa-network-wired', color: 'var(--red)'            },
  WIX2001: { bg: 'var(--green-lt)',           icon: 'fa-shield-alt',    color: 'var(--green)'          },
}

export default function Profile() {
  const { openModal } = useStudent()

  return (
    <>
      <StatusBar time="10:14" />
      <div style={{ padding: '12px 16px 10px', background: 'var(--card)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)' }}>My Profile</div>
        <div style={{ fontSize: 12, color: 'var(--text-sub)', marginTop: 2 }}>Student Portal · University of Malaya</div>
      </div>

      <div className="scroll-body">
        <div className="profile-hero">
          <div className="profile-avatar">{STUDENT.initials}</div>
          <div className="profile-name">{STUDENT.name}</div>
          <div className="profile-email">{STUDENT.email}</div>
          <div className="profile-role-badge">STUDENT</div>
        </div>

        <div className="profile-section">
          <div className="profile-section-label">Account Details</div>
          <div className="profile-row">
            {[
              { bg: 'var(--student-accent-lt)', icon: 'fa-id-card',     color: 'var(--student-accent)', label: 'Matric Number',   value: STUDENT.matricNo   },
              { bg: 'var(--green-lt)',           icon: 'fa-graduation-cap', color: 'var(--green)',        label: 'Programme',      value: STUDENT.programme  },
              { bg: 'var(--yellow-lt)',          icon: 'fa-university',  color: 'var(--yellow)',         label: 'Faculty',        value: STUDENT.faculty    },
              { bg: 'var(--orange-lt)',          icon: 'fa-layer-group', color: 'var(--orange)',         label: 'Year / Semester', value: STUDENT.yearSem   },
            ].map(f => (
              <div key={f.label} className="profile-field">
                <div className="pf-icon" style={{ background: f.bg }}>
                  <i className={`fa ${f.icon}`} style={{ color: f.color }}></i>
                </div>
                <div className="pf-content">
                  <div className="pf-label">{f.label}</div>
                  <div className="pf-value">{f.value}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="profile-section-label">Enrolled Classes</div>
          <div className="profile-row">
            {ENROLLED_CLASSES.map(cls => {
              const ic = CLASS_ICONS[cls.code] ?? { bg: 'var(--gray-100)', icon: 'fa-book', color: 'var(--gray-500)' }
              return (
                <div key={cls.code} className="profile-field">
                  <div className="pf-icon" style={{ background: ic.bg }}>
                    <i className={`fa ${ic.icon}`} style={{ color: ic.color }}></i>
                  </div>
                  <div className="pf-content">
                    <div className="pf-label">{cls.code} · {cls.name}</div>
                    <div className="pf-value" style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-sub)', marginTop: 2 }}>
                      {cls.lecturer} &nbsp;·&nbsp; {cls.venue}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="profile-section-label">Settings</div>
          <div className="profile-row">
            <div className="profile-action-row">
              <div className="pf-icon" style={{ background: 'var(--gray-100)' }}>
                <i className="fa fa-bell" style={{ color: 'var(--gray-500)' }}></i>
              </div>
              <div className="pf-label-main">Notifications</div>
              <div className="pf-chevron"><i className="fa fa-chevron-right"></i></div>
            </div>
            <div className="profile-action-row danger" onClick={() => openModal('signout')}>
              <div className="pf-icon" style={{ background: 'var(--red-lt)' }}>
                <i className="fa fa-sign-out-alt" style={{ color: 'var(--red)' }}></i>
              </div>
              <div className="pf-label-main">Sign Out</div>
              <div className="pf-chevron"><i className="fa fa-chevron-right"></i></div>
            </div>
          </div>
        </div>

        <div style={{ margin: '0 16px 8px', background: 'var(--gray-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <i className="fa fa-info-circle" style={{ color: 'var(--text-hint)', fontSize: 13, marginTop: 1 }}></i>
          <span style={{ fontSize: 12, color: 'var(--text-sub)', lineHeight: 1.5 }}>
            To update your profile details or face enrolment data, contact your faculty administrator.
          </span>
        </div>
        <div style={{ height: 20 }}></div>
      </div>
    </>
  )
}
