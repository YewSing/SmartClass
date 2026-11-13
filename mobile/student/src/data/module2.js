// Module 2 / 5 / 6 / 7 — frontend-only fixtures.
// No backend wiring yet (Modules 2/5/6/7 are backend-pending); these mocks
// mirror the agreed interfaces so the UI flow can be reviewed.

export const PRIORITIES = { urgent: 0, important: 1, general: 2 }

// FR-205..FR-208 — notification feed, ordered by priority then time.
export const NOTIFICATIONS = [
  {
    id: 'n1', priority: 'urgent', event: 'attendance.recorded',
    title: 'Attendance recorded',
    body: 'Your attendance for WIF3001 — Lecture 12 has been recorded as Present.',
    time: '2 min ago', course: 'WIF3001', read: false, icon: 'checkmark-circle',
  },
  {
    id: 'n2', priority: 'urgent', event: 'face_enrolment.result',
    title: 'Face enrolment approved',
    body: 'Your face enrolment was approved automatically. You can now use face attendance.',
    time: '1 hr ago', course: null, read: false, icon: 'person-circle',
  },
  {
    id: 'n3', priority: 'important', event: 'quiz.deadline',
    title: 'Quiz closing soon',
    body: '"Sprint Planning Basics" closes today at 11:59 PM. You have not attempted it yet.',
    time: '3 hrs ago', course: 'WIF3001', read: false, icon: 'alarm',
  },
  {
    id: 'n4', priority: 'important', event: 'quiz.published',
    title: 'New quiz published',
    body: 'Dr. Tan published "Normalization Rules" (10 MCQ · 20 min). Opens now.',
    time: 'Yesterday', course: 'WIA2004', read: true, icon: 'document-text',
  },
  {
    id: 'n5', priority: 'general', event: 'announcement',
    title: 'Class venue change',
    body: 'Next Tuesday\'s WIA2005 lecture moves to DK 3.',
    time: 'Yesterday', course: 'WIA2005', read: true, icon: 'megaphone',
  },
  {
    id: 'n6', priority: 'general', event: 'announcement',
    title: 'Materials updated',
    body: 'New slides uploaded for Week 12 — Graph Traversal.',
    time: '2 days ago', course: 'WIA2004', read: true, icon: 'folder-open',
  },
]

// FR-201 — upcoming quiz/assessment deadlines on the dashboard.
export const DEADLINES = [
  { id: 'd1', course: 'WIF3001', title: 'Sprint Planning Basics', due: 'Today · 11:59 PM', questions: '10 MCQ', urgency: 'today' },
  { id: 'd2', course: 'WIA2004', title: 'Normalization Rules', due: 'Fri · 5:00 PM', questions: '8 MCQ · 2 SA', urgency: 'soon' },
  { id: 'd3', course: 'WIA2005', title: 'UML & Design Patterns', due: 'Next Mon · 11:59 PM', questions: '15 MCQ', urgency: 'later' },
]

// FR-201 — latest announcements.
export const ANNOUNCEMENTS = [
  { id: 'a1', course: 'WIA2005', title: 'Class venue change', body: 'Tuesday lecture moves to DK 3.', time: 'Yesterday' },
  { id: 'a2', course: 'WIA2004', title: 'Week 12 slides uploaded', body: 'Graph Traversal materials are now on Moodle.', time: '2 days ago' },
]

// FR-201 — ongoing classroom activities (Module 5 live session).
export const LIVE_ACTIVITY = {
  open: true,
  course: 'WIF3001 — Software Engineering',
  lecturer: 'Dr. Tan Wei Liang',
  room: 'DK 6',
  poll: { question: 'Which practice improves code quality the most?', voted: false, options: ['Pair programming', 'Code review', 'Unit testing', 'Refactoring'] },
}

// FR-706 — the student's own engagement & performance indicators.
export const MY_PROGRESS = {
  overall: [
    { label: 'Attendance rate', value: '84%', tint: 'good' },
    { label: 'Class participation', value: 'High', tint: 'good' },
    { label: 'Avg quiz score', value: '72%', tint: 'warn' },
    { label: 'At-risk flags', value: 'None', tint: 'good' },
  ],
  courses: [
    {
      code: 'WIF3001', name: 'Software Engineering',
      attendance: { rate: 92, present: 11, total: 12 },
      participation: { questions: 6, idu: 2, polls: 9, trend: 'up' },
      quizzes: [{ title: 'Agile Basics', score: 80, trend: 'up' }, { title: 'Scrum Roles', score: 70, trend: 'same' }],
      trend: [70, 72, 75, 80],
    },
    {
      code: 'WIA2004', name: 'Data Mining',
      attendance: { rate: 75, present: 9, total: 12 },
      participation: { questions: 3, idu: 4, polls: 5, trend: 'down' },
      quizzes: [{ title: 'Clustering', score: 55, trend: 'down' }, { title: 'Classification', score: 48, trend: 'down' }],
      flag: { condition: 'Quiz scores declined across the last 2 quizzes', level: 'warning' },
      trend: [68, 62, 55, 48],
    },
    {
      code: 'WIA2005', name: 'Web Programming',
      attendance: { rate: 86, present: 6, total: 7 },
      participation: { questions: 4, idu: 1, polls: 7, trend: 'up' },
      quizzes: [{ title: 'JavaScript DOM', score: 90, trend: 'up' }],
      trend: [80, 84, 88, 90],
    },
  ],
}
