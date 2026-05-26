import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { LECTURER, CLASSES } from '../data/mockData'

export default function Profile() {
  const { goBack, openModal } = useLecturer()
  return (
    <div className="scroll-body">
      <StatusBar time="10:14" />
      <Topbar title="My Profile" onBack={goBack} />
      <div className="profile-hero">
        <div className="profile-avatar">{LECTURER.initials}</div>
        <div className="profile-name">{LECTURER.name}</div>
        <div className="profile-email">{LECTURER.email}</div>
        <div className="profile-role-badge"><i className="fa fa-chalkboard-teacher"></i> &nbsp;{LECTURER.role}</div>
      </div>

      <div className="profile-section">
        <div className="profile-section-label">Account Information</div>
        <div className="profile-row">
          {[
            { icon: 'fa-id-badge',   bg: 'var(--blue-lt)',   color: 'var(--blue)',   label: 'Staff ID',       value: LECTURER.staffId },
            { icon: 'fa-envelope',   bg: 'var(--blue-lt)',   color: 'var(--blue)',   label: 'Email Address',  value: LECTURER.email   },
            { icon: 'fa-university', bg: 'var(--green-lt)',  color: 'var(--green)',  label: 'Faculty',        value: LECTURER.faculty },
            { icon: 'fa-shield-alt', bg: 'var(--orange-lt)', color: 'var(--orange)', label: 'Role',           value: LECTURER.role    },
          ].map(f => (
            <div key={f.label} className="profile-field">
              <div className="pf-icon" style={{ background: f.bg, color: f.color }}><i className={`fa ${f.icon}`}></i></div>
              <div className="pf-content">
                <div className="pf-label">{f.label}</div>
                <div className="pf-value">{f.value}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="profile-admin-note">
          <i className="fa fa-info-circle"></i>
          <span>Profile details are managed by your system administrator. Contact IT Services to update your name, email, or faculty.</span>
        </div>
      </div>

      <div className="profile-section">
        <div className="profile-section-label">Assigned Classes — Sem 2 2024/25</div>
        <div className="profile-row">
          {CLASSES.map(c => (
            <div key={c.code} className="profile-field">
              <div className="pf-icon" style={{ background: 'var(--blue-lt)', color: 'var(--blue)' }}><i className="fa fa-book"></i></div>
              <div className="pf-content">
                <div className="pf-label">{c.code}</div>
                <div className="pf-value">{c.name}</div>
              </div>
              <span className="badge blue" style={{ fontSize: 10 }}>{c.students} students</span>
            </div>
          ))}
        </div>
      </div>

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
