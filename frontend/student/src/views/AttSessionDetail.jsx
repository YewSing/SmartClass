import { useState } from 'react'
import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'

const VARIANT_CONFIG = {
  present: {
    rowBg: 'var(--green-lt)', rowBorder: '#9DE8C5',
    iconBg: 'var(--green)', icon: 'fa-check', iconColor: '#fff',
    labelColor: 'var(--green-dk)', statusLabel: 'Present',
    checkinBg: 'var(--green-lt)', checkinIcon: 'fa-sign-in-alt', checkinIconColor: 'var(--green)',
    checkinValueColor: 'var(--green-dk)',
    infoBox: null,
  },
  late: {
    rowBg: 'var(--orange-lt)', rowBorder: '#F7C8A0',
    iconBg: 'var(--orange)', icon: 'fa-clock', iconColor: '#fff',
    labelColor: 'var(--orange-dk)', statusLabel: 'Late',
    checkinBg: 'var(--orange-lt)', checkinIcon: 'fa-sign-in-alt', checkinIconColor: 'var(--orange)',
    checkinValueColor: 'var(--orange-dk)',
    infoBox: {
      bg: 'var(--orange-lt)', border: '1px solid #F7C8A0',
      icon: 'fa-info-circle', iconColor: 'var(--orange)',
      textColor: 'var(--orange-dk)',
      text: 'You were detected 17 minutes after the session opened. Late arrival is recorded but still counts toward attendance.',
    },
  },
  absent: {
    rowBg: 'var(--red-lt)', rowBorder: '#f5c5c5',
    iconBg: 'var(--red)', icon: 'fa-times', iconColor: '#fff',
    labelColor: 'var(--red-dk)', statusLabel: 'Absent',
    checkinBg: 'var(--red-lt)', checkinIcon: 'fa-sign-in-alt', checkinIconColor: 'var(--red)',
    checkinValueColor: 'var(--red-dk)',
    infoBox: {
      bg: 'var(--red-lt)', border: '1px solid #f5c5c5',
      icon: 'fa-exclamation-circle', iconColor: 'var(--red)',
      textColor: 'var(--red-dk)',
      text: 'No face detection event was recorded for this session. If you believe this is an error, contact your lecturer.',
    },
  },
  unid: {
    rowBg: 'var(--orange-lt)', rowBorder: '#F7C8A0',
    iconBg: 'var(--orange)', icon: 'fa-question', iconColor: '#fff',
    labelColor: 'var(--orange-dk)', statusLabel: 'Unidentified',
    checkinBg: null, checkinIcon: null, checkinIconColor: null,
    checkinValueColor: null,
    infoBox: null,
  },
}

const REPORT_REASONS = [
  { id: 'present',      label: 'I was physically present in class' },
  { id: 'no-detect',    label: 'Face recognition did not detect me' },
  { id: 'obstruction',  label: 'I had a seating obstruction (hat/glasses)' },
  { id: 'other',        label: 'Other' },
]

export default function AttSessionDetail() {
  const { state, goBack, navigate } = useStudent()
  const { navData } = state
  const variant = navData?.variant ?? 'present'
  const detail  = navData?.session ?? {}
  const cfg = VARIANT_CONFIG[variant] ?? VARIANT_CONFIG.present

  const [selectedReason, setSelectedReason] = useState('present')

  return (
    <>
      <StatusBar time="10:09" />
      <Topbar title="Session Detail" sub={`WIA2005 · Software Engineering`} onBack={goBack} />
      <div className="scroll-body">
        <div className="sess-detail-hero">
          <div className="sess-detail-title">{detail.title}</div>
          <div className="sess-detail-meta">{detail.meta}</div>

          <div className="sess-detail-status-row" style={{ marginTop: 14, background: cfg.rowBg, borderColor: cfg.rowBorder }}>
            <div className="sess-detail-status-icon" style={{ background: cfg.iconBg }}>
              <i className={`fa ${cfg.icon}`} style={{ color: cfg.iconColor, fontSize: 18 }}></i>
            </div>
            <div className="sess-detail-status-info">
              <div className="label" style={{ color: cfg.labelColor }}>Your Status</div>
              <div className="val" style={{ color: cfg.labelColor }}>{cfg.statusLabel}</div>
            </div>
            {detail.isLive && (
              <div className="live-chip" style={{ marginLeft: 'auto' }}>
                <div className="live-dot"></div>Live Now
              </div>
            )}
          </div>
        </div>

        {variant === 'unid' && (
          <div style={{ margin: '12px 16px 0', background: 'var(--orange-lt)', border: '1px solid #F7C8A0', borderRadius: 'var(--radius-sm)', padding: '10px 14px', display: 'flex', gap: 8 }}>
            <i className="fa fa-exclamation-triangle" style={{ color: 'var(--orange)', marginTop: 1, flexShrink: 0 }}></i>
            <span style={{ fontSize: 12, color: 'var(--orange-dk)', lineHeight: 1.5 }}>
              Face detection picked up your presence but could not confidently match your identity. Submit a report to have your lecturer manually verify this session.
            </span>
          </div>
        )}

        <div className="section-header" style={{ paddingTop: 14 }}>
          <span className="section-title">Session Info</span>
        </div>
        <div style={{ background: 'var(--card)', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
          <div className="sess-info-row">
            <div className="sess-info-icon" style={{ background: 'var(--student-accent-lt)' }}>
              <i className="fa fa-clock" style={{ color: 'var(--student-accent)' }}></i>
            </div>
            <div className="sess-info-content">
              <div className="lbl">Session Time</div>
              <div className="val">{detail.sessionTime}</div>
            </div>
          </div>

          {(variant === 'present' || variant === 'late') && detail.checkinTime && (
            <div className="sess-info-row">
              <div className="sess-info-icon" style={{ background: cfg.checkinBg }}>
                <i className={`fa ${cfg.checkinIcon}`} style={{ color: cfg.checkinIconColor }}></i>
              </div>
              <div className="sess-info-content">
                <div className="lbl">Your Check-in Time</div>
                <div className="val" style={{ color: cfg.checkinValueColor, fontWeight: 700 }}>
                  {detail.checkinTime}&nbsp;
                  <span style={{ fontSize: 12, fontWeight: 600 }}>{detail.checkinNote}</span>
                </div>
              </div>
            </div>
          )}

          {variant === 'absent' && (
            <div className="sess-info-row">
              <div className="sess-info-icon" style={{ background: 'var(--red-lt)' }}>
                <i className="fa fa-sign-in-alt" style={{ color: 'var(--red)' }}></i>
              </div>
              <div className="sess-info-content">
                <div className="lbl">Your Check-in Time</div>
                <div className="val" style={{ color: 'var(--red-dk)' }}>Not detected</div>
              </div>
            </div>
          )}

          <div className="sess-info-row">
            <div className="sess-info-icon" style={{ background: 'var(--gray-100)' }}>
              <i className="fa fa-map-marker-alt" style={{ color: 'var(--gray-500)' }}></i>
            </div>
            <div className="sess-info-content">
              <div className="lbl">Venue</div>
              <div className="val">{detail.venue}</div>
            </div>
          </div>
          <div className="sess-info-row" style={{ borderBottom: 'none' }}>
            <div className="sess-info-icon" style={{ background: 'var(--gray-100)' }}>
              <i className="fa fa-user" style={{ color: 'var(--gray-500)' }}></i>
            </div>
            <div className="sess-info-content">
              <div className="lbl">Lecturer</div>
              <div className="val">{detail.lecturer}</div>
            </div>
          </div>
        </div>

        {cfg.infoBox && (
          <div style={{ margin: '12px 16px', background: cfg.infoBox.bg, border: cfg.infoBox.border, borderRadius: 'var(--radius-sm)', padding: '10px 14px', display: 'flex', gap: 8 }}>
            <i className={`fa ${cfg.infoBox.icon}`} style={{ color: cfg.infoBox.iconColor, marginTop: 1, flexShrink: 0 }}></i>
            <span style={{ fontSize: 12, color: cfg.infoBox.textColor, lineHeight: 1.5 }}>{cfg.infoBox.text}</span>
          </div>
        )}

        {(variant === 'present' || variant === 'late') && detail.classPresent != null && (
          <>
            <div className="section-header" style={{ paddingTop: 14 }}>
              <span className="section-title">Class Attendance</span>
            </div>
            <div style={{ background: 'var(--card)', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
              <div className="sess-info-row">
                <div className="sess-info-icon" style={{ background: 'var(--green-lt)' }}>
                  <i className="fa fa-users" style={{ color: 'var(--green)' }}></i>
                </div>
                <div className="sess-info-content"><div className="lbl">Present</div><div className="val">{detail.classPresent} students</div></div>
              </div>
              <div className="sess-info-row">
                <div className="sess-info-icon" style={{ background: 'var(--red-lt)' }}>
                  <i className="fa fa-user-times" style={{ color: 'var(--red)' }}></i>
                </div>
                <div className="sess-info-content"><div className="lbl">Absent</div><div className="val">{detail.classAbsent} students</div></div>
              </div>
              <div className="sess-info-row" style={{ borderBottom: 'none' }}>
                <div className="sess-info-icon" style={{ background: 'var(--orange-lt)' }}>
                  <i className="fa fa-question-circle" style={{ color: 'var(--orange)' }}></i>
                </div>
                <div className="sess-info-content"><div className="lbl">Unidentified</div><div className="val">{detail.classUnid} student</div></div>
              </div>
            </div>
          </>
        )}

        {variant === 'unid' && (
          <>
            <div className="section-header" style={{ paddingTop: 14 }}>
              <span className="section-title">Report This Session</span>
            </div>
            <div style={{ margin: '0 16px 12px' }}>
              <div style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 12, lineHeight: 1.5 }}>
                Your attendance was marked as <strong style={{ color: 'var(--orange-dk)' }}>Unidentified</strong>. Select the reason for your report:
              </div>
              {REPORT_REASONS.map(r => (
                <div
                  key={r.id}
                  className={`report-reason-option${selectedReason === r.id ? ' selected' : ''}`}
                  onClick={() => setSelectedReason(r.id)}
                >
                  <div className="rr-radio"></div>
                  <div className="rr-text">{r.label}</div>
                </div>
              ))}
              <div className="form-group" style={{ marginTop: 10 }}>
                <label className="form-label">Additional notes (optional)</label>
                <textarea rows={3} placeholder="Describe the situation…"></textarea>
              </div>
              <button
                className="btn btn-full"
                style={{ background: 'var(--orange)', color: '#fff', padding: 13 }}
                onClick={() => navigate('att-report-status')}
              >
                <i className="fa fa-flag"></i> Submit Report
              </button>
            </div>
          </>
        )}

        <div style={{ height: 24 }}></div>
      </div>
    </>
  )
}
