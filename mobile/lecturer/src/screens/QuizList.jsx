import { useState, useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { getClasses } from '../services/api'
import { C } from '../theme'

export default function QuizList({ navigation }) {
  const { state, showToast } = useLecturer()
  const { classes: storedClasses = [] } = state
  const [courses, setCourses] = useState(storedClasses)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getClasses()
      .then(list => { if (!cancelled) { setCourses(list); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [])

  const headerRight = courses.length > 0 ? (
    <View style={styles.headerRight}>
      <TouchableOpacity style={styles.createTopBtn} onPress={() => navigation.navigate('CreateQuiz', { courseId: courses[0].course_id, courseCode: courses[0].code, courseName: courses[0].name })}>
        <Ionicons name="add" size={16} color="#fff" />
        <Text style={styles.createTopBtnText}>Create quiz</Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.createTopBtn} onPress={() => {
        showToast('Saved as draft', 'success')
      }}>
        <Ionicons name="document-text" size={16} color="#fff" />
        <Text style={styles.createTopBtnText}>Draft</Text>
      </TouchableOpacity>
    </View>
  ) : null

  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title="Quiz & Poll" />
        <View style={styles.loading}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Loading courses…</Text>
        </View>
      </View>
    )
  }

  if (error) {
    return (
      <View style={styles.flex}>
        <Topbar title="Quiz & Poll" />
        <View style={styles.empty}>
          <Ionicons name="alert-circle" size={32} color={C.red} />
          <Text style={styles.emptyText}>{error}</Text>
        </View>
      </View>
    )
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Quiz & Poll"
        sub="Create and manage quizzes for your courses"
        right={headerRight}
      />
      {courses.length === 0 && (
        <View style={styles.empty}>
          <Ionicons name="school" size={32} color={C.textHint} />
          <Text style={styles.emptyText}>No courses found</Text>
        </View>
      )}
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.list}>
        {courses.map(course => {
          const typeVariant = course.type === 'LECTURE' ? 'blue' : 'green'
          const typeText = course.type === 'LECTURE' ? 'Lecture' : (course.label ?? 'Tutorial')
          return (
            <TouchableOpacity
              key={course.id}
              style={styles.courseCard}
              onPress={() => navigation.navigate('CreateQuiz', {
                courseId: course.course_id, courseCode: course.code, courseName: course.name,
              })}
            >
              <View style={styles.cardTop}>
                <View style={styles.cardBody}>
                  <View style={styles.codeRow}>
                    <Text style={styles.courseCode}>{course.code}</Text>
                    <Badge variant={typeVariant}>{typeText}</Badge>
                  </View>
                  <Text style={styles.courseName}>{course.name}</Text>
                  {course.day_of_week && (
                    <Text style={styles.courseMeta}>
                      {course.day_of_week} {course.start_time}–{course.end_time}{course.room ? ` · ${course.room}` : ''}
                    </Text>
                  )}
                </View>
                <Badge variant="blue">{course.enrolled_count != null ? course.enrolled_count : 0} students</Badge>
              </View>
            </TouchableOpacity>
          )
        })}
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  loadingText: { fontSize: 14, color: C.textSub },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 10 },
  emptyText: { fontSize: 14, color: C.textSub },
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
  courseCard: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginHorizontal: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.border,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 8,
  },
  cardBody: { flex: 1 },
  codeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 2,
  },
  courseCode: {
    fontSize: 15,
    fontWeight: '800',
    color: C.primary,
  },
  courseName: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
    marginTop: 2,
  },
  courseMeta: {
    fontSize: 11,
    color: C.textHint,
    marginTop: 4,
  },
})
