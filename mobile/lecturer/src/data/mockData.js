export const LECTURER = { name: 'Dr. Tan Wei Liang', initials: 'TW', email: 'drtan.wl@um.edu.my', staffId: 'WL2019-0047', faculty: 'Computer Science & IT', role: 'Lecturer' }
export const CURRENT_CLASS = { code: 'WIA2005', name: 'Software Engineering', semester: 'Sem 2 2024/25', venue: 'DK 6, BLI Building', enrolled: 26 }
export const CLASSES = [{ code: 'WIA2005', name: 'Software Engineering', students: 26 }, { code: 'WIA2004', name: 'Data Mining', students: 31 }, { code: 'WIX3001', name: 'Final Year Project II', students: 18 }]
export const SESSIONS = [
  { id: 1, day: 24, month: 'May', week: 6, session: 1, time: '10:05 AM', duration: null, open: true, present: 22, absent: 3, unid: 1 },
  { id: 2, day: 21, month: 'May', week: 5, session: 2, time: '10:05 AM', duration: '110 min', open: false, present: 24, absent: 2, unid: 0 },
  { id: 3, day: 19, month: 'May', week: 5, session: 1, time: '8:00 AM',  duration: '110 min', open: false, present: 21, absent: 4, unid: 1 },
  { id: 4, day: 14, month: 'May', week: 4, session: 2, time: '10:05 AM', duration: '110 min', open: false, present: 25, absent: 1, unid: 0 },
  { id: 5, day: 12, month: 'May', week: 4, session: 1, time: '8:00 AM',  duration: '110 min', open: false, present: 23, absent: 3, unid: 0 },
  { id: 6, day: 7,  month: 'May', week: 3, session: 2, time: '10:05 AM', duration: '110 min', open: false, present: 20, absent: 6, unid: 0 },
]
export const STUDENTS = [
  { id: 'U2300124', name: 'Ahmad Izzul Hakim',   initials: 'AI', status: 'present' },
  { id: 'U2300207', name: 'Chow Shino',           initials: 'CS', status: 'present' },
  { id: 'U2300312', name: 'Farhana Binti Roslan', initials: 'FR', status: 'absent'  },
  { id: 'U2300445', name: 'Isyraf Danieal',        initials: 'ID', status: 'present' },
  { id: 'U2300521', name: 'Khor Jia Ling',         initials: 'KJ', status: 'present' },
  { id: 'U2300603', name: 'Lim Wei Hao',           initials: 'LW', status: 'unidentified' },
  { id: 'U2300718', name: 'Muhammad Haziq',        initials: 'MH', status: 'present' },
  { id: 'U2300829', name: 'Nazirul Asyraf',        initials: 'NA', status: 'absent'  },
  { id: 'U2300934', name: 'Nurul Amirah',          initials: 'NA', status: 'present' },
  { id: 'U2301047', name: 'Tan Ee Xuan',           initials: 'TX', status: 'present' },
  { id: 'U2301152', name: 'Yong Yew Sing',         initials: 'YY', status: 'present' },
  { id: 'U2301268', name: 'Zul Izzat Izzuddin',    initials: 'ZI', status: 'absent'  },
]
export const QUIZZES = [
  { id: 'q1', status: 'active',  question: 'Which software development model uses iterative development with fixed-length sprints?', options: ['Waterfall Model', 'Agile / Scrum', 'Spiral Model', 'V-Model'], correct: 1, time: '10:12 AM', timer: '30s', answered: 4, total: 5, pct: 80, distribution: [1, 3, 1, 0] },
  { id: 'q2', status: 'closed',  question: 'What does SOLID stand for in object-oriented design principles?', options: ['Single Responsibility...', 'Structured OO...', 'Scalable...', 'Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion'], correct: 3, time: '10:02 AM', timer: '60s', answered: 22, total: 25, correct_count: 18, wrong_count: 4, unanswered_count: 3, pct: 72, distribution: [4, 2, 2, 18] },
  { id: 'q3', status: 'draft',   question: 'Which UML diagram best represents the sequence of operations in a use case?', options: ['Class Diagram', 'Use Case Diagram', 'Sequence Diagram', 'Activity Diagram'], correct: 2, time: '9:55 AM', timer: null },
]
export const BREAKDOWN_ROWS = [
  { name: 'Ahmad Izzul Hakim',   answer: 'D', correct: true  },
  { name: 'Chow Shino',           answer: 'D', correct: true  },
  { name: 'Farhana Binti Roslan', answer: '—', correct: null  },
  { name: 'Isyraf Danieal',        answer: 'A', correct: false },
  { name: 'Khor Jia Ling',         answer: 'D', correct: true  },
  { name: 'Lim Wei Hao',           answer: 'B', correct: false },
  { name: 'Muhammad Haziq',        answer: 'D', correct: true  },
  { name: 'Nazirul Asyraf',        answer: '—', correct: null  },
  { name: 'Nurul Amirah',          answer: 'D', correct: true  },
  { name: 'Tan Ee Xuan',           answer: 'C', correct: false },
  { name: 'Yong Yew Sing',         answer: 'D', correct: true  },
  { name: 'Zul Izzat Izzuddin',    answer: '—', correct: null  },
]
export const SENSORS = { temperature: { value: '26.4', unit: '°C', status: 'Normal', warn: false }, humidity: { value: '61', unit: '%', status: 'Normal', warn: false }, co2: { value: '1240', unit: 'ppm', status: 'Elevated', warn: true }, light: { value: '420', unit: 'lux', status: 'Normal', warn: false }, occupancy: { value: '23', total: 30, status: 'Normal', warn: false } }
export const ANALYTICS_ATT_BARS = [66,78,90,80,96,85,88,100,74,84,88]
export const ANALYTICS_ATT_LABELS = ['W1S1','W1S2','W2S1','W2S2','W3S1','W3S2','W4S1','W4S2','W5S1','W5S2','Today']
export const ANALYTICS_PAR_BARS = [66,78,88,72,90,84]
export const ANALYTICS_PAR_LABELS = ['W1','W2','W3','W4','W5','Today']
export const AT_RISK = [
  { name: 'Farhana Binti Roslan', pct: '58.3%', color: 'red' },
  { name: 'Nazirul Asyraf',       pct: '66.7%', color: 'red' },
  { name: 'Zul Izzat Izzuddin',   pct: '75.0%', color: 'orange' },
]
