import { useEffect } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'

export default function Profile() {
  const { state, goBack, openModal, loadAllClasses } = useLecturer()
  const { lecturer, allClasses } = state

  useEffect(() => { loadAllClasses() }, [loadAllClasses])

  // Group occurrences by course code
  const courseMap = {}
  for (const c of allClasses) {
    if (!courseMap[c.code]) courseMap[c.code] = { name: c.name, occs: [] }
    courseMap[c.code].occs.push(c)
  }
  const courses = Object.entries(courseMap)

  const initials = lecturer?.initials ?? '??'

  return (
    <div className="scroll-body">
      <StatusBar time="10:14" />
      <Topbar title="My Profile" onBack={goBack} />

      {/* Hero */}
      <div className="profile-hero">
        <div className="profile-avatar">{initials}</div>
        <div className="profile-name">{lecturer?.name ?? '—'}</div>
        <div className="profile-email">{lecturer?.email ?? '—'}</div>
        <div className="profile-role-badge"><i className="fa fa-chalkboard-teacher"></i> &nbsp;Lecturer</div>
      </div>

      {/* Account info */}
      <div className="profile-section">
        <div className="profile-section-label">Account Information</div>
        <div className="profile-row">
          {[
            { icon: 'fa-id-badge',   bg: 'var(--blue-lt)',   color: 'var(--blue)',    label: 'Staff ID',   value: lecturer?.staffId  },
            { icon: 'fa-envelope',   bg: 'var(--blue-lt)',   color: 'var(--blue)',    label: 'Email',      value: lecturer?.email    },
            { icon: 'fa-university', bg: 'var(--green-lt)',  color: 'var(--green)',   label: 'Department', value: lecturer?.faculty  },
            { icon: 'fa-shield-alt', bg: 'var(--orange-lt)', color: 'var(--orange)',  label: 'Role',       value: 'Lecturer'         },
          ].map(f => (
            <div key={f.label} className="profile-field">
              <div className="pf-icon" style={{ background: f.bg, color: f.color }}><i className={`fa ${f.icon}`}></i></div>
              <div className="pf-content">
                <div className="pf-label">{f.label}</div>
                <div className="pf-value">{f.value ?? '—'}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="profile-admin-note">
          <i className="fa fa-info-circle"></i>
          <span>Profile details are managed by your system administrator. Contact IT Services to update your name, email, or department.</span>
        </div>
      </div>

      {/* Assigned classes */}
      <div className="profile-section">
        <div className="profile-section-label">Assigned Classes — Current Semester</div>
        <div className="profile-row">
          {courses.length === 0 ? (
            <div className="profile-field">
              <div className="pf-content">
                <div className="pf-value" style={{ color: 'var(--text-hint)', fontSize: 13 }}>No classes assigned</div>
              </div>
            </div>
          ) : courses.map(([code, { name, occs }]) => (
            <div key={code} className="profile-field" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 0 }}>
              {/* Course header row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div className="pf-icon" style={{ background: 'var(--blue-lt)', color: 'var(--blue)', flexShrink: 0 }}>
                  <i className="fa fa-book"></i>
                </div>
                <div className="pf-content">
                  <div className="pf-label">{code}</div>
                  <div className="pf-value">{name}</div>
                </div>
              </div>
              {/* Occurrence rows */}
              <div style={{ paddingLeft: 44, marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {occs.map(o => (
                  <div key={o.id} style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span
                      className={`badge ${o.type === 'LECTURE' ? 'blue' : 'green'}`}
                      style={{ fontSize: 9, padding: '1px 6px' }}
                    >
                      {o.type === 'LECTURE' ? 'Lec' : (o.label ?? 'Tut')}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-sub)' }}>
                      {o.day_of_week} {o.start_time}–{o.end_time}
                      {o.room ? ` · ${o.room}` : ''}
                    </span>
                    <span className="badge gray" style={{ fontSize: 9, padding: '1px 6px', marginLeft: 'auto' }}>
                      {o.enrolled_count} students
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Account actions */}
      <div className="profile-section">
        <div className="profile-section-label">Account</div>
        <div className="profile-row">
          {[
            { icon: 'fa-lock',         bg: 'var(--yellow-lt)', color: 'var(--yellow-dk)', label: 'Change Password',         type: 'change-password', danger: false },
            { icon: 'fa-clock',        bg: 'var(--green-lt)',  color: 'var(--green-dk)',  label: 'Session & Login Activity', type: 'session-info',    danger: false },
            { icon: 'fa-sign-out-alt', bg: 'var(--red-lt)',    color: 'var(--red)',        label: 'Sign Out',                 type: 'signout',         danger: true  },
          ].map(a => (
            <div key={a.type} className={`profile-action-row${a.danger ? ' danger' : ''}`} onClick={() => openModal(a.type)}>
              <div className="pf-icon" style={{ background: a.bg, color: a.color }}><i className={`fa ${a.icon}`}></i></div>
              <span className="pf-label-main">{a.label}</span>
              <i className="fa fa-chevron-right pf-chevron"></i>
            </div>
          ))}
        </div>
      </div>

      <div style={{ textAlign: 'center', padding: '8px 0 28px', fontSize: 11, color: 'var(--text-hint)' }}>
        SmartClass Lecturer App &nbsp;·&nbsp; v1.0.0 &nbsp;·&nbsp; University of Malaya
      </div>
    </div>
  )
}
