import { useCallback, useEffect, useRef, useState } from 'react'
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Alert, RefreshControl,
} from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { useStudent } from '../context/StudentContext'
import { getAssistantCourses, getChatSessions, deleteChatSession } from '../services/api'
import { C } from '../theme'

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs} h ago`
  return new Date(iso).toLocaleDateString('en-MY', { day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' })
}

export default function Assistant({ navigation }) {
  const { showToast } = useStudent()
  const [courses, setCourses] = useState(null)
  const [courseId, setCourseId] = useState(null)
  const [sessions, setSessions] = useState([])
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const chipRow = useRef(null)
  const chipX = useRef({})

  const course = courses?.find(c => c.course_id === courseId) ?? null

  const loadCourses = useCallback(async () => {
    try {
      const list = await getAssistantCourses()
      setCourses(list)
      // Default to the first course that has materials to answer from
      setCourseId(prev => prev ?? (list.find(c => c.indexed_materials > 0) ?? list[0])?.course_id ?? null)
    } catch (e) {
      setCourses([])
      showToast(e.message, 'error')
    }
  }, [showToast])

  const loadSessions = useCallback(async () => {
    if (!courseId) return
    setLoadingSessions(true)
    try {
      setSessions(await getChatSessions(courseId))
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoadingSessions(false)
    }
  }, [courseId, showToast])

  useEffect(() => { loadCourses() }, [loadCourses])

  // Keep the selected course chip on screen (the default one may be far along the row)
  const scrollToChip = (id) => {
    const x = chipX.current[id]
    if (x !== undefined) chipRow.current?.scrollTo({ x: Math.max(0, x - 16), animated: true })
  }
  useEffect(() => { scrollToChip(courseId) }, [courseId])
  // Reload when coming back from a chat, so new chats and titles show up
  useFocusEffect(useCallback(() => { loadSessions() }, [loadSessions]))

  const onRefresh = async () => {
    setRefreshing(true)
    await Promise.all([loadCourses(), loadSessions()])
    setRefreshing(false)
  }

  const openChat = (session) => navigation.navigate('AssistantChat', {
    courseId: course.course_id,
    courseCode: course.code,
    sessionId: session?.id ?? null,
    title: session?.title ?? null,
  })

  const confirmDelete = (session) => {
    Alert.alert('Delete chat?', session.title || 'Untitled chat', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await deleteChatSession(session.id)
            setSessions(list => list.filter(s => s.id !== session.id))
          } catch (e) { showToast(e.message, 'error') }
        },
      },
    ])
  }

  if (courses === null) {
    return (
      <View style={styles.screen}>
        <Topbar title="AI Assistant" sub="Ask about your course materials" />
        <ActivityIndicator style={{ marginTop: 40 }} color={C.primary} />
      </View>
    )
  }

  return (
    <View style={styles.screen}>
      <Topbar title="AI Assistant" sub="Ask about your course materials" />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {courses.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="school-outline" size={36} color={C.textHint} />
            <Text style={styles.emptyText}>You are not enrolled in any course yet.</Text>
          </View>
        ) : (
          <>
            <Text style={styles.sectionLabel}>Course</Text>
            <ScrollView
              ref={chipRow}
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chips}
            >
              {courses.map(c => {
                const active = c.course_id === courseId
                return (
                  <TouchableOpacity
                    key={c.course_id}
                    onLayout={e => {
                      chipX.current[c.course_id] = e.nativeEvent.layout.x
                      if (active) scrollToChip(c.course_id)
                    }}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => setCourseId(c.course_id)}
                  >
                    <Text style={[styles.chipText, active && styles.chipTextActive]}>{c.code}</Text>
                  </TouchableOpacity>
                )
              })}
            </ScrollView>

            {course ? (
              <View style={styles.courseCard}>
                <Text style={styles.courseName}>{course.code} · {course.name}</Text>
                <Text style={styles.courseMeta}>
                  {course.indexed_materials > 0
                    ? `${course.indexed_materials} materials from SPeCTRUM`
                    : 'No materials yet, so answers will be general knowledge only'}
                </Text>
                <TouchableOpacity style={styles.newBtn} onPress={() => openChat(null)}>
                  <Ionicons name="add" size={18} color="#fff" style={{ marginRight: 6 }} />
                  <Text style={styles.newBtnText}>New chat</Text>
                </TouchableOpacity>
              </View>
            ) : null}

            <Text style={styles.sectionLabel}>Your chats</Text>
            {loadingSessions && sessions.length === 0 ? (
              <ActivityIndicator style={{ marginTop: 16 }} color={C.primary} />
            ) : sessions.length === 0 ? (
              <Text style={styles.noChats}>No chats for this course yet.</Text>
            ) : (
              sessions.map(s => (
                <TouchableOpacity
                  key={s.id}
                  style={styles.sessionRow}
                  onPress={() => openChat(s)}
                  onLongPress={() => confirmDelete(s)}
                >
                  <Ionicons name="chatbubble-ellipses-outline" size={20} color={C.primary} />
                  <View style={styles.sessionText}>
                    <Text style={styles.sessionTitle} numberOfLines={1}>{s.title || 'Untitled chat'}</Text>
                    <Text style={styles.sessionMeta}>{timeAgo(s.updated_at)}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={C.textHint} />
                </TouchableOpacity>
              ))
            )}
            {sessions.length > 0 ? <Text style={styles.hint}>Long-press a chat to delete it.</Text> : null}
          </>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32 },
  sectionLabel: {
    fontSize: 12, fontWeight: '700', color: C.textSub, textTransform: 'uppercase',
    letterSpacing: 0.5, marginBottom: 8, marginTop: 4,
  },
  chips: { gap: 8, paddingBottom: 12 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 18,
    backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
  },
  chipActive: { backgroundColor: C.primary, borderColor: C.primary },
  chipText: { fontSize: 13, fontWeight: '600', color: C.text },
  chipTextActive: { color: '#fff' },
  courseCard: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 18,
    borderWidth: 1, borderColor: C.border,
  },
  courseName: { fontSize: 15, fontWeight: '700', color: C.text },
  courseMeta: { fontSize: 12, color: C.textSub, marginTop: 4, marginBottom: 12 },
  newBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 11,
  },
  newBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  noChats: { fontSize: 13, color: C.textHint, marginTop: 4 },
  sessionRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: C.card, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  sessionText: { flex: 1 },
  sessionTitle: { fontSize: 14, fontWeight: '600', color: C.text },
  sessionMeta: { fontSize: 12, color: C.textHint, marginTop: 2 },
  hint: { fontSize: 11, color: C.textHint, textAlign: 'center', marginTop: 6 },
  empty: { alignItems: 'center', marginTop: 60, gap: 10 },
  emptyText: { fontSize: 14, color: C.textSub },
})
