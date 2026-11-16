import { useState, useEffect, useCallback, useRef } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, Alert, TextInput,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import {
  getQuizDetail, startQuizAttempt, submitQuizAttempt, saveQuizAttemptProgress,
} from '../services/api'
import { C } from '../theme'

function Section({ tint = 'blue', badge, right, children, style }) {
  const bg = { blue: C.blueLt, green: C.greenLt, red: C.redLt, orange: C.orangeLt, gray: C.gray100, purple: C.purpleLt, yellow: C.yellowLt }[tint]
  const fg = { blue: C.blueDk, green: C.greenDk, red: C.redDk, orange: C.orangeDk, gray: C.textSub, purple: C.purple, yellow: C.yellowDk }[tint]
  return (
    <View style={[styles.section, style]}>
      {badge != null && (
        <View style={styles.sectionHead}>
          <View style={[styles.sectionBadge, { backgroundColor: bg }]}>
            <Text style={[styles.sectionBadgeText, { color: fg }]}>{badge}</Text>
          </View>
          <View style={{ flex: 1 }} />
          {right}
        </View>
      )}
      {children}
    </View>
  )
}

function fmt(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

/**
 * Take one quiz: starts the attempt on entry, shows the server-side countdown
 * (started_at + time limit) and auto-submits when it runs out (FR-606/608).
 */
export default function TakeQuiz({ navigation, route }) {
  const { showToast } = useStudent()
  const { quiz, courseCode } = (route?.params ?? {})

  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState({}) // question_id -> option text / free text
  const [attemptId, setAttemptId] = useState(null)
  const [deadline, setDeadline] = useState(null)
  const [remaining, setRemaining] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const submittedRef = useRef(false)

  // Start the attempt and load the quiz's questions (answers stripped server-side).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!quiz?.id) { setLoading(false); return }
      try {
        const detail = await getQuizDetail(quiz.id)
        if (cancelled) return
        let attId = detail.active_attempt_id
        let attDeadline = detail.active_deadline

        if (!attId) {
          const att = await startQuizAttempt(quiz.id)
          attId = att.attempt_id
          attDeadline = att.deadline
        }

        setAttemptId(attId)
        setDeadline(new Date(attDeadline))
        setQuestions(detail.questions ?? [])
        if (detail.saved_answers && Object.keys(detail.saved_answers).length > 0) {
          setAnswers(detail.saved_answers)
        }
        setLoading(false)
      } catch (e) {
        if (!cancelled) {
          showToast(e.message || 'Could not start the attempt', 'error')
          navigation.goBack()
        }
      }
    })()
    return () => { cancelled = true }
  }, [quiz?.id])

  // Auto-save progress whenever answers change
  useEffect(() => {
    if (!attemptId || submittedRef.current) return
    const timer = setTimeout(() => {
      const payload = Object.entries(answers).map(([qid, ans]) => ({
        question_id: Number(qid),
        answer: ans,
      }))
      if (payload.length > 0) {
        saveQuizAttemptProgress(attemptId, payload).catch(() => {})
      }
    }, 1000)
    return () => clearTimeout(timer)
  }, [answers, attemptId])

  const handleBack = () => {
    if (attemptId && Object.keys(answers).length > 0) {
      const payload = Object.entries(answers).map(([qid, ans]) => ({
        question_id: Number(qid),
        answer: ans,
      }))
      saveQuizAttemptProgress(attemptId, payload).catch(() => {})
    }
    showToast('Progress saved — you can continue before the time limit ends', 'info')
    navigation.goBack()
  }

  const doSubmit = useCallback(async (auto = false) => {
    if (submitting || submittedRef.current) return
    submittedRef.current = true
    setSubmitting(true)
    try {
      const payload = {
        answers: Object.entries(answers).map(([question_id, answer]) => ({
          question_id: Number(question_id), answer,
        })),
      }
      const res = await submitQuizAttempt(attemptId, payload.answers)
      navigation.replace('QuizResult', {
        attemptId: res?.attempt_id ?? attemptId,
        quizTitle: quiz?.title,
        justSubmitted: true,
        autoSubmitted: auto || res?.auto_submitted,
      })
    } catch (e) {
      if (auto || e?.status === 403 || e?.status === 409 || e?.message?.includes('expired') || e?.message?.includes('already_submitted')) {
        navigation.replace('QuizResult', {
          attemptId,
          quizTitle: quiz?.title,
          justSubmitted: true,
          autoSubmitted: true,
        })
        return
      }
      submittedRef.current = false
      setSubmitting(false)
      showToast(e.message || 'Could not submit', 'error')
    }
  }, [answers, attemptId, submitting, quiz?.title, navigation, showToast])

  // Countdown — auto-submit at zero (server also auto-submits expired attempts).
  useEffect(() => {
    if (!deadline) return
    const tick = () => {
      const left = Math.max(0, Math.floor((deadline.getTime() - Date.now()) / 1000))
      setRemaining(left)
      if (left <= 0 && !submittedRef.current) {
        submittedRef.current = true
        showToast('Time is up — auto-submitting your quiz…', 'info')
        doSubmit(true)
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [deadline, doSubmit, showToast])

  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title={quiz?.title ?? 'Quiz'} onBack={() => navigation.goBack()} />
        <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>
      </View>
    )
  }

  const low = remaining != null && remaining < 60

  return (
    <View style={styles.flex}>
      <Topbar
        title={quiz?.title ?? 'Quiz'}
        sub={courseCode}
        onBack={handleBack}
        right={
          remaining != null ? (
            <View style={[styles.timer, low && styles.timerLow]}>
              <Ionicons name="time-outline" size={14} color={low ? C.redDk : C.blueDk} />
              <Text style={[styles.timerText, low && { color: C.redDk }]}>{fmt(remaining)}</Text>
            </View>
          ) : null
        }
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {questions.length === 0 && (
          <View style={styles.empty}>
            <Ionicons name="alert-circle-outline" size={28} color={C.orange} />
            <Text style={styles.emptyText}>No questions on this quiz.</Text>
          </View>
        )}
        {questions.map((q, idx) => (
          <Section
            key={q.id}
            tint={q.type === 'mcq' ? 'blue' : 'purple'}
            badge={`Q${idx + 1} · ${q.type === 'mcq' ? 'MCQ' : 'Short answer'}`}
          >
            <Text style={styles.questionText}>{q.question}</Text>
            {q.type === 'mcq' ? (
              <View style={styles.options}>
                {(q.options ?? []).map((opt, i) => {
                  const currentSelected = (answers[q.id] || '').split(',').map(s => s.trim()).filter(Boolean)
                  const on = currentSelected.includes(opt)
                  const toggleOption = () => {
                    setAnswers(prev => {
                      const cur = (prev[q.id] || '').split(',').map(s => s.trim()).filter(Boolean)
                      const next = cur.includes(opt) ? cur.filter(x => x !== opt) : [...cur, opt]
                      return { ...prev, [q.id]: next.join(', ') }
                    })
                  }
                  return (
                    <TouchableOpacity
                      key={i}
                      style={[styles.option, on && styles.optionOn]}
                      onPress={toggleOption}
                      testID={`quiz-opt-${q.id}-${i}`}
                    >
                      <View style={[styles.letter, on && styles.letterOn]}>
                        <Text style={[styles.letterText, on && { color: '#fff' }]}>{'ABCD'[i] ?? '?'}</Text>
                      </View>
                      <Text style={[styles.optionText, on && { color: C.blueDk, fontWeight: '700' }]}>{opt}</Text>
                      {on && (
                        <Ionicons name="checkmark-circle" size={16} color={C.primary} style={{ marginLeft: 'auto' }} />
                      )}
                    </TouchableOpacity>
                  )
                })}
              </View>
            ) : (
              <TextInput
                style={styles.saInput}
                value={answers[q.id] ?? ''}
                onChangeText={t => setAnswers(prev => ({ ...prev, [q.id]: t }))}
                multiline
                placeholder="Type your answer…"
                placeholderTextColor={C.textHint}
                testID={`quiz-sa-${q.id}`}
              />
            )}
          </Section>
        ))}
        <TouchableOpacity
          style={[styles.submitBtn, submitting && { opacity: 0.6 }]}
          onPress={() => doSubmit(false)}
          disabled={submitting}
          testID="quiz-submit"
        >
          {submitting
            ? <ActivityIndicator size="small" color="#fff" />
            : <Ionicons name="send" size={16} color="#fff" />}
          <Text style={styles.submitText}>{submitting ? 'Submitting…' : 'Submit quiz'}</Text>
        </TouchableOpacity>
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  empty: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyText: { fontSize: 13, color: C.textSub },
  section: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  timer: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: C.blueLt, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  timerLow: { backgroundColor: C.redLt },
  timerText: { fontSize: 13, fontWeight: '800', color: C.blueDk },
  questionText: { fontSize: 14, fontWeight: '700', color: C.text, lineHeight: 20, marginBottom: 10 },
  options: { gap: 8 },
  option: {
    flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10,
    borderRadius: 10, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.gray50,
  },
  optionOn: { borderColor: C.primary, backgroundColor: C.blueLt },
  letter: {
    width: 26, height: 26, borderRadius: 7, borderWidth: 1.5, borderColor: C.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.card,
  },
  letterOn: { backgroundColor: C.primary, borderColor: C.primary },
  letterText: { fontSize: 12, fontWeight: '800', color: C.textSub },
  optionText: { fontSize: 13, color: C.text, flex: 1 },
  saInput: {
    minHeight: 90, borderWidth: 1.5, borderColor: C.border, borderRadius: 10,
    padding: 10, fontSize: 14, color: C.text, backgroundColor: C.gray50,
    textAlignVertical: 'top',
  },
  saBox: { height: 0 },
  submitBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: C.primary, borderRadius: 12, paddingVertical: 15, marginTop: 6,
  },
  submitText: { fontSize: 16, fontWeight: '800', color: '#fff' },
})
