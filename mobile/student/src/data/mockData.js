import { C } from '../theme'

// Module 3/4 (participation / quiz) is not yet wired to a backend — these
// mock fixtures mirror the web student app so the Participation screens render.

export const PART_SUMMARY = { correct: 18, wrong: 5, skipped: 2, score: '72%' }

export const PARTICIPATION_GROUPS = [
  {
    id: 'today',
    label: 'Today — WIA2005 · Lec 12',
    perfKey: 'today',
    items: [
      {
        id: 'p1', type: 'quiz', typeLabel: 'Quiz',
        question: 'Which software development model uses iterative development with fixed-length sprints?',
        myAnswer: 'B — Scrum', myAnswerClass: 'correct',
        correctAnswer: 'B — Scrum',
        resultIcon: 'checkmark-circle', resultColor: C.green,
        meta: '10:12 AM · 30s timer · Answered in 8s',
      },
      {
        id: 'p2', type: 'poll', typeLabel: 'Poll',
        question: 'Which part of sprint planning do you find most confusing?',
        myAnswer: 'C — Story points', myAnswerClass: 'poll-ans',
        correctAnswer: null,
        meta: '10:35 AM · Your answer highlighted in blue',
        pollBars: [
          { opt: 'A', pct: 15, isMyChoice: false },
          { opt: 'B', pct: 28, isMyChoice: false },
          { opt: 'C', pct: 45, isMyChoice: true },
          { opt: 'D', pct: 12, isMyChoice: false },
        ],
      },
    ],
  },
  {
    id: 'lec11',
    label: 'Mon 20 May — WIA2005 · Lec 11',
    perfKey: 'lec11',
    items: [
      {
        id: 'p3', type: 'quiz', typeLabel: 'Quiz',
        question: 'What does SOLID stand for in object-oriented design?',
        myAnswer: 'A — Single Responsibility…', myAnswerClass: 'wrong',
        correctAnswer: 'B — Single, Open, Liskov…',
        resultIcon: 'close-circle', resultColor: C.red,
        meta: '10:08 AM · 60s timer · Answered in 42s',
      },
      {
        id: 'p4', type: 'quiz', typeLabel: 'Quiz',
        question: 'Which UML diagram best represents a sequence of system operations?',
        myAnswer: 'C — Sequence Diagram', myAnswerClass: 'correct',
        correctAnswer: 'C — Sequence Diagram',
        resultIcon: 'checkmark-circle', resultColor: C.green,
        meta: '10:32 AM · 30s timer · Answered in 11s',
      },
    ],
  },
  {
    id: 'wia2004',
    label: 'Wed 21 May — WIA2004 · Lec 11',
    perfKey: 'wia2004',
    items: [
      {
        id: 'p5', type: 'quiz', typeLabel: 'Quiz',
        question: 'Which normal form eliminates transitive dependencies?',
        myAnswer: null,
        correctAnswer: 'B — 3NF',
        resultIcon: 'remove-circle', resultColor: C.gray400,
        meta: '2:18 PM · Time expired · No response recorded',
        metaColor: C.orangeDk,
      },
    ],
  },
]

export const SESSION_PERFS = {
  today: {
    classLabel: 'WIA2005 · Software Engineering',
    title: 'Lecture 12 — Sprint Planning',
    date: 'Today, 25 May 2025 · 10:05 AM',
    stats: { correct: 1, wrong: 0, skipped: 0, score: '100%' },
    scoreValue: '100%', scoreColor: C.green, scoreWidth: '100%',
    classAvg: '68%',
    warning: null,
    questions: [
      {
        type: 'quiz', typeLabel: 'Quiz', meta: 'Q1 · 10:12 AM · 30s',
        question: 'Which software development model uses iterative development with fixed-length sprints?',
        answerPill: { label: 'B — Scrum ✓', cls: 'correct' },
        timeBadge: '8s · avg 19s', timeBadgeIcon: 'flash',
      },
      {
        type: 'poll', typeLabel: 'Poll', meta: 'Q2 · 10:35 AM · 60s',
        question: 'Which part of sprint planning do you find most confusing?',
        answerPill: { label: 'C — Story points', cls: 'poll-ans' },
        timeBadge: 'Class: 45% chose C', timeBadgeIcon: null,
      },
    ],
  },
  lec11: {
    classLabel: 'WIA2005 · Software Engineering',
    title: 'Lecture 11 — Agile Methodology',
    date: 'Mon, 20 May 2025 · 10:05 AM',
    stats: { correct: 1, wrong: 1, skipped: 0, score: '50%' },
    scoreValue: '50%', scoreColor: C.orange, scoreWidth: '50%',
    classAvg: '65%',
    warning: null,
    questions: [
      {
        type: 'quiz', typeLabel: 'Quiz', meta: 'Q1 · 10:08 AM · 60s',
        question: 'What does SOLID stand for in object-oriented design?',
        answerPill: { label: 'A — Single Resp… ✗', cls: 'wrong' },
        correctRef: 'B — Correct',
        timeBadge: '42s', timeBadgeIcon: 'time-outline',
      },
      {
        type: 'quiz', typeLabel: 'Quiz', meta: 'Q2 · 10:32 AM · 30s',
        question: 'Which UML diagram best represents a sequence of system operations?',
        answerPill: { label: 'C — Sequence Diagram ✓', cls: 'correct' },
        timeBadge: '11s · avg 22s', timeBadgeIcon: 'flash',
      },
    ],
  },
  wia2004: {
    classLabel: 'WIA2004 · Database Systems',
    title: 'Lecture 11 — Normal Forms',
    date: 'Wed, 21 May 2025 · 2:00 PM',
    stats: { correct: 0, wrong: 0, skipped: 1, score: '0%' },
    scoreValue: '0%', scoreColor: C.red, scoreWidth: '2%',
    classAvg: '72%',
    warning: 'You did not respond before time expired. Make sure your desk projection is active during quiz sessions.',
    questions: [
      {
        type: 'quiz', typeLabel: 'Quiz', meta: 'Q1 · 2:18 PM · 30s',
        question: 'Which normal form eliminates transitive dependencies?',
        answerPill: { label: '— No answer', cls: 'no-answer' },
        correctRef: 'B — 3NF',
        timeBadge: 'Expired', timeBadgeIcon: 'close-circle', timeBadgeColor: C.orangeDk,
      },
    ],
  },
}
