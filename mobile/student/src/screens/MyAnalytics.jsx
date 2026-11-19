import { useState, useCallback } from 'react'
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useFocusEffect } from '@react-navigation/native'
import { getMyAnalytics } from '../services/api'
import { C } from '../theme'

function rateColor(rate) {
  if (rate == null) return C.textHint
  if (rate >= 80) return C.green
  if (rate >= 60) return C.orange
  return C.red
}

function rateLabel(rate) {
  if (rate == null) return 'No data yet'
  if (rate >= 80) return 'Great attendance'
  if (rate >= 60) return 'Getting close — push a little more'
  return 'Attendance is low — talk to your lecturer'
}

// Tinted insight card: icon + big number + caption.
function InsightCard({ icon, bg, color, value, label }) {
  return (
    <View style={[styles.insightCard, { backgroundColor: bg }]}>
      <Ionicons name={icon} size={16} color={color} />
      <Text style={[styles.insightValue, { color }]}>{value}</Text>
      <Text style={[styles.insightLabel, { color }]}>{label}</Text>
    </View>
  )
}

// Horizontal progress bar with the score on the right.
function ScoreBar({ label, score, right }) {
  const color = rateColor(score)
  const pct = Math.max(0, Math.min(100, score ?? 0))
  return (
    <View style={styles.scoreRow}>
      <Text style={styles.scoreLabel}>{label}</Text>
      <View style={styles.scoreTrack}>
        <View style={[styles.scoreFill, { width: `${pct}%`, backgroundColor: color }]} />
      </View>
      <Text style={[styles.scoreValue, { color }]}>{right}</Text>
    </View>
  )
}

// Colored action-count chip.
function Chip({ value, label }) {
  return (
    <View style={styles.chip}>
      <Text style={styles.chipNum}>{value}</Text>
      <Text style={styles.chipLbl}>{label}</Text>
    </View>
  )
}

function CourseCard({ course }) {
  const a = course.attendance ?? {}
  const p = course.participation ?? {}
  const q = course.quizzes ?? {}
  const title = course.course_code ?? `Course #${course.course_id}`
  const graded = (q.trend ?? []).filter(t => t.score != null)
  const bestQuiz = graded.reduce((b, t) => (!b || t.score > b.score ? t : b), null)
  return (
    <View style={styles.card}>
      <View style={styles.cardHead}>
        <View style={styles.cardBadge}>
          <Text style={styles.cardBadgeText}>{title}</Text>
        </View>
        <RatePill rate={a.rate} />
      </View>
      {course.course_name ? (
        <Text style={styles.cardSub} numberOfLines={1}>{course.course_name}</Text>
      ) : null}

      <View style={styles.barSection}>
        <ScoreBar label="Attendance" right={a.rate != null ? `${Math.round(a.rate)}%` : '—'} score={a.rate} />
        <ScoreBar label="Quiz average" right={q.average_score != null ? `${Math.round(q.average_score)}%` : '—'} score={q.average_score} />
      </View>

      <View style={styles.chipRow}>
        <Chip value={p.frequency ?? 0} label="Participation" />
        <Chip value={p.questions ?? 0} label="Questions" />
        <Chip value={p.votes ?? 0} label="Votes" />
        <Chip value={p.reactions ?? 0} label="Reactions" />
        <Chip value={p.idu_signals ?? 0} label="IDU" />
      </View>

      {bestQuiz && bestQuiz.score != null && (
        <View style={styles.bestQuizRow}>
          <Ionicons name="trophy-outline" size={13} color={C.greenDk} />
          <Text style={styles.bestQuizText} numberOfLines={1}>
            Best quiz: {bestQuiz.title} · {Math.round(bestQuiz.score)}%
          </Text>
        </View>
      )}
    </View>
  )
}

function RatePill({ rate }) {
  const color = rateColor(rate)
  return (
    <View style={[styles.ratePill, { backgroundColor: color + '1A' }]}>
      <Text style={[styles.ratePillText, { color }]}>{rateLabel(rate)}</Text>
    </View>
  )
}

export default function MyAnalytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const insets = useSafeAreaInsets()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await getMyAnalytics())
    } catch (e) {
      setError(e.message || 'Could not load your analytics.')
    } finally {
      setLoading(false)
    }
  }, [])

  useFocusEffect(useCallback(() => { load() }, [load]))

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }, [load])

  const courses = data?.courses ?? []
  const totalParticipation = courses.reduce((s, c) => s + (c.participation?.frequency ?? 0), 0)
  const quizAverages = courses.map(c => c.quizzes?.average_score).filter(s => s != null)
  const quizAvg = quizAverages.length
    ? quizAverages.reduce((s, x) => s + x, 0) / quizAverages.length
    : null
  const weakest = courses.reduce((b, c) => (
    c.attendance?.rate != null && (!b || c.attendance.rate < b.attendance.rate) ? c : b
  ), null)
  const overall = data?.overall_attendance_rate

  return (
    <View style={[styles.flex, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>My Analytics</Text>
        <Text style={styles.headerSub}>Your attendance, participation and quiz performance</Text>
      </View>

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {loading ? (
          <View style={styles.centered}><Text style={styles.hintText}>Loading…</Text></View>
        ) : error ? (
          <View style={styles.centered}><Text style={styles.hintText}>{error}</Text></View>
        ) : !data ? (
          <View style={styles.centered}><Text style={styles.hintText}>No data available</Text></View>
        ) : (
          <>
            {/* Overall attendance hero */}
            <View style={[styles.heroCard, overall != null && overall < 60 && { borderColor: C.redLt }]}>
              <Text style={[styles.heroValue, { color: rateColor(overall) }]}>
                {overall != null ? `${overall.toFixed(1)}%` : '—'}
              </Text>
              <Text style={styles.heroTitle}>Overall attendance</Text>
              <Text style={styles.heroSub}>{rateLabel(overall)}</Text>
            </View>

            {/* Insight cards */}
            <View style={styles.insightRow}>
              <InsightCard icon="people-outline" bg={C.blueLt} color={C.blueDk} value={courses.length} label="Courses" />
              <InsightCard icon="chatbubbles-outline" bg={C.greenLt} color={C.greenDk} value={totalParticipation} label="Interactions" />
              <InsightCard icon="help-circle-outline" bg={C.purpleLt} color={C.purple} value={quizAvg != null ? `${Math.round(quizAvg)}%` : '—'} label="Quiz average" />
            </View>

            {/* Weakest-course nudge */}
            {weakest && overall != null && overall < 80 && (
              <View style={styles.nudgeCard}>
                <Ionicons name="warning-outline" size={16} color={C.orangeDk} />
                <Text style={styles.nudgeText} numberOfLines={1}>
                  {weakest.course_code} has your lowest attendance ({Math.round(weakest.attendance.rate)}%) — every class counts.
                </Text>
              </View>
            )}

            {courses.length === 0 ? (
              <View style={styles.card}>
                <Text style={styles.hintText}>No course data yet.</Text>
              </View>
            ) : (
              courses.map(c => <CourseCard key={c.course_id} course={c} />)
            )}
          </>
        )}
        <View style={{ height: 20 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  header: {
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 10,
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: C.text },
  headerSub: { fontSize: 12, color: C.textSub, marginTop: 2 },
  // Overall attendance hero
  heroCard: {
    backgroundColor: C.card,
    margin: 16,
    marginBottom: 8,
    padding: 18,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
  },
  heroValue: { fontSize: 34, fontWeight: '800' },
  heroTitle: { fontSize: 14, fontWeight: '700', color: C.text, marginTop: 2 },
  heroSub: { fontSize: 12, color: C.textSub, marginTop: 3, textAlign: 'center' },
  // Insight cards
  insightRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 10,
    gap: 10,
  },
  insightCard: {
    flex: 1,
    borderRadius: 12,
    padding: 12,
    gap: 2,
  },
  insightValue: { fontSize: 18, fontWeight: '800' },
  insightLabel: { fontSize: 10, fontWeight: '600', opacity: 0.9 },
  // Weakest-course nudge
  nudgeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.orangeLt,
    marginHorizontal: 16,
    marginTop: 10,
    padding: 10,
    borderRadius: 10,
  },
  nudgeText: { flex: 1, fontSize: 12, color: C.orangeDk, fontWeight: '600' },
  // Course cards
  card: {
    backgroundColor: C.card,
    borderRadius: 14,
    margin: 16,
    marginTop: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  cardHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  cardBadge: {
    backgroundColor: C.blueLt,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  cardBadgeText: { fontSize: 12, fontWeight: '800', color: C.primary },
  cardSub: { fontSize: 12, color: C.textSub, marginTop: 4, marginBottom: 8 },
  barSection: { marginTop: 8, gap: 4 },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 4,
  },
  scoreLabel: { fontSize: 12, color: C.textSub, width: 92 },
  scoreTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: C.gray100 ?? '#F3F4F6',
    overflow: 'hidden',
  },
  scoreFill: { height: '100%', borderRadius: 4 },
  scoreValue: { fontSize: 12, fontWeight: '800', width: 34, textAlign: 'right' },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 10,
  },
  chip: {
    backgroundColor: '#F8FAFC',
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: C.border,
  },
  chipNum: { fontSize: 12, fontWeight: '800', color: C.text },
  chipLbl: { fontSize: 9, color: C.textSub },
  bestQuizRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    backgroundColor: '#F0FDF4',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  bestQuizText: { flex: 1, fontSize: 11, color: C.greenDk, fontWeight: '600' },
  ratePill: {
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  ratePillText: { fontSize: 10, fontWeight: '800' },
  centered: { alignItems: 'center', padding: 40 },
  hintText: { fontSize: 13, color: C.textHint, textAlign: 'center' },
})
