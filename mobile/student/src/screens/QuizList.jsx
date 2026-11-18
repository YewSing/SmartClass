import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useStudent } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import { getStudentQuizzes, getEnrolledClasses } from '../services/api'
import { C } from '../theme'

/** Section card in the participation style: colored title chip (S29 pattern). */
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

function statusInfo(quiz) {
  const now = new Date()
  const closedByTime = quiz.closes_at && new Date(quiz.closes_at) < now
  if (quiz.status !== 'published') return { label: 'Closed', dot: C.gray500, text: C.textHint }
  if (closedByTime) return { label: 'Closed', dot: C.gray500, text: C.textHint }
  if (quiz.opens_at && new Date(quiz.opens_at) > now) return { label: 'Not open yet', dot: C.orange, text: C.orangeDk }
  if (quiz.attempts_used >= quiz.attempts_allowed) return { label: 'Attempted', dot: C.blueDk, text: C.blueDk }
  return { label: 'Open', dot: C.green, text: C.greenDk }
}

export default function QuizList({ navigation }) {
  const { showToast } = useStudent()
  const [quizzes, setQuizzes] = useState([])
  const [classMap, setClassMap] = useState({})
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const [list, classes] = await Promise.all([getStudentQuizzes(), getEnrolledClasses()])
      const map = {}
      for (const c of classes) {
        if (c.course_id != null) map[c.course_id] = c
        if (c.id != null && !map[c.id]) map[c.id] = c
      }
      setClassMap(map)
      setQuizzes(list)
      setError(null)
    } catch (e) {
      setError(e.message || 'Could not load quizzes')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useFocusEffect(
    useCallback(() => {
      load()
    }, [load])
  )

  const openQuiz = (quiz) => {
    const cls = classMap[quiz.course_id] ?? {}
    if (quiz.attempt_id && quiz.attempts_used >= quiz.attempts_allowed) {
      navigation.navigate('QuizResult', { attemptId: quiz.attempt_id, quizTitle: quiz.title })
      return
    }
    navigation.navigate('TakeQuiz', {
      quiz, courseCode: cls.code, courseName: cls.name,
    })
  }

  const renderItem = (quiz) => {
    const cls = classMap[quiz.course_id] ?? {}
    const st = statusInfo(quiz)
    return (
      <TouchableOpacity key={quiz.id} style={styles.quizCard} onPress={() => openQuiz(quiz)} testID={`student-quiz-${quiz.id}`}>
        <View style={{ flex: 1 }}>
          <View style={styles.titleRow}>
            <Text style={styles.quizTitle} numberOfLines={1}>{quiz.title || 'Untitled quiz'}</Text>
            <View style={styles.pill}>
              <View style={[styles.pillDot, { backgroundColor: st.dot }]} />
              <Text style={[styles.pillText, { color: st.text }]}>{st.label}</Text>
            </View>
          </View>
          <Text style={styles.quizMeta}>
            {cls.code ?? `Course #${quiz.course_id}`}
            {quiz.time_limit_minutes ? ` · ${quiz.time_limit_minutes} min` : ''}
            {` · ${quiz.attempts_used}/${quiz.attempts_allowed} attempt${quiz.attempts_allowed !== 1 ? 's' : ''}`}
          </Text>
          {quiz.closes_at && (
            <Text style={styles.quizMeta}>
              until {new Date(quiz.closes_at).toLocaleDateString([], { day: 'numeric', month: 'short' })}
              {` ${new Date(quiz.closes_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
            </Text>
          )}
        </View>
        <Ionicons name="chevron-forward" size={16} color={C.textHint} />
      </TouchableOpacity>
    )
  }

  const open = quizzes.filter(q => statusInfo(q).label === 'Open')
  const other = quizzes.filter(q => statusInfo(q).label !== 'Open')

  // Group earlier & closed quizzes by course
  const otherByCourse = {}
  for (const q of other) {
    const cid = q.course_id
    if (!otherByCourse[cid]) otherByCourse[cid] = []
    otherByCourse[cid].push(q)
  }

  const courseIds = Object.keys(otherByCourse)
  const tints = ['purple', 'blue', 'orange', 'yellow', 'gray']

  return (
    <View style={styles.flex}>
      <Topbar title="Quiz" sub="Quizzes your lecturers published" />
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load() }} />}
      >
        {loading && <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>}
        {!loading && error && <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>}
        {!loading && !error && quizzes.length === 0 && (
          <View style={styles.empty}>
            <Ionicons name="help-circle-outline" size={32} color={C.textHint} />
            <Text style={styles.emptyText}>No quizzes yet</Text>
          </View>
        )}
        {!loading && !error && open.length > 0 && (
          <Section tint="green" badge="Open now" right={<Text style={styles.counter}>{open.length} to do</Text>}>
            {open.map(renderItem)}
          </Section>
        )}
        {!loading && !error && courseIds.length > 0 && (
          <>
            <Text style={styles.groupHeading}>Earlier & closed</Text>
            {courseIds.map((cid, i) => {
              const qList = otherByCourse[cid]
              const cls = classMap[cid] ?? {}
              const badgeLabel = cls.code ?? `Course #${cid}`
              return (
                <Section
                  key={cid}
                  tint={tints[i % tints.length]}
                  badge={badgeLabel}
                  right={<Text style={styles.counter}>{qList.length} quiz{qList.length !== 1 ? 'zes' : ''}</Text>}
                >
                  {cls.name && <Text style={styles.courseSubtitle}>{cls.name}</Text>}
                  {qList.map(renderItem)}
                </Section>
              )
            })}
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
  empty: { alignItems: 'center', paddingVertical: 60, gap: 10 },
  emptyText: { fontSize: 14, color: C.textSub },
  section: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  counter: { fontSize: 11, color: C.textHint, fontWeight: '600' },
  groupHeading: { fontSize: 14, fontWeight: '800', color: C.textSub, marginTop: 8, marginBottom: 8 },
  courseSubtitle: { fontSize: 13, fontWeight: '700', color: C.text, marginBottom: 6 },
  quizCard: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: C.gray50, borderRadius: 10, padding: 12, marginTop: 6,
    borderWidth: 1, borderColor: C.border,
  },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  quizTitle: { fontSize: 14, fontWeight: '700', color: C.text, flexShrink: 1 },
  quizMeta: { fontSize: 11, color: C.textHint, marginTop: 2 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: C.card, borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2 },
  pillDot: { width: 6, height: 6, borderRadius: 3 },
  pillText: { fontSize: 10, fontWeight: '700' },
})
