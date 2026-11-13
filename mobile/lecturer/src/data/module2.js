// Module 2 / 5 / 6 / 7 — lecturer-side frontend-only fixtures.
// No backend wiring yet; these mirror the agreed interfaces so the UI flow
// can be reviewed and replaced by API calls later.

export const PRIORITIES = { urgent: 0, important: 1, general: 2 }

// FR-205..FR-208 — lecturer notification feed (incl. FR-210 at-risk alerts,
// FR-212 face-review notifications).
export const NOTIFICATIONS = [
  {
    id: 'n1', priority: 'important', event: 'risk.flagged',
    title: 'At-risk student flagged',
    body: 'Farhana Binti Roslan (WIF3001): attendance rate fell below 80%.',
    time: '5 min ago', course: 'WIF3001', read: false, icon: 'warning',
  },
  {
    id: 'n2', priority: 'important', event: 'face_enrolment.pending_review',
    title: 'Face enrolment needs review',
    body: '1 submission failed automatic verification and needs your review.',
    time: '32 min ago', course: 'WIA2004', read: false, icon: 'person-circle',
  },
  {
    id: 'n3', priority: 'important', event: 'face.unrecognised',
    title: 'Unrecognised face at DK 6',
    body: 'A face at the entrance could not be matched. Assign it or dismiss it.',
    time: '1 hr ago', course: 'WIF3001', read: false, icon: 'scan-outline',
  },
  {
    id: 'n4', priority: 'important', event: 'quiz.submitted',
    title: 'Short answers to grade',
    body: '2 short-answer responses in "Normalization Rules" await your scoring.',
    time: '3 hrs ago', course: 'WIA2004', read: false, icon: 'pencil',
  },
  {
    id: 'n5', priority: 'general', event: 'announcement',
    title: 'Reminder: attendance sync',
    body: 'Yesterday\'s WIF3001 session synced to SPeCTRUM successfully.',
    time: 'Yesterday', course: 'WIF3001', read: true, icon: 'cloud-done',
  },
]

// FR-202 — lecturer dashboard overview cards.
export const CLASS_OVERVIEW = {
  enrolled: 26, attendanceRate: 88, participationRate: 79, avgQuizScore: 68, atRisk: 3,
}

// FR-202 — assessment activity snapshot.
export const ASSESSMENT_ACTIVITY = [
  { id: 'as1', course: 'WIF3001', title: 'Sprint Planning Basics', meta: '10 MCQ · 20 min', open: 'Today 9:00 AM', closes: '11:59 PM', submitted: 14, enrolled: 26, status: 'open' },
  { id: 'as2', course: 'WIA2004', title: 'Normalization Rules', meta: '8 MCQ · 2 SA · 25 min', open: 'Mon', closes: 'Fri 5:00 PM', submitted: 9, enrolled: 31, status: 'open' },
  { id: 'as3', course: 'WIF3001', title: 'UML Basics', meta: 'Graded · avg 72%', meta2: '2 short answers unscored', status: 'needs-grading' },
  { id: 'as4', course: 'WIA2005', title: 'JavaScript DOM', meta: 'Graded · avg 84%', status: 'closed' },
]

// FR-702/703 — per-student indicators.
export const STUDENT_INDICATORS = [
  { id: 'U2300124', name: 'Ahmad Izzul Hakim', attendance: 92, absences: 1, participation: 'High', questions: 5, idu: 1, quizAvg: 78, trend: 'up', flagged: false },
  { id: 'U2300207', name: 'Chow Shino', attendance: 96, absences: 0, participation: 'High', questions: 8, idu: 2, quizAvg: 85, trend: 'up', flagged: false },
  { id: 'U2300312', name: 'Farhana Binti Roslan', attendance: 58, absences: 5, participation: 'Low', questions: 0, idu: 3, quizAvg: 41, trend: 'down', flagged: true, condition: 'Attendance below 80% · 5 consecutive absences · declining quiz scores' },
  { id: 'U2300445', name: 'Isyraf Danieal', attendance: 83, absences: 2, participation: 'Medium', questions: 2, idu: 1, quizAvg: 64, trend: 'same', flagged: false },
  { id: 'U2300521', name: 'Khor Jia Ling', attendance: 88, absences: 1, participation: 'Medium', questions: 3, idu: 0, quizAvg: 70, trend: 'up', flagged: false },
  { id: 'U2300603', name: 'Lim Wei Hao', attendance: 71, absences: 3, participation: 'Low', questions: 1, idu: 4, quizAvg: 52, trend: 'down', flagged: true, condition: 'Participation dropped by 45% compared with last month' },
  { id: 'U2300934', name: 'Nurul Amirah', attendance: 100, absences: 0, participation: 'High', questions: 6, idu: 0, quizAvg: 91, trend: 'up', flagged: false },
]

// FR-705 — class assessment performance by topic.
export const TOPIC_PERFORMANCE = [
  { topic: 'Scrum framework', avg: 82, missRate: 8, material: 'Week 8 slides (pp. 12–30)' },
  { topic: 'UML diagrams', avg: 74, missRate: 18, material: 'Week 9 notes (pp. 4–11)' },
  { topic: 'Normalization', avg: 55, missRate: 52, material: 'Week 10 slides (pp. 2–19)' },
  { topic: 'Estimation', avg: 68, missRate: 24, material: 'Week 11 slides (pp. 7–14)' },
]

// Module 6 — AI question bank (FR-602/603). Topics + sources come from M8 retrieval.
export const GENERATED_QUESTIONS = [
  { id: 'gq1', topic: 'Scrum framework', source: 'Week 8 slides · pp. 12–30', type: 'mcq', status: 'approved', text: 'Which ceremony follows the Daily Scrum?', options: ['Sprint Review', 'Sprint Retrospective', 'Backlog refinement', 'Release demo'], correct: 0 },
  { id: 'gq2', topic: 'Scrum framework', source: 'Week 8 slides · pp. 12–30', type: 'mcq', status: 'approved', text: 'Who owns the ordering of the Product Backlog?', options: ['Scrum Master', 'Product Owner', 'Dev team', 'Stakeholders'], correct: 1 },
  { id: 'gq3', topic: 'UML diagrams', source: 'Week 9 notes · pp. 4–11', type: 'mcq', status: 'pending', text: 'Which UML diagram best represents a sequence of system operations?', options: ['Class Diagram', 'Sequence Diagram', 'State Diagram', 'Component Diagram'], correct: 1 },
  { id: 'gq4', topic: 'UML diagrams', source: 'Week 9 notes · pp. 6–8', type: 'short', status: 'pending', text: 'Describe in one or two sentences when you would choose a state diagram over a sequence diagram.', suggested: 'When the focus is on how one object changes state in response to events over its lifetime, rather than the order of interactions between objects.' },
  { id: 'gq5', topic: 'Estimation', source: 'Week 11 slides · p. 9', type: 'mcq', status: 'pending', text: 'Story points estimate primarily…', options: ['Calendar time', 'Effort & complexity', 'Cost in RM', 'Developer seniority'], correct: 1 },
  { id: 'gq6', topic: 'Normalization', source: 'Week 10 slides · pp. 2–19', type: 'short', status: 'rejected', text: 'Explain why 2NF is violated by a partial dependency.', suggested: 'A non-key attribute depends on only part of a composite primary key.' },
]

// Module 6 — quiz results (FR-612/613).
export const QUIZ_RESULTS = {
  title: 'UML Basics', course: 'WIF3001',
  avg: 72, highest: 95, lowest: 40, submitted: 24, enrolled: 26,
  grades: [92, 85, 80, 76, 74, 72, 70, 68, 65, 60, 55, 48, 40],
  frequentlyMissed: [
    { text: 'Which UML diagram best represents a sequence of system operations?', wrongPct: 58, options: ['Class Diagram', 'Sequence Diagram', 'State Diagram', 'Component Diagram'], correct: 1, topic: 'UML diagrams', source: 'Week 9 notes · pp. 4–11' },
    { text: 'A component diagram shows…', wrongPct: 54, options: ['Runtime interactions', 'Physical code organisation', 'Class hierarchy', 'Deployment nodes'], correct: 1, topic: 'UML diagrams', source: 'Week 9 notes · p. 8' },
  ],
}

// FR-610 — AI-suggested scores for short answers.
export const SHORT_ANSWERS = [
  { id: 'sa1', student: 'Chow Shino', question: 'Describe when you would choose a state diagram over a sequence diagram.', response: 'A state diagram fits when we track how one object changes state due to events across its lifetime; a sequence diagram shows message order between objects.', aiScore: 9, aiMax: 10, aiNote: 'Covers the key distinction; example missing.' },
  { id: 'sa2', student: 'Khor Jia Ling', question: 'Describe when you would choose a state diagram over a sequence diagram.', response: 'Use a state diagram for states of one object. Sequence shows flow between many objects in time order.', aiScore: 7, aiMax: 10, aiNote: 'Correct direction but lacks the lifecycle framing.' },
]
