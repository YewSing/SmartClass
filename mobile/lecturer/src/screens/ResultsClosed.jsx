import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, TextInput,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { getQuizAttempts, getUnscoredAnswers, getAllAttemptAnswers, scoreShortAnswer, suggestScore } from '../services/api'
import { C } from '../theme'

/** Section card in the interaction style: colored title chip + right node (S29 pattern). */
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

export default function ResultsClosed({ navigation, route }) {
  const { showToast } = useLecturer()
  const { attemptId, quizId } = (route?.params ?? {})

  const [attempt, setAttempt] = useState(null)
  const [unscored, setUnscored] = useState([])
  const [allAnswers, setAllAnswers] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(null)
  const [scoring, setScoring] = useState({}) // answerId -> busy
  const loading = !loaded

  const loadAttempt = useCallback(async () => {
    if (!quizId) return
    try {
      const list = await getQuizAttempts(quizId)
      const a = list.find(x => x.attempt_id === attemptId)
      setAttempt(a ?? null)
      if (!a) setError('Attempt not found for this quiz')
    } catch (e) { setError(e.message || 'Could not load attempt') }
  }, [quizId, attemptId])

  const loadUnscored = useCallback(async () => {
    if (!attemptId) return
    try {
      const [uList, allList] = await Promise.all([
        getUnscoredAnswers(attemptId),
        getAllAttemptAnswers(attemptId).catch(() => []),
      ])
      setUnscored(uList)
      setAllAnswers(allList)
    } catch (e) { setError(e.message || 'Could not load answers') }
  }, [attemptId])

  useEffect(() => {
    if (!quizId || !attemptId) {
      setError('This page was opened without an attempt — go back and open it from Live Results.')
      setLoaded(true)
      return
    }
    let cancelled = false
    Promise.all([loadAttempt(), loadUnscored()])
      .finally(() => { if (!cancelled) setLoaded(true) })
    return () => { cancelled = true }
  }, [loadAttempt, loadUnscored, quizId, attemptId])

  const complete = attempt?.grading_complete
  const statusLabel = (s) => {
    switch (s) {
      case 'started': return 'In progress'
      case 'submitted': return 'Submitted'
      case 'auto_submitted': return 'Auto-submitted'
      default: return s
    }
  }

  const handleSuggest = async (answer) => {
    setScoring(prev => ({ ...prev, [answer.answer_id]: true }))
    try {
      const suggestion = await suggestScore(attemptId, answer.answer_id)
      const maxPts = answer.max_score ?? 1.0
      const pts = Math.round((suggestion.suggested_score / 100) * maxPts * 10) / 10
      setScoreInputs(prev => ({ ...prev, [answer.answer_id]: String(pts) }))
      setUnscored(prev => prev.map(a =>
        a.answer_id === answer.answer_id ? { ...a, suggestedScore: suggestion.suggested_score, suggestedReason: suggestion.reasoning } : a
      ))
      showToast(`AI suggests ${pts}/${maxPts} (${Math.round(suggestion.suggested_score)}%)`, 'info')
    } catch (e) {
      showToast(e.message || 'Could not get AI suggestion', 'error')
    } finally {
      setScoring(prev => { const { [answer.answer_id]: _, ...rest } = prev; return rest })
    }
  }

  const handleSave = async (answer) => {
    const maxScore = answer.max_score ?? 1.0
    const input = scoreInputs[answer.answer_id] ?? '0'
    const score = parseFloat(input)
    if (Number.isNaN(score) || score < 0 || score > maxScore) {
      showToast(`Enter a score between 0 and ${maxScore}`, 'error')
      return
    }
    setScoring(prev => ({ ...prev, [answer.answer_id]: true }))
    try {
      await scoreShortAnswer(attemptId, answer.answer_id, score)
      setUnscored(prev => prev.filter(a => a.answer_id !== answer.answer_id))
      showToast(`Score saved (${score}/${maxScore})`, 'success')
      if (attempt && !attempt.grading_complete) {
        // re-fetch to detect completion
        const list = await getQuizAttempts(quizId)
        const a = list.find(x => x.attempt_id === attemptId)
        setAttempt(a)
      }
    } catch (e) {
      showToast(e.message || 'Could not save score', 'error')
    } finally {
      setScoring(prev => { const { [answer.answer_id]: _, ...rest } = prev; return rest })
    }
  }

  // per-answer score inputs (uncontrolled text, read on save)
  const [scoreInputs, setScoreInputs] = useState({})

  return (
    <View style={styles.flex}>
      <Topbar
        title="Score & Review"
        sub={attempt ? `Attempt #${String(attempt.attempt_id).slice(-4)}` : undefined}
        onBack={() => navigation.goBack()}
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {loading && <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>}

        {!loading && error && (
          <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>
        )}

        {!loading && !error && attempt && (
          <>
            {/* Attempt status */}
            <Section tint="blue" badge="Attempt" right={
              <Badge variant={attempt.status === 'submitted' || attempt.auto_submitted ? 'green' : 'blue'} dot>
                {statusLabel(attempt.status)}
              </Badge>
            }>
              <View style={styles.statusRow}>
                <Text style={styles.statusLabel}>Score</Text>
                <Text style={styles.statusValue}>{attempt.score != null ? `${attempt.score}%` : '--'}</Text>
              </View>
              {attempt.auto_submitted && (
                <View style={styles.statusRow}>
                  <Text style={styles.statusLabel}>Submitted</Text>
                  <Text style={[styles.statusValue, { color: C.textSub }]}>Auto-submitted (deadline passed)</Text>
                </View>
              )}
              <View style={styles.statusRow}>
                <Text style={styles.statusLabel}>Grading</Text>
                {complete
                  ? <Badge variant="green">Complete</Badge>
                  : <Badge variant="orange">Short answers awaiting your score</Badge>}
              </View>
            </Section>

            {/* Unscored short answers */}
            <Section
              tint="yellow"
              badge="Short answers to score"
              right={unscored.length > 0 ? <Text style={styles.counter}>{unscored.length} waiting</Text> : null}
            >
              {unscored.length === 0 && (
                <View style={styles.empty}>
                  <Ionicons name="checkmark-circle" size={28} color={C.green} />
                  <Text style={styles.emptyText}>All short answers are scored.</Text>
                </View>
              )}
            {unscored.map(answer => (
              <View key={answer.answer_id} style={styles.answerCard}>
                <View style={styles.answerBody}>
                  <Text style={styles.answerQuestion}>{answer.question}</Text>
                  <View style={styles.answerMeta}>
                    <Text style={styles.metaLabel}>Student's answer</Text>
                    <Text style={styles.answerText}>{answer.answer ?? '(no answer)'}</Text>
                    {answer.suggested_answer && (
                      <>
                        <Text style={styles.metaLabel}>Ideal answer</Text>
                        <Text style={[styles.answerText, { color: C.textSub }]}>{answer.suggested_answer}</Text>
                      </>
                    )}
                  </View>
                  <View style={styles.scoreRow}>
                    <View style={styles.stepperWrap}>
                      <TouchableOpacity
                        style={styles.stepperBtn}
                        onPress={() => {
                          const maxPts = answer.max_score ?? 1.0
                          const cur = parseFloat(scoreInputs[answer.answer_id] ?? '0') || 0
                          const step = maxPts <= 2 ? 0.5 : 1
                          const next = Math.max(0, Math.min(maxPts, +(cur - step).toFixed(2)))
                          setScoreInputs(prev => ({ ...prev, [answer.answer_id]: String(next) }))
                        }}
                      >
                        <Ionicons name="remove" size={16} color={C.text} />
                      </TouchableOpacity>
                      <TextInput
                        style={styles.stepperInput}
                        value={scoreInputs[answer.answer_id] ?? '0'}
                        onChangeText={t => {
                          const maxPts = answer.max_score ?? 1.0
                          const v = parseFloat(t)
                          if (!t) setScoreInputs(prev => ({ ...prev, [answer.answer_id]: '' }))
                          else if (!isNaN(v)) {
                            setScoreInputs(prev => ({ ...prev, [answer.answer_id]: String(Math.max(0, Math.min(maxPts, v))) }))
                          }
                        }}
                        keyboardType="numeric"
                      />
                      <Text style={styles.stepperMax}>/ {answer.max_score ?? 1}</Text>
                      <TouchableOpacity
                        style={styles.stepperBtn}
                        onPress={() => {
                          const maxPts = answer.max_score ?? 1.0
                          const cur = parseFloat(scoreInputs[answer.answer_id] ?? '0') || 0
                          const step = maxPts <= 2 ? 0.5 : 1
                          const next = Math.max(0, Math.min(maxPts, +(cur + step).toFixed(2)))
                          setScoreInputs(prev => ({ ...prev, [answer.answer_id]: String(next) }))
                        }}
                      >
                        <Ionicons name="add" size={16} color={C.text} />
                      </TouchableOpacity>
                    </View>

                    <TouchableOpacity
                      style={styles.suggestBtn}
                      onPress={() => handleSuggest(answer)}
                      disabled={scoring[answer.answer_id]}
                    >
                      <Ionicons name="sparkles" size={14} color={C.primary} />
                      <Text style={styles.suggestText}>AI suggest</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.saveBtn}
                      onPress={() => handleSave(answer)}
                      disabled={scoring[answer.answer_id]}
                    >
                      <Text style={styles.saveText}>Save</Text>
                    </TouchableOpacity>
                  </View>
                  {answer.suggestedScore != null && (
                    <Text style={styles.aiHint}>AI suggests {Math.round(answer.suggestedScore)}% · {answer.suggestedReason}</Text>
                  )}
                </View>
              </View>
            ))}
            </Section>

            {/* All Questions & Answers Breakdown */}
            {allAnswers.length > 0 && (
              <Section tint="blue" badge="All student responses" right={<Text style={styles.counter}>{allAnswers.length} questions</Text>}>
                {allAnswers.map((item, idx) => {
                  const maxPts = item.max_score ?? 1.0
                  const isCorrect = item.score != null && item.score >= maxPts
                  const isWrong = item.score != null && item.score < maxPts
                  const isUnscored = item.score == null
                  return (
                    <View key={item.answer_id || idx} style={styles.reviewCard}>
                      <View style={styles.reviewHead}>
                        <Text style={styles.reviewQ}>Q{idx + 1} · {item.type === 'mcq' ? 'MCQ' : 'Short answer'} · {item.score != null ? item.score : 0}/{maxPts} pts</Text>
                        <View style={[styles.reviewBadge, {
                          backgroundColor: isCorrect ? C.greenLt : (isWrong ? C.redLt : C.yellowLt),
                        }]}>
                          <Text style={[styles.reviewBadgeText, {
                            color: isCorrect ? C.greenDk : (isWrong ? C.redDk : C.yellowDk),
                          }]}>
                            {isCorrect ? 'Correct' : (isWrong ? 'Incorrect' : 'Needs score')}
                          </Text>
                        </View>
                      </View>

                      <Text style={styles.reviewQuestion}>{item.question}</Text>

                      <View style={styles.reviewField}>
                        <Text style={styles.reviewLabel}>Student Answer:</Text>
                        <Text style={[styles.reviewAnswerVal, isWrong && { color: C.redDk }]}>{item.answer || '(unanswered)'}</Text>
                      </View>

                      {item.correct_answer && (
                        <View style={styles.reviewField}>
                          <Text style={styles.reviewLabel}>Correct Answer:</Text>
                          <Text style={[styles.reviewAnswerVal, { color: C.greenDk }]}>{item.correct_answer}</Text>
                        </View>
                      )}

                      {item.suggested_answer && (
                        <View style={styles.reviewField}>
                          <Text style={styles.reviewLabel}>Ideal Answer:</Text>
                          <Text style={[styles.reviewAnswerVal, { color: C.textSub }]}>{item.suggested_answer}</Text>
                        </View>
                      )}
                    </View>
                  )
                })}
              </Section>
            )}

            {complete && (
              <Section tint="green" badge="Grading">
                <View style={styles.doneCard}>
                  <Ionicons name="checkmark-circle" size={32} color={C.green} />
                  <Text style={styles.doneTitle}>Grading complete</Text>
                  <Text style={styles.doneSub}>
                    Final score: <Text style={styles.doneScore}>{attempt.score != null ? `${attempt.score}%` : '--'}</Text>
                  </Text>
                </View>
              </Section>
            )}

            <View style={{ height: 24 }} />
          </>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 40 },
  err: { padding: 16 },
  errText: { fontSize: 13, color: C.red },
  section: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  counter: { fontSize: 11, color: C.textHint, fontWeight: '600' },
  statusRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  statusLabel: { fontSize: 12, fontWeight: '700', color: C.textSub },
  statusValue: { fontSize: 15, fontWeight: '800', color: C.text },
  sectionTitle: { fontSize: 14, fontWeight: '800', color: C.text, marginBottom: 8 },
  empty: { alignItems: 'center', paddingVertical: 30, gap: 8 },
  emptyText: { fontSize: 14, color: C.textSub },
  reviewCard: {
    backgroundColor: C.gray50, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  reviewHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  reviewQ: { fontSize: 12, fontWeight: '800', color: C.textSub },
  reviewBadge: { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2 },
  reviewBadgeText: { fontSize: 10, fontWeight: '800' },
  reviewQuestion: { fontSize: 13, fontWeight: '700', color: C.text, marginBottom: 6 },
  reviewField: { marginTop: 4 },
  reviewLabel: { fontSize: 11, fontWeight: '700', color: C.textHint },
  reviewAnswerVal: { fontSize: 13, fontWeight: '600', color: C.text, marginTop: 1 },
  answerCard: {
    backgroundColor: C.card, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  answerBody: { flex: 1 },
  answerQuestion: { fontSize: 14, fontWeight: '800', color: C.text, lineHeight: 20, marginBottom: 8 },
  answerMeta: { marginBottom: 8 },
  metaLabel: { fontSize: 11, fontWeight: '700', color: C.textSub, marginBottom: 4 },
  answerText: { fontSize: 13, color: C.text, lineHeight: 18, marginBottom: 4 },
  scoreRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap',
  },
  stepperWrap: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: C.gray50,
    borderWidth: 1.5, borderColor: C.border, borderRadius: 8, paddingHorizontal: 4, height: 40,
  },
  stepperBtn: {
    padding: 6, alignItems: 'center', justifyContent: 'center',
  },
  stepperInput: {
    minWidth: 32, textAlign: 'center', fontSize: 14, fontWeight: '700', color: C.text, paddingHorizontal: 2,
  },
  stepperMax: {
    fontSize: 12, fontWeight: '700', color: C.textSub, marginRight: 4,
  },
  suggestBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6, paddingHorizontal: 10,
    borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.card,
  },
  suggestText: { fontSize: 12, fontWeight: '700', color: C.primary },
  saveBtn: {
    paddingVertical: 6, paddingHorizontal: 12, borderRadius: 8, backgroundColor: C.primary,
  },
  saveText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  aiHint: { fontSize: 11, color: C.textSub, marginTop: 4, fontStyle: 'italic' },
  doneCard: {
    backgroundColor: C.greenLt, borderRadius: 12, padding: 16, marginTop: 10, alignItems: 'center',
    borderWidth: 1, borderColor: C.greenLt,
  },
  doneTitle: { fontSize: 16, fontWeight: '800', color: C.greenDk, marginTop: 8 },
  doneSub: { fontSize: 13, color: C.text, marginTop: 4 },
  doneScore: { fontSize: 20, fontWeight: '800', color: C.greenDk },
})
