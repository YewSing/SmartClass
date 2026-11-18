import { useEffect, useState, useCallback, useMemo } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { LinearGradient } from 'expo-linear-gradient'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useFocusEffect } from '@react-navigation/native'
import { useStudent } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { navigateTo } from '../navigation/navigationRef'
import { getOpenInteractions } from '../services/api'
import { C } from '../theme'

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning,'
  if (h < 17) return 'Good afternoon,'
  return 'Good evening,'
}

function statusColor(status) {
  switch (status) {
    case 'present': return C.green
    case 'late': return C.orange
    case 'absent': return C.red
    case 'excused': return C.primary
    default: return C.textHint
  }
}

function statusLabel(status) {
  switch (status) {
    case 'present': return 'Present'
    case 'late': return 'Late'
    case 'absent': return 'Absent'
    case 'excused': return 'Excused'
    default: return 'Not Yet Recorded'
  }
}

function statusBadge(status) {
  switch (status) {
    case 'present': return 'green'
    case 'late': return 'orange'
    case 'absent': return 'red'
    case 'excused': return 'blue'
    default: return 'gray'
  }
}

export default function Home({ navigation }) {
  const { state, loadClasses, loadAttendanceCourses, showToast } = useStudent()
  const { classes, student, attendanceCourses } = state
  const insets = useSafeAreaInsets()

  useEffect(() => { loadClasses() }, [loadClasses])
  useEffect(() => { loadAttendanceCourses() }, [loadAttendanceCourses])

  // ── Live interaction (from lecturer opening a session) ──
  const [openInteractions, setOpenInteractions] = useState([])
  const loadOpenInteractions = useCallback(async () => {
    try { setOpenInteractions(await getOpenInteractions()) } catch { /* card hides on failure */ }
  }, [])
  useFocusEffect(useCallback(() => { loadOpenInteractions() }, [loadOpenInteractions]))

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadClasses(), loadAttendanceCourses(), loadOpenInteractions()])
    setRefreshing(false)
  }, [loadClasses, loadAttendanceCourses, loadOpenInteractions])

  const liveInteraction = openInteractions[0] ?? null

  // Find a live session across attendance courses
  const liveSession = useMemo(() => {
    for (const c of attendanceCourses ?? []) {
      const s = c.sessions?.find(s => s.isLive)
      if (s) return { ...s, course: c }
    }
    return null
  }, [attendanceCourses])

  const isLive = Boolean(liveSession || liveInteraction)

  // Current active class information
  const activeClass = useMemo(() => {
    if (liveSession?.course) {
      return {
        id: liveSession.course.id,
        code: liveSession.course.course_code ?? liveSession.course.code,
        name: liveSession.course.course_name ?? liveSession.course.name,
        room: liveSession.room ?? liveSession.venue ?? 'DK 6, BLI Building',
        time: liveSession.time ?? '10:00–12:00',
        day: liveSession.day ?? 'Mon',
      }
    }
    if (liveInteraction) {
      return {
        id: liveInteraction.occurrence_id ?? 1,
        code: liveInteraction.class_code,
        name: liveInteraction.class_name,
        room: 'DK 6, BLI Building',
        time: 'Active now',
        day: 'Today',
      }
    }
    // Fallback to first enrolled class if no session is open
    const first = classes[0]
    if (first) {
      return {
        id: first.id,
        code: first.code,
        name: first.name,
        room: first.room ?? first.venue ?? 'DK 6, BLI Building',
        time: first.start_time && first.end_time ? `${first.start_time}–${first.end_time}` : 'Scheduled',
        day: first.day_of_week ?? 'Mon',
      }
    }
    return null
  }, [liveSession, liveInteraction, classes])

  // Count of active questions / polls pushed by lecturer during live interaction
  const liveInteractionCounts = useMemo(() => {
    if (!liveInteraction) return { questionsCount: 0, pollsCount: 0, totalPushed: 0 }
    const questionsCount = Array.isArray(liveInteraction.questions) ? liveInteraction.questions.length : (liveInteraction.open_questions ?? 1)
    const pollsCount = liveInteraction.current_poll ? 1 : 0
    const liveQsCount = liveInteraction.live_question ? 1 : 0
    const totalPushed = questionsCount + pollsCount + liveQsCount
    return { questionsCount, pollsCount, totalPushed }
  }, [liveInteraction])

  const openPersonalSession = () => {
    if (liveSession) {
      navigation.navigate('AttSessionDetail', {
        courseId: liveSession.course?.id ?? liveSession.occurrence_id,
        sessionId: liveSession.id,
      })
    } else {
      navigation.navigate('Attendance')
    }
  }

  const joinInteraction = () => {
    if (liveInteraction || liveSession) {
      navigation.navigate('Participation', {
        interaction_id: liveInteraction?.id ?? liveSession?.id,
      })
    } else {
      navigation.navigate('Participation')
    }
  }

  // Next upcoming session (non-live)
  const nextSession = useMemo(() => {
    const upcoming = attendanceCourses?.flatMap(c =>
      (c.sessions ?? []).map(s => ({ ...s, course: c })).filter(s => !s.isLive) ?? []
    ) ?? []
    return upcoming[0] ?? null
  }, [attendanceCourses])

  const myLiveStatus = liveSession?.status ?? (isLive ? 'present' : 'not_recorded')

  return (
    <View style={styles.flex}>
      <Topbar
        icon="school"
        title="SmartClass"
        right={
          <TouchableOpacity
            style={styles.profileBtn}
            onPress={() => navigateTo('Home', { screen: 'ProfileScreen' })}
          >
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{student?.initials ?? 'AI'}</Text>
            </View>
          </TouchableOpacity>
        }
      />
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* Greeting banner */}
        <LinearGradient
          colors={['#0D47A1', '#1565C0', '#1976D2']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[styles.banner, { paddingTop: insets.top + 16 }]}
        >
          <Text style={styles.greetingText}>{greeting()}</Text>
          <Text style={styles.greetingName}>{student?.name ?? '—'}</Text>
          <Text style={styles.greetingSub}>
            {classes.length > 0
              ? `${classes.length} enrolled class${classes.length !== 1 ? 'es' : ''} · Semester 2`
              : 'Loading classes…'}
          </Text>
        </LinearGradient>

        {/* ── Top Class Session Card (mirrors lecturer header card design, no open button) ── */}
        <View style={styles.sessionHeaderCard}>
          <View style={styles.sessionCardTop}>
            <View style={styles.sessionDetailsCol}>
              <Text style={styles.sessionClassCode}>
                {activeClass?.code ?? 'Course'} — {activeClass?.name ?? 'No scheduled class'}
              </Text>
              <Text style={styles.sessionClassMeta}>
                {[activeClass?.day, activeClass?.time, activeClass?.room].filter(Boolean).join(' · ')}
              </Text>
            </View>
            <Badge variant={isLive ? 'green' : 'gray'} dot>
              {isLive ? 'Session Live' : 'No Live Class'}
            </Badge>
          </View>

          <View style={styles.sessionCardDivider} />

          {/* ── Below Side-by-Side Dual Cards: Personal Attendance Status + Live Interaction ── */}
          <View style={styles.dualCardsRow}>
            {/* Left Card: Personal live attendance status -> click to personal session details */}
            <TouchableOpacity
              style={styles.halfCard}
              activeOpacity={0.8}
              testID="home-personal-attendance"
              onPress={openPersonalSession}
            >
              <View style={styles.halfCardHeader}>
                <View style={styles.iconCircleBlue}>
                  <Ionicons name="scan-outline" size={16} color={C.primary} />
                </View>
                <Badge variant={statusBadge(myLiveStatus)} dot>
                  {statusLabel(myLiveStatus)}
                </Badge>
              </View>

              <Text style={styles.halfCardTitle}>My Attendance</Text>
              <Text style={styles.halfCardSub}>
                {isLive ? 'Camera verification active' : 'View session history'}
              </Text>

              <View style={styles.halfCardActionRow}>
                <Text style={styles.halfCardActionText}>Session Details</Text>
                <Ionicons name="chevron-forward" size={13} color={C.primary} />
              </View>
            </TouchableOpacity>

            {/* Right Card: Live interaction card -> shows pushed Qs/polls count -> click to join */}
            <TouchableOpacity
              style={[styles.halfCard, liveInteraction && styles.halfCardActiveInteraction]}
              activeOpacity={0.8}
              testID="home-live-interaction"
              onPress={joinInteraction}
            >
              <View style={styles.halfCardHeader}>
                <View style={styles.iconCircleGreen}>
                  <Ionicons name="chatbubbles-outline" size={16} color={C.green} />
                </View>
                <Badge variant={liveInteraction ? 'green' : 'gray'} dot={Boolean(liveInteraction)}>
                  {liveInteraction ? 'Live' : 'Inactive'}
                </Badge>
              </View>

              <View style={styles.interactionCountRow}>
                <Text style={styles.interactionCountNumber}>
                  {liveInteraction ? liveInteractionCounts.totalPushed : 0}
                </Text>
                <Text style={styles.interactionCountUnit}>active</Text>
              </View>

              <Text style={styles.halfCardTitle}>Classroom Interaction</Text>
              <Text style={styles.halfCardSub} numberOfLines={1}>
                {liveInteraction
                  ? `${liveInteractionCounts.questionsCount} Qs · ${liveInteractionCounts.pollsCount} polls live`
                  : 'No active interaction room'}
              </Text>

              <View style={styles.halfCardActionRow}>
                <Text style={[styles.halfCardActionText, { color: C.green }]}>
                  {liveInteraction ? 'Join Now' : 'Open Tab'}
                </Text>
                <Ionicons name="chevron-forward" size={13} color={C.green} />
              </View>
            </TouchableOpacity>
          </View>
        </View>

        {/* Next session reminder banner if no session live */}
        {!isLive && nextSession && (
          <View style={styles.nextSessionCallout}>
            <Ionicons name="time-outline" size={15} color={C.textSub} />
            <Text style={styles.nextSessionCalloutText}>
              Next class: <Text style={styles.bold}>{nextSession.course?.course_code ?? 'Class'}</Text> ({nextSession.dayMonth ? `${nextSession.dayMonth.day} ${nextSession.dayMonth.month}` : ''} · {nextSession.time ?? ''})
            </Text>
          </View>
        )}

        {/* Enrolled Classes Section */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Enrolled Classes</Text>
        </View>

        {classes.map(cls => (
          <TouchableOpacity
            key={cls.id}
            style={styles.classCard}
            activeOpacity={0.7}
            onPress={() => navigation.navigate('Attendance')}
          >
            <View style={[styles.accent, { backgroundColor: cls.accentColor ?? C.primary }]} />
            <View style={styles.classBody}>
              <View style={styles.codeRow}>
                <Text style={styles.classCode}>{cls.code}</Text>
                <Badge variant={cls.type === 'LECTURE' ? 'blue' : 'green'}>
                  {cls.type === 'LECTURE' ? 'Lecture' : (cls.label ?? 'Tutorial')}
                </Badge>
              </View>
              <Text style={styles.classTitle}>{cls.name}</Text>
              <View style={styles.metaRow}>
                <Ionicons name="location-outline" size={12} color={C.textSub} />
                <Text style={styles.metaText}>
                  {[cls.venue, cls.day_of_week && cls.start_time ? `${cls.day_of_week} ${cls.start_time}` : null].filter(Boolean).join(' · ')}
                </Text>
              </View>
            </View>
            <View style={styles.cardArrow}>
              <Ionicons name="chevron-forward" size={18} color={C.gray400} />
            </View>
          </TouchableOpacity>
        ))}

        {classes.length === 0 && (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No enrolled classes found.</Text>
          </View>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#FFFFFF' },
  profileBtn: { padding: 6 },
  avatar: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: '#fff',
  },
  avatarText: {
    fontSize: 12,
    fontWeight: '800',
    color: '#fff',
  },
  banner: {
    paddingHorizontal: 20,
    paddingBottom: 24,
  },
  greetingText: {
    fontSize: 14,
    color: '#DBEAFE',
    fontWeight: '500',
  },
  greetingName: {
    fontSize: 22,
    fontWeight: '800',
    color: '#fff',
    marginTop: 2,
  },
  greetingSub: {
    fontSize: 12,
    color: '#BFDBFE',
    marginTop: 4,
  },
  sessionHeaderCard: {
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginTop: -12,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  sessionCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  sessionDetailsCol: {
    flex: 1,
  },
  sessionClassCode: {
    fontSize: 15,
    fontWeight: '700',
    color: C.text,
  },
  sessionClassMeta: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 4,
  },
  sessionCardDivider: {
    height: 1,
    backgroundColor: C.border,
    marginVertical: 12,
  },
  dualCardsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  halfCard: {
    flex: 1,
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: C.border,
    justifyContent: 'space-between',
    minHeight: 120,
  },
  halfCardActiveInteraction: {
    backgroundColor: '#F0FDF4',
    borderColor: '#BBF7D0',
  },
  halfCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  iconCircleBlue: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconCircleGreen: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: '#DCFCE7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  interactionCountRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 4,
  },
  interactionCountNumber: {
    fontSize: 18,
    fontWeight: '800',
    color: C.green,
  },
  interactionCountUnit: {
    fontSize: 11,
    fontWeight: '600',
    color: C.green,
  },
  halfCardTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
    marginTop: 2,
  },
  halfCardSub: {
    fontSize: 10,
    color: C.textSub,
    marginTop: 2,
  },
  halfCardActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 8,
  },
  halfCardActionText: {
    fontSize: 11,
    fontWeight: '700',
    color: C.primary,
  },
  nextSessionCallout: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
  },
  nextSessionCalloutText: {
    fontSize: 12,
    color: C.textSub,
  },
  bold: {
    fontWeight: '700',
    color: C.text,
  },
  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  classCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    overflow: 'hidden',
  },
  accent: {
    width: 5,
    alignSelf: 'stretch',
  },
  classBody: {
    flex: 1,
    paddingVertical: 12,
    paddingLeft: 14,
    paddingRight: 6,
  },
  codeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  classCode: {
    fontSize: 12,
    fontWeight: '700',
    color: C.primary,
  },
  classTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  metaText: {
    fontSize: 11,
    color: C.textSub,
  },
  cardArrow: {
    justifyContent: 'center',
    paddingRight: 14,
    paddingLeft: 4,
  },
  empty: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    color: C.textSub,
  },
})
