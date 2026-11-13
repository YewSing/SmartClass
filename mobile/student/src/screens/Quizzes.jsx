// Module 6 — Quizzes (student view): FR-606, FR-607, FR-611.
// Organised by class (course) and by status so the list stays clean even with
// many quizzes: a class filter row + status tabs, then grouped cards.
// Frontend-only: attempt runner and results use local state until M6 is wired.
import { useState, useMemo, useRef, useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

// Published quizzes of enrolled courses (FR-606).
const PUBLISHED = [
  {
    id: 'qz1', course: 'WIF3001', title: 'Sprint Planning Basics',
    meta: '10 MCQ · 20 min', due: 'Today · 11:59 PM', status: 'open',
    questions: [
      { id: 'p1', type: 'mcq', text: 'Which ceremony follows the Daily Scrum?', options: ['Sprint Review', 'Sprint Retrospective', 'Backlog refinement', 'Release demo'], correct: 0 },
      { id: 'p2', type: 'mcq', text: 'Who owns the Product Backlog ordering?', options: ['Scrum Master', 'Product Owner', 'Dev team', 'Stakeholders'], correct: 1 },
      { id: 'p3', type: 'mcq', text: 'A Sprint is at most…', options: ['2 weeks', '1 month', '6 months', '1 week'], correct: 1 },
    ],
  },
  {
    id: 'qz2', course: 'WIF3001', title: 'Agile Roles Recap',
    meta: '6 MCQ · 15 min', due: 'Wed · 5:00 PM', status: 'open',
    questions: [
      { id: 'p1', type: 'mcq', text: 'Which role removes impediments?', options: ['Product Owner', 'Scrum Master', 'PM', 'QA lead'], correct: 1 },
    ],
  },
  {
    id: 'qz3', course: 'WIA2004', title: 'Normalization Rules',
    meta: '8 MCQ · 2 short-answer · 25 min', due: 'Fri · 5:00 PM', status: 'open',
    questions: [
      { id: 'p1', type: 'mcq', text: 'Which normal form removes transitive dependencies?', options: ['1NF', '2NF', '3NF', 'BCNF'], correct: 2 },
      { id: 'p2', type: 'short', text: 'In one sentence, state what a partial dependency is.' },
    ],
  },
  {
    id: 'qz4', course: 'WIA2005', title: 'JavaScript DOM',
    meta: 'Attempted · graded', due: 'Closed last Mon', status: 'graded', score: 90, total: 10,
    questions: [
      { id: 'p1', type: 'mcq', text: 'Which method selects elements by CSS selector?', options: ['getElementById', 'querySelector', 'createElement', 'appendChild'], yourAnswer: 1, correct: 1 },
      { id: 'p2', type: 'mcq', text: 'What does addEventListener return?', options: ['undefined', 'The element', 'A boolean', 'A promise'], yourAnswer: 0, correct: 0 },
    ],
  },
  {
    id: 'qz5', course: 'WIA2005', title: 'UML & Design Patterns',
    meta: '15 MCQ · 30 min', due: 'Opens Next Mon · 9:00 AM', status: 'scheduled',
  },
  {
    id: 'qz6', course: 'WIA2005', title: 'React State & Props',
    meta: 'Attempted · awaiting grading', due: 'Closed Tue', status: 'pending-grade',
  },
]

const STATUS_ORDER = { open: 0, 'pending-grade': 1, graded: 2, scheduled: 3 }
const STATUS_META = {
  open:           { label: 'Open',       variant: 'green',  icon: 'play-circle' },
  'pending-grade':{ label: 'In grading', variant: 'orange', icon: 'hourglass' },
  graded:         { label: 'Graded',     variant: 'blue',   icon: 'ribbon' },
  scheduled:      { label: 'Scheduled',  variant: 'gray',   icon: 'lock-closed' },
}

function fmtTime(sec) {
  const m = String(Math.floor(sec / 60)).padStart(2, '0')
  const s = String(sec % 60).padStart(2, '0')
  return `${m}:${s}`
}

export default function Quizzes({ navigation }) {
  const [attempt, setAttempt] = useState(null)
  const [classFilter, setClassFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('open')
  const timerRef = useRef(null)

  // FR-607 — auto-submit when the time limit expires.
  useEffect(() => {
    if (!attempt) return
    timerRef.current = setInterval(() => {
      setAttempt(a => {
        if (!a) return a
        if (a.secsLeft <= 1) return grade(a)
        return { ...a, secsLeft: a.secsLeft - 1 }
      })
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [attempt !== null])

  const grade = (a) => {
    const mcqs = a.quiz.questions.filter(q => q.type === 'mcq')
    const correct = mcqs.filter(q => a.answers[q.id] === q.correct).length
    return { ...a, result: { score: correct, total: mcqs.length } }
  }

  const classCodes = useMemo(
    () => ['All', ...[...new Set(PUBLISHED.map(q => q.course))]],
    []
  )

  const filtered = PUBLISHED
    .filter(q => classFilter === 'All' || q.course === classFilter)
    .filter(q => q.status === statusFilter)
    .sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status])

  const statusCounts = useMemo(() => {
    const c = { open: 0, 'pending-grade': 0, graded: 0, scheduled: 0 }
    PUBLISHED.forEach(q => { c[q.status] = (c[q.status] ?? 0) + 1 })
    return c
  }, [])

  const start = (quiz) =>
    setAttempt({ quiz, qi: 0, answers: {}, secsLeft: 3 * 60 })

  // ─── Attempt result view (FR-611) ────────────────────────────────────────────
  if (attempt?.result) {
    const { quiz, result } = attempt
    return (
      <View style={styles.flex}>
        <Topbar title="Your Result" sub={quiz.title} onBack={() => setAttempt(null)} />
        <ScrollView showsVerticalScrollIndicator={false} style={styles.flex}>
          <View style={styles.resultHero}>
            <Text style={styles.resultScore}>{result.score}/{result.total}</Text>
            <Text style={styles.resultLbl}>MCQ auto-graded (FR-608)</Text>
            <Text style={styles.resultNote}>
              Short-answer questions are scored by your lecturer — your final score may rise.
            </Text>
          </View>
          {quiz.questions.filter(q => q.type === 'mcq').map((q, i) => {
            const mine = attempt.answers[q.id]
            const ok = mine === q.correct
            return (
              <View key={q.id} style={styles.qCard}>
                <View style={styles.qTop}>
                  <Text style={styles.qNum}>Q{i + 1}</Text>
                  <Ionicons
                    name={ok ? 'checkmark-circle' : 'close-circle'}
                    size={18}
                    color={ok ? C.green : C.red}
                  />
                </View>
                <Text style={styles.qText}>{q.text}</Text>
                {q.options.map((opt, oi) => (
                  <View
                    key={oi}
                    style={[
                      styles.optRow,
                      oi === q.correct && styles.optCorrect,
                      oi === mine && mine !== q.correct && styles.optWrong,
                    ]}
                  >
                    <Text style={styles.optLetter}>{String.fromCharCode(65 + oi)}</Text>
                    <Text style={styles.optText}>{opt}</Text>
                    {oi === q.correct && <Ionicons name="checkmark" size={14} color={C.greenDk} style={{ marginLeft: 'auto' }} />}
                    {oi === mine && mine !== q.correct && <Text style={styles.yourAns}>your answer</Text>}
                  </View>
                ))}
              </View>
            )
          })}
          <View style={{ height: 24 }} />
        </ScrollView>
      </View>
    )
  }

  // ─── Attempt runner (FR-607) ─────────────────────────────────────────────────
  if (attempt) {
    const { quiz, qi } = attempt
    const q = quiz.questions[qi]
    const last = qi >= quiz.questions.length - 1
    return (
      <View style={styles.flex}>
        <Topbar
          title={quiz.title}
          sub={`${quiz.course} · ${fmtTime(attempt.secsLeft)} left`}
        />
        <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
          <View style={styles.attemptTop}>
            <Badge variant="blue">{`Question ${qi + 1} of ${quiz.questions.length}`}</Badge>
            <Text style={[styles.timer, { color: attempt.secsLeft < 30 ? C.red : C.textSub }]}>
              {fmtTime(attempt.secsLeft)}
            </Text>
          </View>
          <View style={styles.attemptCard}>
            <Text style={styles.qText}>{q.text}</Text>
            {q.type === 'mcq' ? (
              q.options.map((opt, oi) => (
                <TouchableOpacity
                  key={oi}
                  style={[styles.optRow, attempt.answers[q.id] === oi && styles.optSelected]}
                  onPress={() => setAttempt(a => ({ ...a, answers: { ...a.answers, [q.id]: oi } }))}
                >
                  <Text style={styles.optLetter}>{String.fromCharCode(65 + oi)}</Text>
                  <Text style={styles.optText}>{opt}</Text>
                  {attempt.answers[q.id] === oi && (
                    <Ionicons name="checkmark-circle" size={16} color={C.primary} style={{ marginLeft: 'auto' }} />
                  )}
                </TouchableOpacity>
              ))
            ) : (
              <View>
                <Text style={styles.saHint}>Short answer — graded later by your lecturer (FR-609).</Text>
                <View style={styles.saBox}>
                  <Text style={styles.saPlaceholder}>Your typed answer will appear here…</Text>
                </View>
              </View>
            )}
          </View>
          <View style={styles.attemptNav}>
            {qi > 0 && (
              <TouchableOpacity style={styles.navBtn} onPress={() => setAttempt(a => ({ ...a, qi: a.qi - 1 }))}>
                <Text style={styles.navBtnText}>Previous</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity
              style={[styles.navBtnPrimary, !last && styles.navBtnFull]}
              onPress={() => (last ? setAttempt(a => grade(a)) : setAttempt(a => ({ ...a, qi: a.qi + 1 })))}
            >
              <Text style={styles.navBtnPrimaryText}>{last ? 'Submit' : 'Next'}</Text>
            </TouchableOpacity>
          </View>
          <View style={{ height: 24 }} />
        </ScrollView>
      </View>
    )
  }

  // ─── List view: class chips + status tabs ────────────────────────────────────
  return (
    <View style={styles.flex}>
      <Topbar title="Quizzes" sub="Published quizzes for your courses" />

      {/* Status tabs with counts */}
      <View style={styles.tabsRow}>
        {Object.entries(STATUS_META).map(([id, meta]) => (
          <TouchableOpacity
            key={id}
            style={[styles.tab, statusFilter === id && styles.tabActive]}
            onPress={() => setStatusFilter(id)}
          >
            <Ionicons name={meta.icon} size={13} color={statusFilter === id ? C.primary : C.textHint} />
            <Text style={[styles.tabText, statusFilter === id && styles.tabTextActive]}>{meta.label}</Text>
            <View style={[styles.tabCount, statusFilter === id && styles.tabCountOn]}>
              <Text style={[styles.tabCountText, statusFilter === id && { color: '#fff' }]}>
                {statusCounts[id] ?? 0}
              </Text>
            </View>
          </TouchableOpacity>
        ))}
      </View>

      {/* Class chips */}
      <View style={styles.classRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.classContent}>
          {classCodes.map(code => (
            <TouchableOpacity
              key={code}
              style={[styles.classChip, classFilter === code && styles.classChipOn]}
              onPress={() => setClassFilter(code)}
            >
              <Text style={[styles.classChipText, classFilter === code && styles.classChipTextOn]}>{code}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {filtered.length === 0 && (
          <View style={styles.empty}>
            <Ionicons name="document-text-outline" size={34} color={C.gray300} />
            <Text style={styles.emptyText}>
              No {STATUS_META[statusFilter].label.toLowerCase()} quizzes
              {classFilter !== 'All' ? ` in ${classFilter}` : ''}.
            </Text>
          </View>
        )}

        {filtered.map(qz => (
          <View key={qz.id} style={styles.card}>
            <View style={styles.cardTop}>
              <View style={styles.courseTag}><Text style={styles.courseTagText}>{qz.course}</Text></View>
              <Text style={styles.dueText} numberOfLines={1}>{qz.due}</Text>
            </View>
            <Text style={styles.cardTitle}>{qz.title}</Text>
            <Text style={styles.cardMeta}>{qz.meta}</Text>

            {qz.status === 'open' && (
              <TouchableOpacity style={styles.startBtn} onPress={() => start(qz)}>
                <Ionicons name="play" size={14} color="#fff" />
                <Text style={styles.startBtnText}>Start attempt</Text>
                <Text style={styles.startHint}>one attempt only</Text>
              </TouchableOpacity>
            )}
            {qz.status === 'graded' && (
              <TouchableOpacity
                style={styles.resultBtn}
                onPress={() => setAttempt({ quiz: qz, result: { score: qz.score / 10, total: qz.total } })}
              >
                <Ionicons name="ribbon" size={14} color={C.primary} />
                <Text style={styles.resultBtnText}>Score: {qz.score}% · view per-question result</Text>
                <Ionicons name="chevron-forward" size={13} color={C.primary} />
              </TouchableOpacity>
            )}
            {qz.status === 'pending-grade' && (
              <View style={styles.pendingRow}>
                <Ionicons name="hourglass" size={13} color={C.orangeDk} />
                <Text style={styles.pendingText}>Waiting for your lecturer to grade the short answers</Text>
              </View>
            )}
            {qz.status === 'scheduled' && (
              <View style={styles.pendingRow}>
                <Ionicons name="lock-closed-outline" size={13} color={C.textHint} />
                <Text style={styles.pendingTextGray}>Opens later — no attempt yet</Text>
              </View>
            )}
          </View>
        ))}
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  tabsRow: {
    flexDirection: 'row', backgroundColor: C.card,
    borderBottomWidth: 1, borderBottomColor: C.border,
  },
  tab: {
    flex: 1, paddingVertical: 11, alignItems: 'center', gap: 3,
    borderBottomWidth: 2, borderBottomColor: 'transparent',
  },
  tabActive: { borderBottomColor: C.primary },
  tabText: { fontSize: 11, fontWeight: '600', color: C.textSub },
  tabTextActive: { color: C.primary },
  tabCount: {
    backgroundColor: C.gray100, minWidth: 18, height: 16, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5,
  },
  tabCountOn: { backgroundColor: C.primary },
  tabCountText: { fontSize: 9, fontWeight: '800', color: C.gray600 },
  classRow: {
    backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  classContent: { paddingHorizontal: 12, paddingVertical: 9, gap: 8 },
  classChip: {
    paddingHorizontal: 13, paddingVertical: 6, borderRadius: 18,
    borderWidth: 1, borderColor: C.border, backgroundColor: C.bg,
  },
  classChipOn: { backgroundColor: C.primary, borderColor: C.primary },
  classChipText: { fontSize: 12, fontWeight: '700', color: C.textSub },
  classChipTextOn: { color: '#fff' },
  empty: { alignItems: 'center', padding: 44, gap: 8 },
  emptyText: { fontSize: 13, color: C.textHint, textAlign: 'center' },
  card: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 10,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  cardTop: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8,
  },
  courseTag: { backgroundColor: C.blueLt, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6 },
  courseTagText: { fontSize: 10, fontWeight: '800', color: C.primary },
  dueText: { fontSize: 10, fontWeight: '700', color: C.textHint, flex: 1, textAlign: 'right', marginLeft: 8 },
  cardTitle: { fontSize: 15, fontWeight: '700', color: C.text },
  cardMeta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  startBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 11, marginTop: 12,
  },
  startBtnText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  startHint: { fontSize: 10, color: '#BFDBFE' },
  resultBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.blueLt, borderRadius: 10, paddingVertical: 11, paddingHorizontal: 12, marginTop: 12,
  },
  resultBtnText: { flex: 1, fontSize: 13, fontWeight: '700', color: C.primary },
  pendingRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12,
    backgroundColor: C.orangeLt, borderRadius: 9, paddingHorizontal: 10, paddingVertical: 9,
  },
  pendingText: { flex: 1, fontSize: 12, color: C.orangeDk, fontWeight: '600' },
  pendingTextGray: { fontSize: 12, color: C.textHint },
  attemptTop: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingTop: 14,
  },
  timer: { fontSize: 13, fontWeight: '800' },
  attemptCard: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 10,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 16,
  },
  qText: { fontSize: 15, fontWeight: '700', color: C.text, lineHeight: 21, marginBottom: 14 },
  qNum: { fontSize: 11, fontWeight: '800', color: C.primary },
  qTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  qCard: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 10,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  optRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: 1, borderColor: C.border, borderRadius: 10,
    padding: 11, marginBottom: 8, backgroundColor: C.bg,
  },
  optSelected: { borderColor: C.primary, backgroundColor: C.blueLt },
  optCorrect: { borderColor: C.green, backgroundColor: C.greenLt },
  optWrong: { borderColor: C.red, backgroundColor: C.redLt },
  optLetter: { fontSize: 12, fontWeight: '800', color: C.gray600, width: 16 },
  optText: { flex: 1, fontSize: 13, color: C.text },
  yourAns: { fontSize: 10, color: C.redDk, fontWeight: '700' },
  saHint: { fontSize: 12, color: C.textSub, marginBottom: 8 },
  saBox: {
    borderWidth: 1.5, borderColor: C.border, borderRadius: 10,
    backgroundColor: C.bg, minHeight: 90, padding: 12,
  },
  saPlaceholder: { fontSize: 13, color: C.textHint },
  attemptNav: { flexDirection: 'row', gap: 8, marginHorizontal: 16, marginTop: 12 },
  navBtn: {
    paddingVertical: 12, paddingHorizontal: 18, borderRadius: 10,
    borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card, alignItems: 'center',
  },
  navBtnText: { fontSize: 14, fontWeight: '600', color: C.text },
  navBtnPrimary: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: C.primary, alignItems: 'center' },
  navBtnFull: {},
  navBtnPrimaryText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  resultHero: {
    backgroundColor: C.primary, margin: 16, borderRadius: 14, padding: 20, alignItems: 'center',
  },
  resultScore: { fontSize: 40, fontWeight: '900', color: '#fff' },
  resultLbl: { fontSize: 13, color: '#BFDBFE', marginTop: 2 },
  resultNote: {
    fontSize: 11, color: '#DBEAFE', textAlign: 'center', marginTop: 10,
    lineHeight: 16, backgroundColor: 'rgba(255,255,255,0.12)',
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8,
  },
})
