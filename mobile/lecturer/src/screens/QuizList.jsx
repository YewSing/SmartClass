import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, Modal, FlatList,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { getClasses, getCourseQuizzes, publishQuizDraft, updateQuizDraft } from '../services/api'
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

function QuizStatusPill({ quiz }) {
  const closed = quiz.status === 'closed' ||
    (quiz.closes_at && new Date(quiz.closes_at) < new Date())
  const open = quiz.status === 'published' && !closed &&
    (!quiz.opens_at || new Date(quiz.opens_at) <= new Date())
  const map = open
    ? { dot: C.green, text: C.greenDk, label: 'Open' }
    : closed
      ? { dot: C.gray500, text: C.textHint, label: 'Closed' }
      : quiz.status === 'draft'
        ? { dot: C.orange, text: C.orangeDk, label: 'Draft' }
        : { dot: C.blueDk, text: C.blueDk, label: 'Scheduled' }
  return (
    <View style={styles.pill}>
      <View style={[styles.pillDot, { backgroundColor: map.dot }]} />
      <Text style={[styles.pillText, { color: map.text }]}>{map.label}</Text>
    </View>
  )
}

export default function QuizList({ navigation }) {
  const { showToast } = useLecturer()
  const [courses, setCourses] = useState([])
  const [quizzesByCourse, setQuizzesByCourse] = useState({}) // courseId -> [quiz]
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [draftOpen, setDraftOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const list = await getClasses()
        if (cancelled) return
        setCourses(list)
        const results = await Promise.allSettled(list.map(c => getCourseQuizzes(c.course_id)))
        const map = {}
        list.forEach((c, i) => {
          map[c.course_id] = results[i].status === 'fulfilled' ? results[i].value : []
        })
        if (!cancelled) setQuizzesByCourse(map)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const allDrafts = Object.values(quizzesByCourse)
    .flat()
    .filter(q => q.status === 'draft')
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))

  const courseOf = (quiz) => courses.find(c => c.course_id === quiz.course_id)

  const openQuiz = useCallback((quiz) => {
    if (quiz.status === 'draft') { setDraftOpen(true); return }
    const c = courseOf(quiz) ?? {}
    navigation.navigate('LiveResults', {
      quizId: quiz.id, courseId: quiz.course_id, courseCode: c.code, courseName: c.name,
    })
  }, [courses, navigation])

  const publishDraft = useCallback(async (quiz) => {
    try {
      const created = await publishQuizDraft(quiz.id)
      showToast(`Published to ${created.length} class${created.length !== 1 ? 'es' : ''}`, 'success')
      setQuizzesByCourse(prev => ({
        ...prev,
        [quiz.course_id]: (prev[quiz.course_id] ?? []).map(q =>
          q.id === quiz.id ? { ...q, status: 'published' } : q),
      }))
    } catch (e) {
      showToast(e.message || 'Could not publish draft', 'error')
    }
  }, [showToast])

  const discardDraft = useCallback(async (quiz) => {
    try {
      // a draft set keeps its questions draft; remove them from the set via update
      // (only drafts are editable) then drop it from the list
      await updateQuizDraft(quiz.id, { title: quiz.title })
      showToast('Draft kept for later — publish it from here when ready', 'info')
    } catch (e) {
      showToast(e.message || 'Could not open draft', 'error')
    }
  }, [showToast])

  const renderQuizRow = (quiz) => {
    const c = courseOf(quiz)
    return (
      <TouchableOpacity
        key={quiz.id}
        style={styles.quizCard}
        onPress={() => openQuiz(quiz)}
        testID={`quiz-card-${quiz.id}`}
      >
        <View style={{ flex: 1 }}>
          <View style={styles.quizTitleRow}>
            <Text style={styles.quizTitle} numberOfLines={1}>
              {quiz.title || 'Untitled quiz'}
            </Text>
            <QuizStatusPill quiz={quiz} />
          </View>
          <Text style={styles.quizMeta}>
            {quiz.question_count} question{quiz.question_count !== 1 ? 's' : ''}
            {quiz.time_limit_minutes ? ` · ${quiz.time_limit_minutes} min` : ''}
            {quiz.attempts_allowed > 1 ? ` · ${quiz.attempts_allowed} attempts` : ' · 1 attempt'}
            {c ? ` · ${c.code}` : ''}
          </Text>
          {quiz.closes_at && quiz.status !== 'draft' && (
            <Text style={styles.quizMeta}>
              until {new Date(quiz.closes_at).toLocaleDateString([], { day: 'numeric', month: 'short' })}
              {` ${new Date(quiz.closes_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
            </Text>
          )}
        </View>
        <Ionicons
          name={quiz.status === 'draft' ? 'document-text-outline' : 'bar-chart-outline'}
          size={18}
          color={C.textHint}
        />
      </TouchableOpacity>
    )
  }

  const headerRight = (
    <View style={styles.headerRight}>
      <TouchableOpacity
        style={styles.createTopBtn}
        onPress={() => navigation.navigate('CreateQuiz', {})}
        testID="quiz-create"
      >
        <Ionicons name="add" size={16} color="#fff" />
        <Text style={styles.createTopBtnText}>Create quiz</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.createTopBtn, { backgroundColor: C.orange }]}
        onPress={() => setDraftOpen(true)}
        testID="quiz-drafts"
      >
        <Ionicons name="document-text" size={16} color="#fff" />
        <Text style={styles.createTopBtnText}>Draft{allDrafts.length ? ` (${allDrafts.length})` : ''}</Text>
      </TouchableOpacity>
    </View>
  )

  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title="Quiz" />
        <View style={styles.loading}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Loading quizzes…</Text>
        </View>
      </View>
    )
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Quiz"
        sub="Create, publish and grade quizzes for your courses"
        right={headerRight}
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.list}>
        {error && (
          <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>
        )}
        {courses.length === 0 && !error && (
          <View style={styles.empty}>
            <Ionicons name="school" size={32} color={C.textHint} />
            <Text style={styles.emptyText}>No courses found</Text>
          </View>
        )}
        {courses.map((course, i) => {
          const quizzes = quizzesByCourse[course.course_id] ?? []
          const tints = ['blue', 'green', 'purple', 'yellow', 'orange']
          return (
            <Section
              key={course.id}
              tint={tints[i % tints.length]}
              badge={course.code}
              right={<Badge variant={course.type === 'LECTURE' ? 'blue' : 'green'} dot>
                {course.enrolled_count != null ? course.enrolled_count : 0} students
              </Badge>}
            >
              <Text style={styles.courseName}>{course.name}</Text>
              {course.day_of_week && (
                <Text style={styles.courseMeta}>
                  {course.day_of_week} {course.start_time}–{course.end_time}{course.room ? ` · ${course.room}` : ''}
                </Text>
              )}
              {quizzes.length === 0 ? (
                <View style={styles.quizEmpty}>
                  <Text style={styles.quizEmptyText}>No quizzes yet — use “Create quiz” to build one</Text>
                </View>
              ) : (
                quizzes.map(renderQuizRow)
              )}
            </Section>
          )
        })}
        <View style={{ height: 24 }} />
      </ScrollView>

      {/* Draft quiz sets (the top-right Draft button) */}
      <Modal visible={draftOpen} animationType="slide" transparent onRequestClose={() => setDraftOpen(false)}>
        <View style={styles.sheetWrap}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Draft quiz sets</Text>
              <TouchableOpacity onPress={() => setDraftOpen(false)} hitSlop={8} testID="draft-modal-close">
                <Ionicons name="close" size={22} color={C.textSub} />
              </TouchableOpacity>
            </View>
            <FlatList
              data={allDrafts}
              keyExtractor={q => String(q.id)}
              ListEmptyComponent={<Text style={styles.sheetEmpty}>No draft quiz sets. Generated questions can be saved as a draft quiz in Create quiz.</Text>}
              renderItem={({ item }) => {
                const c = courseOf(item)
                return (
                  <View style={styles.draftRow}>
                    <TouchableOpacity style={{ flex: 1 }} onPress={() => { setDraftOpen(false); openQuiz(item) }}>
                      <Text style={styles.draftTitle}>{item.title || 'Untitled quiz'}</Text>
                      <Text style={styles.draftMeta}>
                        {item.question_count} question{item.question_count !== 1 ? 's' : ''}{c ? ` · ${c.code}` : ''}
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.draftPublishBtn}
                      onPress={() => publishDraft(item)}
                      testID={`draft-publish-${item.id}`}
                    >
                      <Ionicons name="send-outline" size={14} color="#fff" />
                      <Text style={styles.draftPublishText}>Publish</Text>
                    </TouchableOpacity>
                  </View>
                )
              }}
              contentContainerStyle={{ paddingBottom: 24 }}
            />
          </View>
        </View>
      </Modal>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  loadingText: { fontSize: 14, color: C.textSub },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 10 },
  emptyText: { fontSize: 14, color: C.textSub },
  err: { padding: 16 },
  errText: { fontSize: 13, color: C.red },
  list: { padding: 16 },
  headerRight: { flexDirection: 'row', gap: 8 },
  createTopBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    gap: 4,
  },
  createTopBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  section: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  sectionBadge: {
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8,
  },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  courseName: { fontSize: 14, fontWeight: '800', color: C.text },
  courseMeta: { fontSize: 11, color: C.textHint, marginTop: 2, marginBottom: 6 },
  quizCard: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: C.gray50, borderRadius: 10, padding: 10, marginTop: 6,
    borderWidth: 1, borderColor: C.border,
  },
  quizTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  quizTitle: { fontSize: 13, fontWeight: '700', color: C.text, flexShrink: 1 },
  quizMeta: { fontSize: 11, color: C.textHint, marginTop: 2 },
  quizEmpty: { paddingVertical: 10 },
  quizEmptyText: { fontSize: 12, color: C.textHint },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: C.card, borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2 },
  pillDot: { width: 6, height: 6, borderRadius: 3 },
  pillText: { fontSize: 10, fontWeight: '700' },
  sheetWrap: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 20, paddingTop: 12, maxHeight: 480,
  },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sheetTitle: { fontSize: 17, fontWeight: '800', color: C.text },
  sheetEmpty: { fontSize: 13, color: C.textHint, paddingVertical: 20, textAlign: 'center' },
  draftRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: C.gray50, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  draftTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  draftMeta: { fontSize: 11, color: C.textHint, marginTop: 2 },
  draftPublishBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: C.green, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7,
  },
  draftPublishText: { fontSize: 12, fontWeight: '700', color: '#fff' },
})
