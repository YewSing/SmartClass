import { useStudent } from '../context/StudentContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'

export default function AttReportStatus() {
  const { navigate } = useStudent()

  return (
    <>
      <StatusBar time="10:10" />
      <Topbar title="Report Status" sub="Lec 8 · WIA2005" onBack={() => navigate('attendance')} />
      <div className="scroll-body">
        <div className="report-status-hero">
          <div className="report-status-icon" style={{ background: 'var(--yellow-lt)' }}>
            <i className="fa fa-hourglass-half" style={{ color: 'var(--yellow)' }}></i>
          </div>
          <div className="report-status-label">Under Review</div>
          <div className="report-status-sub">Your report has been received and is awaiting review by your lecturer.</div>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-label">Report Details</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              { label: 'Session',   value: 'Lec 8 — Requirements Eng.' },
              { label: 'Date',      value: '29 Apr 2025' },
              { label: 'Reason',    value: 'Face recognition did not detect me' },
              { label: 'Submitted', value: '25 May 2025, 10:10 AM' },
            ].map(row => (
              <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12, color: 'var(--text-sub)' }}>{row.label}</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', textAlign: 'right', maxWidth: '60%' }}>{row.value}</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'var(--text-sub)' }}>Ref. No.</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-hint)', fontFamily: 'var(--font-mono)' }}>RPT-2025-04290012</span>
            </div>
          </div>
        </div>

        <div className="section-header"><span className="section-title">Progress</span></div>
        <div className="report-timeline" style={{ paddingBottom: 8 }}>
          <div className="report-timeline-item">
            <div className="rt-dot done"><i className="fa fa-check"></i></div>
            <div className="rt-content">
              <div className="rt-title">Report Submitted</div>
              <div className="rt-time">25 May 2025 · 10:10 AM</div>
            </div>
          </div>
          <div className="report-timeline-item">
            <div className="rt-dot pending"><i className="fa fa-clock"></i></div>
            <div className="rt-content">
              <div className="rt-title">Under Review</div>
              <div className="rt-time">Pending · Awaiting lecturer action</div>
              <div className="rt-note">Your report has been forwarded to Dr. Tan Wei Lin for review. You will be notified once a decision is made.</div>
            </div>
          </div>
          <div className="report-timeline-item">
            <div className="rt-dot inactive"><i className="fa fa-check-double"></i></div>
            <div className="rt-content" style={{ opacity: .45 }}>
              <div className="rt-title">Resolved</div>
              <div className="rt-time">Awaiting review completion</div>
            </div>
          </div>
        </div>

        <div style={{ margin: '4px 16px 16px', background: 'var(--gray-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', display: 'flex', gap: 8 }}>
          <i className="fa fa-info-circle" style={{ color: 'var(--text-hint)', fontSize: 13, marginTop: 1 }}></i>
          <span style={{ fontSize: 12, color: 'var(--text-sub)', lineHeight: 1.5 }}>
            Resolution typically takes 1–3 business days. Your attendance status will be updated automatically if the report is approved.
          </span>
        </div>
        <div style={{ height: 16 }}></div>
      </div>
    </>
  )
}
