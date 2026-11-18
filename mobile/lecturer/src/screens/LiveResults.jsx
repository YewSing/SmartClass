import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, FlatList,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { getQuizAttempts, getQuizQuestionsForLecturer, getQuiz } from '../services/api'
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

const REFRESH_MS = 5000

export default function LiveResults({ navigation, route }) {
  const { showToast } = useLecturer()
  const { quizId, courseId, courseCode, courseName } = (route?.params ?? {})

  const [activeTab, setActiveTab] = useState('attempts') // 'questions' | 'attempts'
  const [attemptFilter, setAttemptFilter] = useState('all') // 'all' | 'graded' | 'needsReview'
  const [attempts, setAttempts] = useState([])
  const [questions, setQuestions] = useState([])
  const [enrolledCount, setEnrolledCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [intervalId, setIntervalId] = useState(null)

  const loadData = useCallback(async () => {
    if (!quizId) return
    try {
      const [attemptList, questionList, quizDetail] = await Promise.all([
        getQuizAttempts(quizId),
        getQuizQuestionsForLecturer(quizId).catch(() => []),
        getQuiz(quizId).catch(() => null),
      ])
      setAttempts(attemptList)
      setQuestions(questionList)
      if (quizDetail?.total_enrolled != null) {
        setEnrolledCount(quizDetail.total_enrolled)
      } else if (attemptList[0]?.total_enrolled != null) {
        setEnrolledCount(attemptList[0].total_enrolled)
      }
      setError(null)
    } catch (e) {
      setError(e.message || 'Could not load quiz data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [quizId])

  useEffect(() => {
    loadData()
    const id = setInterval(loadData, REFRESH_MS)
    setIntervalId(id)
    return () => clearInterval(id)
  }, [loadData])

  const totalEnrolled = enrolledCount || (attempts[0]?.total_enrolled ?? 0)
  const submittedStudents = new Set(
    attempts.filter(a => a.status === 'submitted' || a.auto_submitted).map(a => a.student_id)
  ).size
  const notSubmitted = Math.max(0, totalEnrolled - submittedStudents)

  const started = attempts.filter(a => a.status === 'started').length
  const submitted = attempts.filter(a => a.status === 'submitted').length
  const autoSubmitted = attempts.filter(a => a.auto_submitted).length
  const scored = attempts.filter(a => a.score != null)
  const numericScores = scored
    .map(a => {
      const v = typeof a.score === 'number' ? a.score : parseFloat(String(a.score ?? ''))
      return Number.isFinite(v) ? v : null
    })
    .filter(v => v != null)
  const avg = numericScores.length ? (numericScores.reduce((s, v) => s + v, 0) / numericScores.length).toFixed(0) : '--'

  const gradedAttempts = attempts.filter(a => a.score != null)
  const needsReviewAttempts = attempts.filter(
    a => a.score == null && (a.status === 'submitted' || a.status === 'auto_submitted')
  )

  const statusLabel = (s) => {
    switch (s) {
      case 'started': return 'In progress'
      case 'submitted': return 'Submitted'
      case 'auto_submitted': return 'Auto-submitted'
      default: return s
    }
  }

  const isNeedsReview = (a) => a.score == null && (a.status === 'submitted' || a.auto_submitted)

  const renderItem = ({ item: a }) => (
    <TouchableOpacity
      style={[styles.row, isNeedsReview(a) && styles.rowNeedsReview]}
      onPress={() => navigation.navigate('ResultsClosed', { attemptId: a.attempt_id, quizId })}
    >
      <View style={styles.rowBody}>
        {isNeedsReview(a) && (
          <View style={styles.reviewTagRow}>
            <Ionicons name="alert-circle" size={14} color={C.orangeDk} />
            <Text style={styles.reviewTagText}>Pending review</Text>
          </View>
        )}
        <Text style={styles.rowStudent} numberOfLines={1}>{a.student_name || `Student #${String(a.student_id).slice(-4)}`}</Text>
        <Text style={styles.rowMeta}>
          {statusLabel(a.status)}{a.submitted_at ? ` · submitted` : ''}
        </Text>
      </View>
      <View style={styles.rowRight}>
        <Badge
          variant={
            a.score == null && (a.status === 'submitted' || a.auto_submitted)
              ? 'orange'
              : a.status === 'submitted' || a.auto_submitted
                ? 'green'
                : 'blue'
          }
          dot
        >
          {a.score == null && (a.status === 'submitted' || a.auto_submitted)
            ? 'Needs review'
            : statusLabel(a.status)}
        </Badge>
        {a.score != null ? (
          <Text style={styles.rowScore}>{a.score}%</Text>
        ) : (
          <Text style={styles.rowScore}>--</Text>
        )}
      </View>
    </TouchableOpacity>
  )

  return (
    <View style={styles.flex}>
      <Topbar
        title="Live Results"
        sub={courseCode ? `${courseCode} · ${courseName}` : undefined}
        onBack={() => navigation.goBack()}
        right={
          <TouchableOpacity style={styles.refresh} onPress={() => { setRefreshing(true); loadData() }}>
            <Ionicons name={refreshing ? 'loop-circle' : 'refresh-outline'} size={18} color={C.primary} />
          </TouchableOpacity>
        }
      />

      {/* Category Tabs: Questions vs Student Attempts */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabBtn, activeTab === 'attempts' && styles.tabBtnActive]}
          onPress={() => setActiveTab('attempts')}
        >
          <Ionicons
            name="people-outline"
            size={16}
            color={activeTab === 'attempts' ? C.primary : C.textSub}
          />
          <Text style={[styles.tabBtnText, activeTab === 'attempts' && styles.tabBtnTextActive]}>
            Student Attempts ({attempts.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabBtn, activeTab === 'questions' && styles.tabBtnActive]}
          onPress={() => setActiveTab('questions')}
        >
          <Ionicons
            name="help-circle-outline"
            size={16}
            color={activeTab === 'questions' ? C.primary : C.textSub}
          />
          <Text style={[styles.tabBtnText, activeTab === 'questions' && styles.tabBtnTextActive]}>
            Questions ({questions.length})
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {activeTab === 'attempts' && (
          <>
            {/* Summary */}
            <Section tint="blue" badge="Live results" right={
              <Badge variant={notSubmitted > 0 ? 'orange' : 'green'} dot>{notSubmitted} not submitted</Badge>
            }>
              <View style={styles.summaryRow}>
                <View style={styles.summaryCell}>
                  <Text style={[styles.summaryNum, { color: C.orange }]}>{notSubmitted}</Text>
                  <Text style={styles.summaryLbl}>Not submitted</Text>
                </View>
                <View style={styles.summaryCell}>
                  <Text style={styles.summaryNum}>{started}</Text>
                  <Text style={styles.summaryLbl}>In progress</Text>
                </View>
                <View style={styles.summaryCell}>
                  <Text style={[styles.summaryNum, { color: C.green }]}>{submitted}</Text>
                  <Text style={styles.summaryLbl}>Submitted</Text>
                </View>
                <View style={styles.summaryCell}>
                  <Text style={[styles.summaryNum, { color: C.textSub }]}>{avg}</Text>
                  <Text style={styles.summaryLbl}>Avg score</Text>
                </View>
                <View style={styles.summaryCell}>
                  <Text style={[styles.summaryNum, { color: needsReviewAttempts.length > 0 ? C.orangeDk : C.textSub }]}>{needsReviewAttempts.length}</Text>
                  <Text style={styles.summaryLbl}>Needs review</Text>
                </View>
              </View>
              {autoSubmitted > 0 && (
                <Text style={styles.hint}>{autoSubmitted} attempt{autoSubmitted !== 1 ? 's' : ''} auto-submitted after deadline.</Text>
              )}
            </Section>

            {loading && <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>}

            {!loading && error && (
              <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>
            )}

            {!loading && !error && attempts.length === 0 && (
              <View style={styles.empty}>
                <Ionicons name="people-outline" size={32} color={C.textHint} />
                <Text style={styles.emptyText}>No attempts yet</Text>
                <Text style={styles.emptySub}>Students take the quiz from the student app.</Text>
              </View>
            )}

            {!loading && !error && attempts.length > 0 && (
              <>
                <Text style={styles.listTitlePlain}>Attempts</Text>
                <View style={styles.filterRow}>
                  <TouchableOpacity
                    style={[styles.filterChip, attemptFilter === 'all' && styles.filterChipActive]}
                    onPress={() => setAttemptFilter('all')}
                  >
                    <Text style={[styles.filterChipText, attemptFilter === 'all' && styles.filterChipTextActive]}>
                      All ({attempts.length})
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.filterChip, attemptFilter === 'graded' && styles.filterChipActive]}
                    onPress={() => setAttemptFilter('graded')}
                  >
                    <Text style={[styles.filterChipText, attemptFilter === 'graded' && styles.filterChipTextActive]}>
                      Graded ({gradedAttempts.length})
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.filterChip, attemptFilter === 'needsReview' && styles.filterChipActive]}
                    onPress={() => setAttemptFilter('needsReview')}
                  >
                    <Text style={[styles.filterChipText, attemptFilter === 'needsReview' && styles.filterChipTextActive]}>
                      Needs review ({needsReviewAttempts.length})
                    </Text>
                  </TouchableOpacity>
                </View>
                <FlatList
                  data={
                    attemptFilter === 'graded'
                      ? gradedAttempts
                      : attemptFilter === 'needsReview'
                        ? needsReviewAttempts
                        : attempts
                  }
                  keyExtractor={(_, i) => String(i)}
                  renderItem={renderItem}
                  ItemSeparatorComponent={() => <View style={styles.separator} />}
                  contentContainerStyle={{ paddingBottom: 90 }}
                  style={styles.flex}
                />
              </>
            )}
          </>
        )}

        {activeTab === 'questions' && (
          <>
            {loading && <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>}

            {!loading && questions.length === 0 && (
              <View style={styles.empty}>
                <Ionicons name="help-circle-outline" size={32} color={C.textHint} />
                <Text style={styles.emptyText}>No questions on this quiz</Text>
              </View>
            )}

            {!loading && questions.map((q, idx) => (
              <Section
                key={q.id}
                tint={q.type === 'mcq' ? 'blue' : 'purple'}
                badge={`Q${idx + 1} · ${q.type === 'mcq' ? 'MCQ' : 'Short answer'} · ${q.score ?? 1} pt${q.score !== 1 ? 's' : ''}`}
                right={<Badge variant={q.status === 'approved' ? 'green' : 'gray'}>{q.level}</Badge>}
              >
                <Text style={styles.questionText}>{q.question}</Text>
                {q.type === 'mcq' ? (
                  <View style={styles.optionsList}>
                    {(q.options ?? []).map((opt, i) => {
                      const correctList = (q.correct_answer || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
                      const isCorrect = correctList.includes(opt.trim().toLowerCase())
                      return (
                        <View key={i} style={[styles.optionItem, isCorrect && styles.optionItemCorrect]}>
                          <View style={[styles.letterBadge, isCorrect && styles.letterBadgeCorrect]}>
                            <Text style={[styles.letterBadgeText, isCorrect && { color: '#fff' }]}>
                              {'ABCD'[i] ?? '?'}
                            </Text>
                          </View>
                          <Text style={[styles.optionText, isCorrect && styles.optionTextCorrect]}>
                            {opt}
                          </Text>
                          {isCorrect && (
                            <Ionicons name="checkmark-circle" size={16} color={C.green} style={{ marginLeft: 'auto' }} />
                          )}
                        </View>
                      )
                    })}
                  </View>
                ) : (
                  <View style={styles.idealAnswerBox}>
                    <Text style={styles.idealLabel}>Ideal Answer (Grading Reference):</Text>
                    <Text style={styles.idealText}>{q.suggested_answer || '(No suggested answer recorded)'}</Text>
                  </View>
                )}
                {q.topic ? (
                  <Text style={styles.questionTopic}>Topic: {q.topic}</Text>
                ) : null}
              </Section>
            ))}
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
  section: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  refresh: { padding: 8 },
  summaryCard: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  summaryRow: { flexDirection: 'row', gap: 10 },
  summaryCell: { flex: 1, alignItems: 'center' },
  summaryNum: { fontSize: 22, fontWeight: '800', color: C.text },
  summaryLbl: { fontSize: 11, color: C.textSub, marginTop: 2 },
  hint: { fontSize: 12, color: C.textHint, marginTop: 8 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 40 },
  err: { padding: 16 },
  errText: { fontSize: 13, color: C.red },
  empty: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyText: { fontSize: 15, fontWeight: '700', color: C.text },
  emptySub: { fontSize: 13, color: C.textSub },
  listTitle: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 10, marginBottom: 4 },
  listTitlePlain: { fontSize: 15, fontWeight:'700', color: C.text, marginTop: 10, marginBottom: 8 },
  filterRow: { flexDirection: 'row', gap: 6, marginBottom: 8, flexWrap: 'wrap' },
  filterChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12,
    backgroundColor: C.gray50, borderWidth: 1, borderColor: C.border,
  },
  filterChipActive: { backgroundColor: C.blueLt, borderColor: C.primary },
  filterChipText: { fontSize: 11, color: C.textSub },
  filterChipTextActive: { fontWeight: '700', color: C.primary },
  listSub: { fontSize: 12, color: C.textSub, marginBottom: 8 },
  separator: { height: 1, backgroundColor: C.border, marginHorizontal: 16 },
  tabBar: {
    flexDirection: 'row', backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  tabBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 12, borderBottomWidth: 2, borderBottomColor: 'transparent',
  },
  tabBtnActive: { borderBottomColor: C.primary },
  tabBtnText: { fontSize: 13, fontWeight: '700', color: C.textSub },
  tabBtnTextActive: { color: C.primary },
  questionText: { fontSize: 14, fontWeight: '700', color: C.text, marginBottom: 10, lineHeight: 20 },
  optionsList: { gap: 6, marginBottom: 8 },
  optionItem: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: C.gray50, borderRadius: 8, padding: 8,
    borderWidth: 1, borderColor: C.border,
  },
  optionItemCorrect: { backgroundColor: C.greenLt, borderColor: C.green },
  letterBadge: {
    width: 24, height: 24, borderRadius: 12, backgroundColor: C.gray200,
    alignItems: 'center', justifyContent: 'center',
  },
  letterBadgeCorrect: { backgroundColor: C.green },
  letterBadgeText: { fontSize: 11, fontWeight: '800', color: C.text },
  optionText: { fontSize: 13, color: C.text, flex: 1 },
  optionTextCorrect: { color: C.greenDk, fontWeight: '700' },
  idealAnswerBox: {
    backgroundColor: C.gray50, borderRadius: 8, padding: 10, marginBottom: 8,
    borderLeftWidth: 3, borderLeftColor: C.purple,
  },
  idealLabel: { fontSize: 11, fontWeight: '800', color: C.purple, marginBottom: 4 },
  idealText: { fontSize: 13, color: C.text, lineHeight: 18 },
  questionTopic: { fontSize: 11, color: C.textHint, marginTop: 4 },
  row: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: C.card,
    borderBottomWidth: 1, borderBottomColor: C.border,
  },
  rowNeedsReview: {
    backgroundColor: '#FFF7ED',
    borderColor: C.orangeDk,
    borderWidth: 1,
  },
  reviewTagRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.orangeLt, borderRadius: 8, paddingHorizontal: 8,
    paddingVertical: 4, marginBottom: 6, alignSelf: 'flex-start',
  },
  reviewTagText: { fontSize: 10, fontWeight: '800', color: C.orangeDk },
  rowBody: { flex: 1, marginRight: 10 },
  rowStudent: { fontSize: 14, fontWeight: '700', color: C.text },
  rowMeta: { fontSize: 11, color: C.textHint, marginTop: 2 },
  rowRight: { alignItems: 'flex-end', minWidth: 110 },
  rowScore: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 2 },
  needsReviewLabel: { fontSize: 10, fontWeight: '800', color: C.redDk, marginTop: 2 },
})
