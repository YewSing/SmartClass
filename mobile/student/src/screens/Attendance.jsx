import { useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import Badge from '../components/Badge'
import { STATUSES, statusInfo } from '../services/attendance'
import { C } from '../theme'

const BADGE_COLORS = {
  green:  { bg: C.greenLt,  fg: C.green },
  yellow: { bg: C.yellowLt, fg: C.yellowDk },
  blue:   { bg: C.blueLt,   fg: C.primary },
  red:    { bg: C.redLt,    fg: C.red },
  gray:   { bg: C.gray100,  fg: C.gray500 },
}

export default function Attendance({ navigation }) {
  const { state, loadAttendanceCourses } = useStudent()
  const { attendanceCourses, attendanceError } = state
  const insets = useSafeAreaInsets()
  const [collapsed, setCollapsed] = useState({})
  const [activeFilter, setActiveFilter] = useState('All')
  const [refreshing, setRefreshing] = useState(false)

  useFocusEffect(useCallback(() => { loadAttendanceCourses() }, [loadAttendanceCourses]))

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadAttendanceCourses()
    setRefreshing(false)
  }, [loadAttendanceCourses])

  const courses = attendanceCourses ?? []
  const filters = ['All', ...courses.map(c => c.code)]
  const visibleCourses = activeFilter === 'All' ? courses : courses.filter(c => c.code === activeFilter)
  const toggleCourse = (code) => setCollapsed(prev => ({ ...prev, [code]: !prev[code] }))

  const loading = attendanceCourses === null && !attendanceError

  return (
    <View style={styles.flex}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <Text style={styles.headerTitle}>My Attendance</Text>
        <Text style={styles.headerSub}>Rate per course · Late counts as attended, Excused isn't counted</Text>
      </View>

      {/* Filter pills */}
      <View style={styles.filterRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterContent}>
          {filters.map(f => (
            <TouchableOpacity
              key={f}
              style={[styles.pill, activeFilter === f && styles.pillActive]}
              onPress={() => setActiveFilter(f)}
            >
              <Text style={[styles.pillText, activeFilter === f && styles.pillTextActive]}>{f}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {loading ? (
          <View style={styles.empty}>
            <ActivityIndicator color={C.primary} />
          </View>
        ) : attendanceCourses === null && attendanceError ? (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>Couldn't load your attendance. Pull down to try again.</Text>
          </View>
        ) : courses.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>You are not enrolled in any course yet.</Text>
          </View>
        ) : visibleCourses.map(course => (
          <View key={course.id} testID={`att-course-${course.code}`} style={styles.courseCard}>
            <TouchableOpacity style={styles.courseHeader} onPress={() => toggleCourse(course.code)}>
              <View style={styles.courseNames}>
                <Text style={styles.courseCode}>{course.code}</Text>
                <Text style={styles.courseName} numberOfLines={1}>{course.name}</Text>
              </View>
              <View style={styles.rateBlock}>
                <Text testID={`att-rate-${course.code}`} style={styles.rateValue}>{course.rateText}</Text>
                <Text style={styles.rateLbl}>rate</Text>
              </View>
              <Ionicons
                name={collapsed[course.code] ? 'chevron-forward' : 'chevron-down'}
                size={14}
                color={C.textSub}
              />
            </TouchableOpacity>

            <Text testID={`att-note-${course.code}`} style={styles.rateNote}>{course.note}</Text>

            <View style={styles.countsRow}>
              {STATUSES.map(status => {
                const colors = BADGE_COLORS[statusInfo(status).badge] ?? BADGE_COLORS.gray
                return (
                  <View key={status} style={[styles.countChip, { backgroundColor: colors.bg }]}>
                    <Text
                      testID={`att-count-${status}-${course.code}`}
                      style={[styles.countText, { color: colors.fg }]}
                    >
                      {`${statusInfo(status).label} ${course.counts[status]}`}
                    </Text>
                  </View>
                )
              })}
            </View>

            {!collapsed[course.code] && course.sessions.length === 0 && (
              <Text style={styles.noRecordText}>No classes yet for this course.</Text>
            )}

            {!collapsed[course.code] && course.sessions.map(session => {
              const colors = BADGE_COLORS[session.badge] ?? BADGE_COLORS.gray
              return (
                <TouchableOpacity
                  key={session.id}
                  testID={`att-session-${session.id}`}
                  style={[styles.sessionRow, session.isLive && styles.sessionRowLive]}
                  onPress={() => navigation.navigate('AttSessionDetail', {
                    courseId: course.id,
                    sessionId: session.id,
                  })}
                >
                  <View style={[styles.dateBlock, { backgroundColor: colors.bg }]}>
                    <Text style={[styles.dateDay, { color: colors.fg }]}>{session.day}</Text>
                    <Text style={[styles.dateMonth, { color: colors.fg }]}>{session.month}</Text>
                  </View>
                  <View style={styles.sessionInfo}>
                    <Text style={styles.sessionTitle} numberOfLines={1}>{session.title}</Text>
                    <Text style={styles.sessionSub} numberOfLines={1}>
                      {session.sub}{session.overridden ? ' · changed by lecturer' : ''}
                    </Text>
                  </View>
                  <Badge variant={session.badge} dot={session.isLive}>
                    {session.isLive && session.status === 'not_recorded' ? 'In progress' : session.label}
                  </Badge>
                </TouchableOpacity>
              )
            })}
          </View>
        ))}
        <View style={{ height: 24 }} />
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
    paddingBottom: 10,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: C.text,
  },
  headerSub: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 2,
  },
  filterRow: {
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  filterContent: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.bg,
  },
  pillActive: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  pillText: {
    fontSize: 12,
    fontWeight: '600',
    color: C.textSub,
  },
  pillTextActive: {
    color: '#fff',
  },
  courseCard: {
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 12,
  },
  courseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  courseNames: {
    flex: 1,
  },
  courseCode: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
  },
  courseName: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 2,
  },
  rateBlock: {
    alignItems: 'flex-end',
  },
  rateValue: {
    fontSize: 20,
    fontWeight: '800',
    color: C.primary,
  },
  rateLbl: {
    fontSize: 10,
    color: C.textSub,
  },
  rateNote: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 4,
    marginBottom: 10,
  },
  countsRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 4,
  },
  countChip: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 20,
  },
  countText: {
    fontSize: 11,
    fontWeight: '700',
  },
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    marginTop: 8,
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: C.border,
    gap: 12,
  },
  sessionRowLive: {
    borderColor: C.primary,
    borderWidth: 1.5,
  },
  dateBlock: {
    width: 44,
    height: 50,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dateDay: {
    fontSize: 20,
    fontWeight: '800',
  },
  dateMonth: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sessionInfo: {
    flex: 1,
  },
  sessionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  sessionSub: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 2,
  },
  empty: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    color: C.textSub,
    textAlign: 'center',
  },
  noRecordText: {
    fontSize: 13,
    color: C.textHint,
    marginTop: 8,
  },
})
