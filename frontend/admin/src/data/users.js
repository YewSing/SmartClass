export const CLASS_META = {
  WIA2005: { name: 'Software Engineering', lecturer: 'Dr. Amirul Hakim' },
  WIA2004: { name: 'Algorithm Design', lecturer: 'Dr. Lee Siew Lin' },
  WIA2006: { name: 'Database Systems', lecturer: 'Dr. Lee Siew Lin' },
  WIA3001: { name: 'AI Fundamentals', lecturer: 'Dr. Amirul Hakim' },
}

export const ALL_CLASSES = Object.keys(CLASS_META)

export const INITIAL_USERS = [
  { id: 'U2024001', name: 'Nurul Ain binti Razak',  role: 'Student',  email: 'u2024001@siswa.um.edu.my', phone: '+60112345678', status: 'Active',   face: true,  faceDate: '2025-05-26', faceSamples: 5, classes: ['WIA2005', 'WIA2004'], dept: 'FCSIT',      color: '#4f8ef7' },
  { id: 'U2024002', name: 'Lim Wei Xian',            role: 'Student',  email: 'u2024002@siswa.um.edu.my', phone: '+60198765432', status: 'Active',   face: true,  faceDate: '2025-05-20', faceSamples: 5, classes: ['WIA2005', 'WIA2006'], dept: 'FCSIT',      color: '#34d399' },
  { id: 'U2024003', name: 'Ahmad Fariz bin Hassan',  role: 'Student',  email: 'u2024003@siswa.um.edu.my', phone: '+60167891234', status: 'Active',   face: false, faceDate: null,         faceSamples: 0, classes: ['WIA2005'],           dept: 'FCSIT',      color: '#fb923c' },
  { id: 'U2024004', name: 'Priya Navaratnam',        role: 'Student',  email: 'u2024004@siswa.um.edu.my', phone: '+60134567890', status: 'Active',   face: true,  faceDate: '2025-05-18', faceSamples: 5, classes: ['WIA2004', 'WIA3001'], dept: 'FCSIT',      color: '#f472b6' },
  { id: 'U2024005', name: 'Tan Jia Yi',              role: 'Student',  email: 'u2024005@siswa.um.edu.my', phone: '+60156789012', status: 'Active',   face: false, faceDate: null,         faceSamples: 0, classes: ['WIA2006'],           dept: 'FCSIT',      color: '#a78bfa' },
  { id: 'U2024006', name: 'Muhammad Haziq Zulkifli', role: 'Student',  email: 'u2024006@siswa.um.edu.my', phone: '+60173456789', status: 'Active',   face: false, faceDate: null,         faceSamples: 0, classes: ['WIA2005', 'WIA3001'], dept: 'FCSIT',      color: '#60a5fa' },
  { id: 'U2024007', name: 'Siti Hajar binti Mohd',   role: 'Student',  email: 'u2024007@siswa.um.edu.my', phone: '+60189012345', status: 'Active',   face: true,  faceDate: '2025-05-15', faceSamples: 5, classes: ['WIA2005'],           dept: 'FCSIT',      color: '#f87171' },
  { id: 'U2024008', name: 'Kelvin Ong Beng Huat',    role: 'Student',  email: 'u2024008@siswa.um.edu.my', phone: '+60121234567', status: 'Inactive', face: true,  faceDate: '2025-04-10', faceSamples: 5, classes: [],                   dept: 'FCSIT',      color: '#94a3b8' },
  { id: 'S1001',    name: 'Dr. Amirul Hakim',        role: 'Lecturer', email: 'amirul@um.edu.my',          phone: '+60312345678', status: 'Active',   face: false, faceDate: null,         faceSamples: 0, classes: ['WIA2005', 'WIA3001'], dept: 'Dept. of SE', color: '#7b5cf5' },
  { id: 'S1002',    name: 'Dr. Lee Siew Lin',        role: 'Lecturer', email: 'siewlin@um.edu.my',         phone: '+60323456789', status: 'Active',   face: false, faceDate: null,         faceSamples: 0, classes: ['WIA2004', 'WIA2006'], dept: 'Dept. of AI', color: '#7b5cf5' },
  { id: 'ADM01',    name: 'Admin User',              role: 'Admin',    email: 'admin@um.edu.my',           phone: '+60312345000', status: 'Active',   face: false, faceDate: null,         faceSamples: 0, classes: [],                   dept: 'FCSIT Admin', color: '#fbbf24' },
]

export const AUDIT_LOG = [
  { ts: '2025-05-26 09:14:33', actor: 'admin@um.edu.my', action: 'FACE_ENROLL',    target: 'U2024001', detail: '5 samples captured, embedding stored' },
  { ts: '2025-05-26 08:50:21', actor: 'admin@um.edu.my', action: 'USER_CREATE',    target: 'U2024047', detail: 'Role: Student, Class: WIA2005' },
  { ts: '2025-05-25 16:30:55', actor: 'admin@um.edu.my', action: 'ENROLL_UPDATE',  target: 'U2024032', detail: 'Added WIA2006, removed WIA2004' },
  { ts: '2025-05-25 14:10:02', actor: 'admin@um.edu.my', action: 'USER_DEACTIVATE',target: 'U2023089', detail: 'Graduated — account archived' },
  { ts: '2025-05-24 11:22:40', actor: 'admin@um.edu.my', action: 'FACE_REMOVE',    target: 'U2024015', detail: 'Previous embedding removed before re-enroll' },
  { ts: '2025-05-24 09:05:17', actor: 'admin@um.edu.my', action: 'USER_UPDATE',    target: 'U2022034', detail: 'Contact info updated' },
]

export const AVATAR_COLORS = ['#4f8ef7', '#34d399', '#f472b6', '#a78bfa', '#60a5fa']
