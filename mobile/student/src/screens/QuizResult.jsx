import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { getQuizAttemptResult } from '../services/api'
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

/** Per-question result for one attempt — visible only after grading is complete (FR-611). */
export default function QuizResult({ navigation, route }) {
  const { attemptId, quizTitle, justSubmitted, autoSubmitted } = (route?.params ?? {})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!attemptId) { setLoading(false); return }
    try {
      const r = await getQuizAttemptResult(attemptId)
      setResult(r)
      setError(null)
    } catch (e) {
      setError(e.message || 'Could not load the result')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [attemptId])

  useEffect(() => { load() }, [load])

  const mcqTotal = result?.answers?.filter(a => a.type === 'mcq').length ?? 0
  const mcqCorrect = result?.answers?.filter(a => a.type === 'mcq' && a.score === 1.0).length ?? 0

  return (
    <View style={styles.flex}>
      <Topbar title={quizTitle ?? 'Quiz result'} onBack={() => navigation.goBack()} />
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load() }} />}
      >
        {loading && <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>}

        {!loading && error && <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>}

        {!loading && !error && result && (
          <>
            <Section
              tint={result.grading_complete ? 'green' : 'yellow'}
              badge={result.grading_complete ? 'Graded' : 'Waiting for grading'}
              right={autoSubmitted || result.auto_submitted
                ? <Text style={styles.autoNote}>auto-submitted</Text>
                : null}
            >
              {justSubmitted && !result.grading_complete && (
                <Text style={styles.note}>Submitted! Your lecturer still has to score the short answers — results appear here once grading is complete.</Text>
              )}
              {result.student_score_visible && result.score != null && (
                <View style={styles.scoreRow}>
                  <Text style={styles.scoreNum}>{Math.round(result.score)}%</Text>
                  {mcqTotal > 0 && (
                    <Text style={styles.scoreSub}>{mcqCorrect}/{mcqTotal} MCQ correct</Text>
                  )}
                </View>
              )}
              {!result.grading_complete && !justSubmitted && (
                <Text style={styles.note}>Grading is not complete yet — pull to refresh.</Text>
              )}
              {result.grading_complete && !result.student_score_visible && (
                <Text style={styles.note}>Your lecturer choose not to reveal the answer to review.</Text>
              )}
            </Section>

            {(result.answers ?? []).length > 0 && (result.student_score_visible || justSubmitted) && (
              <Section tint="blue" badge="Your answers">
                {result.answers.map((a, i) => {
                  const maxPts = a.max_score ?? 1.0
                  const isCorrect = a.score != null && a.score >= maxPts
                  const isWrong = a.score != null && a.score < maxPts
                  return (
                    <View key={a.question_id} style={styles.answerCard}>
                      <View style={styles.answerHead}>
                        <Text style={styles.answerQ}>Q{i + 1} · {a.type === 'mcq' ? 'MCQ' : 'Short answer'} · {a.score != null ? a.score : 0}/{maxPts} pt{maxPts !== 1 ? 's' : ''}</Text>
                        <View style={[styles.badge, { backgroundColor: isCorrect ? C.greenLt : (isWrong ? C.redLt : C.yellowLt) }]}>
                          <Text style={[styles.badgeText, { color: isCorrect ? C.greenDk : (isWrong ? C.redDk : C.yellowDk) }]}>
                            {isCorrect ? 'Correct' : (isWrong ? 'Incorrect' : 'Partially scored')}
                          </Text>
                        </View>
                      </View>

                      {a.question && <Text style={styles.answerBody}>{a.question}</Text>}

                      <Text style={styles.answerLine}>
                        Your answer: <Text style={[styles.answerValue, isWrong && { color: C.redDk }]}>{a.answer || '—'}</Text>
                      </Text>

                      {/* Reveal correct answer if student got it wrong or if review is allowed */}
                      {isWrong && a.correct_answer && (
                        <Text style={styles.answerLine}>
                          Correct answer: <Text style={[styles.answerValue, { color: C.greenDk }]}>{a.correct_answer}</Text>
                        </Text>
                      )}

                      {a.suggested_answer && (
                        <Text style={styles.answerLine}>
                          Ideal answer: <Text style={[styles.answerValue, { color: C.greenDk }]}>{a.suggested_answer}</Text>
                        </Text>
                      )}

                      {/* AI learning suggestion on wrong answers */}
                      {isWrong && a.learning_hint ? (
                        <View style={styles.hintBox}>
                          <View style={styles.hintHeader}>
                            <Ionicons name="sparkles" size={14} color={C.primary} />
                            <Text style={styles.hintTitle}>Where to find the answer & learn</Text>
                          </View>
                          <Text style={styles.hintBody}>{a.learning_hint}</Text>
                        </View>
                      ) : null}
                    </View>
                  )
                })}
              </Section>
            )}

            {!result.student_score_visible && (result.answers ?? []).length > 0 && (
              <Section tint="gray" badge="Submitted answers">
                {result.answers.map((a, i) => (
                  <View key={a.question_id} style={styles.answerCard}>
                    <Text style={styles.answerQ}>Q{i + 1}</Text>
                    <Text style={styles.answerLine}>
                      Your answer: <Text style={styles.answerValue}>{a.answer || '—'}</Text>
                    </Text>
                  </View>
                ))}
              </Section>
            )}
          </>
        )}
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  loading: { paddingVertical: 60, alignItems: 'center' },
  err: { padding: 16 },
  errText: { fontSize: 13, color: C.red },
  section: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  autoNote: { fontSize: 11, color: C.orangeDk, fontWeight: '700' },
  note: { fontSize: 13, color: C.textSub, lineHeight: 18 },
  scoreRow: { flexDirection: 'row', alignItems: 'baseline', gap: 10, marginTop: 4 },
  scoreNum: { fontSize: 40, fontWeight: '900', color: C.greenDk },
  scoreSub: { fontSize: 13, color: C.textSub },
  answerCard: {
    backgroundColor: C.gray50, borderRadius: 10, padding: 10, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  answerHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  answerQ: { fontSize: 12, fontWeight: '800', color: C.textSub },
  badge: { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2 },
  badgeText: { fontSize: 10, fontWeight: '800' },
  answerBody: { fontSize: 13, fontWeight: '700', color: C.text, marginBottom: 6 },
  answerLine: { fontSize: 12, color: C.textHint, marginTop: 2 },
  answerValue: { color: C.text, fontWeight: '600' },
  hintBox: {
    backgroundColor: C.blueLt, borderRadius: 8, padding: 8, marginTop: 8,
    borderLeftWidth: 3, borderLeftColor: C.primary,
  },
  hintHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 },
  hintTitle: { fontSize: 11, fontWeight: '800', color: C.blueDk },
  hintBody: { fontSize: 12, color: C.blueDk, lineHeight: 16 },
})
