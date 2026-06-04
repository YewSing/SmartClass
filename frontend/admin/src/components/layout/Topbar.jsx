import { useAdmin } from '../../context/AdminContext'

const META = {
  dashboard:  { title: 'DASHBOARD',        path: 'Overview' },
  users:      { title: 'USER MANAGEMENT',  path: 'User Management / All Users' },
  students:   { title: 'STUDENTS',         path: 'User Management / Students' },
  lecturers:  { title: 'LECTURERS',        path: 'User Management / Lecturers' },
  enrollment: { title: 'CLASS ENROLLMENT', path: 'Enrollment / Class Assignment' },
  facedata:   { title: 'FACE DATA',        path: 'Enrollment / Face Data' },
  audit:      { title: 'AUDIT LOG',        path: 'System / Audit Log' },
}

export default function Topbar() {
  const { state } = useAdmin()
  const meta = META[state.currentView] ?? { title: state.currentView.toUpperCase(), path: '' }

  return (
    <div className="h-14 border-b border-border flex items-center px-7 gap-4 bg-surface flex-shrink-0">
      <div>
        <div className="font-sans text-[13px] font-bold text-text1 tracking-[0.03em]">{meta.title}</div>
        <div className="text-[12px] text-text3">
          Admin Panel <span className="text-text2">/ {meta.path}</span>
        </div>
      </div>
    </div>
  )
}
