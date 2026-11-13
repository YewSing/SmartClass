// FR-202 / FR-204 — lecturer dashboard: urgent & important notifications on top,
// then class attendance overview, student participation, assessment activities
// and notifications. Frontend-only for the M2/5/6/7 sections.
import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Badge from '../components/Badge'
import {
  NOTIFICATIONS, CLASS_OVERVIEW, ASSESSMENT_ACTIVITY, PRIORITIES,
} from '../data/module2'
import { C } from '../theme'

const DAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function nowHHMM() {
  const n = new Date()
  return `${String(n.getHours()).padStart(2, '0')}:${String(n.getMinutes()).padStart(2, '0')}`
}

function computeNextClasses(allClasses, limit = 3) {
  if (!allClasses.length) return []
  const todayIdx = (new Date().getDay() + 6) % 7
  const hhmm = nowHHMM()
  return allClasses
    .map(c => {
      const dayIdx = DAY_ORDER.indexOf(c.day_of_week)
      let daysAway = (dayIdx - todayIdx + 7) % 7
      if (daysAway === 0 && c.end_time < hhmm) daysAway = 7
      if (daysAway === 0 && c.start_time <= hhmm) return null
      return { ...c, daysAway }
    })
    .filter(Boolean)
    .sort((a, b) => a.daysAway - b.daysAway || a.start_time.localeCompare(b.start_time))
    .slice(0, limit)
}

function nextLabel(c) {
  if (!c) return ''
  const when = c.daysAway === 0 ? 'Today' : c.daysAway === 1 ? 'Tomorrow' : c.day_of_week
  return `${when} · ${c.start_time}–${c.end_time}`
}

export default function Dashboard({ navigation }) {
  const { state, openModal, loadClasses, loadAllClasses, loadSessions, doOpenSession, doCloseSession } = useLecturer()
  const { sessions, classes, allClasses, lecturer } = state
  const insets = useSafeAreaInsets()
  const [toggling, setToggling] = useState(false)

  useEffect(() => {
    loadClasses()
    loadSessions()
    loadAllClasses()
  }, [])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadClasses(), loadSessions(), loadAllClasses()])
    setRefreshing(false)
  }, [loadClasses, loadSessions, loadAllClasses])

  const activeSession = sessions.find(s => s.open)
  const sessionOpen = Boolean(activeSession)
  const firstClass = classes[0]
  const nextClasses = useMemo(() => computeNextClasses(allClasses), [allClasses])
  const nextClass = nextClasses[0] ?? null

  const handleToggleSession = async () => {
    if (toggling) return
    setToggling(true)
    try {
      if (sessionOpen) await doCloseSession(activeSession.id)
      else if (firstClass) await doOpenSession(firstClass.id)
    } catch { /* toast shown in context */ } finally {
      setToggling(false)
    }
  }

  const badgeVariant = sessionOpen ? 'green' : firstClass ? 'yellow' : 'gray'
  const badgeText = sessionOpen ? 'Session Open' : firstClass ? 'Class Ongoing' : 'No Class Now'

  const headerTitle = firstClass
    ? `${firstClass.code} — ${firstClass.name}`
    : nextClass
      ? `${nextClass.code} — ${nextClass.name}`
      : 'No classes this week'

  const headerMeta = firstClass
    ? [firstClass.day_of_week,
    firstClass.start_time && firstClass.end_time ? `${firstClass.start_time}–${firstClass.end_time}` : null,
    firstClass.room ?? null].filter(Boolean).join(' · ')
    : nextClass
      ? `Next: ${nextLabel(nextClass)}`
      : ''

  // FR-204 — urgent & important pinned on top.
  const sortedNotifs = [...NOTIFICATIONS].sort((a, b) => PRIORITIES[a.priority] - PRIORITIES[b.priority])
  const topNotifs = sortedNotifs.filter(n => !n.read).slice(0, 2)
  const unreadCount = NOTIFICATIONS.filter(n => !n.read).length

  return (<>
    <ScrollView
      style={styles.flex}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 8 }]}
      showsVerticalScrollIndicator={false}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
    >
      {/* App header */}
      <View style={styles.appHeader}>
        <View style={styles.brand}>
          <View style={styles.logoIcon}>
            <Ionicons name="school" size={18} color={C.primary} />
          </View>
          <Text style={styles.brandName}>SmartClass</Text>
        </View>
        <View style={styles.headerRight}>
          <TouchableOpacity style={styles.bellBtn} onPress={() => navigation.navigate('Notifications')}>
            <Ionicons name="notifications" size={19} color={C.text} />
            {unreadCount > 0 && (
              <View style={styles.bellBadge}><Text style={styles.bellBadgeText}>{unreadCount}</Text></View>
            )}
          </TouchableOpacity>
          <TouchableOpacity style={styles.profileBtn} onPress={() => navigation.navigate('Profile')}>
            <Text style={styles.profileInitials}>{lecturer?.initials ?? 'ME'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Dash header card (existing attendance session controls — M3) */}
      <View style={styles.dashHeader}>
        <View style={styles.dashHeaderTop}>
          <View style={styles.flex}>
            <Text style={styles.className}>{headerTitle}</Text>
            {headerMeta ? <Text style={styles.classMeta}>{headerMeta}</Text> : null}
          </View>
          <Badge variant={badgeVariant} dot>{badgeText}</Badge>
        </View>
        <View style={styles.dashHeaderBot}>
          {sessionOpen ? (
            <View style={styles.rowGap}>
              <Ionicons name="time-outline" size={12} color={C.textSub} />
              <Text style={styles.metaSmall}>Opened {activeSession.time}</Text>
            </View>
          ) : (
            <Text style={styles.metaSmall}>{firstClass ? 'Ready to open' : 'No active session'}</Text>
          )}
          <TouchableOpacity
            style={[
              styles.sessionToggleBtn,
              sessionOpen ? styles.toggleClose : styles.toggleOpen,
              (toggling || (!sessionOpen && !firstClass)) && styles.btnDisabled,
            ]}
            onPress={handleToggleSession}
            disabled={toggling || (!sessionOpen && !firstClass)}
          >
            <Ionicons name={sessionOpen ? 'stop-circle-outline' : 'play-circle-outline'} size={16} color="#fff" />
            <Text style={styles.toggleText}>
              {toggling ? ' …' : sessionOpen ? ' Close Session' : ' Open Session'}
            </Text>
          </TouchableOpacity>
        </View>

        {!sessionOpen && (
          <>
            <View style={styles.cardDivider} />
            {firstClass ? (
              <View style={styles.cardExtra}>
                <Ionicons name="school" size={14} color={C.green} style={{ marginTop: 1 }} />
                <Text style={styles.cardExtraText}>
                  {firstClass.code} is ongoing — open a session above to start tracking attendance.
                </Text>
              </View>
            ) : nextClasses.length ? (
              <View>
                <View style={styles.cardExtraHeader}>
                  <Ionicons name="calendar-outline" size={13} color={C.textSub} />
                  <Text style={styles.cardExtraLabel}>Upcoming</Text>
                </View>
                {nextClasses.map((c, i) => (
                  <View key={c.id} style={[styles.nextClassRow, i > 0 && styles.nextClassRowBorder]}>
                    <Text style={styles.cardExtraTitle}>{c.code} — {c.name}</Text>
                    <Text style={styles.cardExtraMeta}>
                      {nextLabel(c)}{c.room ? ` · ${c.room}` : ''}
                    </Text>
                  </View>
                ))}
              </View>
            ) : (
              <View style={styles.cardExtra}>
                <Ionicons name="hourglass-outline" size={14} color={C.textSub} style={{ marginTop: 1 }} />
                <Text style={styles.cardExtraText}>No classes scheduled this week.</Text>
              </View>
            )}
          </>
        )}
      </View>

      {/* Urgent & important notifications — pinned (FR-204) */}
      {topNotifs.length > 0 && (
        <>
          <View style={styles.sectionHeader}>
            <Ionicons name="notifications" size={12} color={C.red} />
            <Text style={[styles.sectionTitle, { color: C.redDk }]}>Needs your attention</Text>
            <TouchableOpacity onPress={() => navigation.navigate('Notifications')}>
              <Text style={styles.seeAll}>See all</Text>
            </TouchableOpacity>
          </View>
          {topNotifs.map(n => (
            <TouchableOpacity
              key={n.id}
              style={[styles.notifCard, n.priority === 'urgent' && styles.notifUrgent]}
              activeOpacity={0.7}
              onPress={() => navigation.navigate('Notifications')}
            >
              <View style={[styles.notifIcon, { backgroundColor: n.priority === 'urgent' ? C.redLt : C.orangeLt }]}>
                <Ionicons name={n.icon} size={16} color={n.priority === 'urgent' ? C.red : C.orangeDk} />
              </View>
              <View style={styles.notifBody}>
                <View style={styles.notifTop}>
                  <Text style={styles.notifTitle} numberOfLines={1}>{n.title}</Text>
                  <Badge variant={n.priority === 'urgent' ? 'red' : 'orange'}>
                    {n.priority === 'urgent' ? 'Urgent' : 'Important'}
                  </Badge>
                </View>
                <Text style={styles.notifText} numberOfLines={2}>{n.body}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </>
      )}

      {/* Class overview — FR-202 */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Class Overview</Text>
        <TouchableOpacity onPress={() => navigation.navigate('Analytics')}>
          <Text style={styles.seeAll}>Analytics</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.overviewGrid}>
        <View style={styles.overviewCell}>
          <Text style={[styles.overviewNum, { color: C.primary }]}>{CLASS_OVERVIEW.attendanceRate}%</Text>
          <Text style={styles.overviewLbl}>Attendance</Text>
        </View>
        <View style={styles.overviewCell}>
          <Text style={[styles.overviewNum, { color: C.purple }]}>{CLASS_OVERVIEW.participationRate}%</Text>
          <Text style={styles.overviewLbl}>Participation</Text>
        </View>
        <View style={styles.overviewCell}>
          <Text style={styles.overviewNum}>{CLASS_OVERVIEW.avgQuizScore}%</Text>
          <Text style={styles.overviewLbl}>Avg quiz score</Text>
        </View>
        <View style={styles.overviewCell}>
          <Text style={[styles.overviewNum, { color: C.red }]}>{CLASS_OVERVIEW.atRisk}</Text>
          <Text style={styles.overviewLbl}>At-risk</Text>
        </View>
      </View>

      {/* Live session attendance (existing M3 behaviour) */}
      {sessionOpen && (
        <>
          <View style={[styles.sectionHeader, { paddingTop: 14 }]}>
            <Text style={styles.sectionTitle}>Live Attendance</Text>
          </View>
          <TouchableOpacity style={styles.card} onPress={() => navigation.navigate('Attendance')}>
            <View style={styles.attendStats}>
              <View style={styles.attendStat}>
                <Text style={[styles.attendNum, { color: C.green }]}>{activeSession.present}</Text>
                <Text style={styles.attendLbl}>Present</Text>
              </View>
              <View style={styles.attendStat}>
                <Text style={[styles.attendNum, { color: C.red }]}>{activeSession.absent}</Text>
                <Text style={styles.attendLbl}>Absent</Text>
              </View>
              <View style={styles.attendStat}>
                <Text style={[styles.attendNum, { color: C.orange }]}>{activeSession.unid}</Text>
                <Text style={styles.attendLbl}>Unidentified</Text>
              </View>
            </View>
            <View style={styles.cardFooter}>
              <Ionicons name="chevron-forward" size={12} color={C.textHint} />
              <Text style={styles.cardFooterText}> Tap to view full attendance</Text>
            </View>
          </TouchableOpacity>
        </>
      )}

      {/* Assessment activity — FR-202 / Module 6 */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Assessment Activity</Text>
        <TouchableOpacity onPress={() => navigation.navigate('Quiz')}>
          <Text style={styles.seeAll}>See all</Text>
        </TouchableOpacity>
      </View>
      {ASSESSMENT_ACTIVITY.slice(0, 3).map(a => (
        <TouchableOpacity
          key={a.id}
          style={styles.card}
          activeOpacity={0.7}
          onPress={() => navigation.navigate('Quiz')}
        >
          <View style={styles.assessTop}>
            <View>
              <View style={styles.courseTagRow}>
                <View style={styles.courseTag}><Text style={styles.courseTagText}>{a.course}</Text></View>
              </View>
              <Text style={styles.assessTitle}>{a.title}</Text>
              <Text style={styles.assessMeta}>{a.meta}</Text>
            </View>
            <Badge variant={a.status === 'open' ? 'green' : a.status === 'needs-grading' ? 'orange' : 'gray'}>
              {a.status === 'open' ? 'Open' : a.status === 'needs-grading' ? 'Needs grading' : 'Closed'}
            </Badge>
          </View>
          {a.status === 'open' && (
            <View style={styles.progressRow}>
              <View style={styles.progressTrack}>
                <View style={[styles.progressFill, { width: `${Math.round((a.submitted / a.enrolled) * 100)}%` }]} />
              </View>
              <Text style={styles.progressPct}>{a.submitted}/{a.enrolled}</Text>
            </View>
          )}
        </TouchableOpacity>
      ))}

      {/* Quick actions */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Quick Actions</Text>
      </View>
      <View style={styles.quickGrid}>
        <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('Interact')}>
          <Ionicons name="pulse" size={20} color={C.red} />
          <Text style={styles.quickLbl}>Interact</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('Quiz', { screen: 'CreateQuiz' })}>
          <Ionicons name="sparkles" size={20} color={C.primary} />
          <Text style={styles.quickLbl}>Generate Quiz</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('Quiz')}>
          <Ionicons name="document-text" size={20} color={C.green} />
          <Text style={styles.quickLbl}>Assessments</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('Analytics')}>
          <Ionicons name="bar-chart" size={20} color={C.purple} />
          <Text style={styles.quickLbl}>Analytics</Text>
        </TouchableOpacity>
      </View>

      <View style={{ height: 20 }} />
    </ScrollView>
  </>)
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { backgroundColor: C.bg, paddingHorizontal: 16, paddingBottom: 20 },
  appHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14,
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logoIcon: {
    width: 32, height: 32, borderRadius: 8, backgroundColor: C.blueLt,
    alignItems: 'center', justifyContent: 'center',
  },
  brandName: { fontSize: 18, fontWeight: '800', color: C.text, letterSpacing: -0.3 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  bellBtn: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: C.card,
    borderWidth: 1, borderColor: C.border, alignItems: 'center', justifyContent: 'center',
  },
  bellBadge: {
    position: 'absolute', top: -3, right: -3, minWidth: 16, height: 16, borderRadius: 8,
    backgroundColor: C.red, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4,
  },
  bellBadgeText: { fontSize: 9, fontWeight: '800', color: '#fff' },
  profileBtn: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  profileInitials: { fontSize: 13, fontWeight: '700', color: '#fff' },
  dashHeader: {
    backgroundColor: C.card, borderRadius: 14, padding: 14, marginBottom: 6,
    borderWidth: 1, borderColor: C.border,
  },
  dashHeaderTop: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 10,
  },
  className: { fontSize: 16, fontWeight: '700', color: C.text, marginBottom: 2 },
  classMeta: { fontSize: 12, color: C.textSub },
  dashHeaderBot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  metaSmall: { fontSize: 12, color: C.textSub },
  rowGap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  sessionToggleBtn: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 8, gap: 4,
  },
  toggleOpen: { backgroundColor: C.green },
  toggleClose: { backgroundColor: C.red },
  toggleText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  btnDisabled: { opacity: 0.45 },
  sectionHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 6, marginBottom: 6,
  },
  sectionTitle: {
    fontSize: 11, fontWeight: '600', color: C.textHint,
    textTransform: 'uppercase', letterSpacing: 0.8, flex: 1,
  },
  seeAll: { fontSize: 12, fontWeight: '700', color: C.primary },
  notifCard: {
    flexDirection: 'row', gap: 10, backgroundColor: C.card, marginBottom: 8,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 12, alignItems: 'flex-start',
  },
  notifUrgent: { borderColor: C.red, borderWidth: 1.5, backgroundColor: C.redLt },
  notifIcon: { width: 32, height: 32, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  notifBody: { flex: 1 },
  notifTop: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 },
  notifTitle: { flex: 1, fontSize: 13, fontWeight: '700', color: C.text },
  notifText: { fontSize: 12, color: C.textSub, lineHeight: 17 },
  overviewGrid: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  overviewCell: {
    flex: 1, backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border,
    alignItems: 'center', paddingVertical: 12,
  },
  overviewNum: { fontSize: 18, fontWeight: '800', color: C.text },
  overviewLbl: { fontSize: 9, color: C.textSub, marginTop: 2, textAlign: 'center' },
  card: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  attendStats: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 12 },
  attendStat: { alignItems: 'center' },
  attendNum: { fontSize: 28, fontWeight: '800' },
  attendLbl: { fontSize: 11, color: C.textSub, marginTop: 2 },
  cardFooter: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingTop: 10, borderTopWidth: 1, borderTopColor: C.border,
  },
  cardFooterText: { fontSize: 12, color: C.textHint },
  assessTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 },
  courseTagRow: { marginBottom: 4 },
  courseTag: { backgroundColor: C.blueLt, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6, alignSelf: 'flex-start' },
  courseTagText: { fontSize: 10, fontWeight: '800', color: C.primary },
  assessTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  assessMeta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  progressRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10 },
  progressTrack: { flex: 1, height: 5, borderRadius: 3, backgroundColor: C.gray100, overflow: 'hidden' },
  progressFill: { height: 5, backgroundColor: C.primary },
  progressPct: { fontSize: 11, color: C.textHint, minWidth: 40, textAlign: 'right' },
  quickGrid: { flexDirection: 'row', gap: 8 },
  quickBtn: {
    flex: 1, backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border,
    alignItems: 'center', paddingVertical: 13, gap: 5,
  },
  quickLbl: { fontSize: 10, fontWeight: '700', color: C.textSub, textAlign: 'center' },
  cardDivider: { height: 1, backgroundColor: C.border, marginVertical: 12 },
  cardExtra: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  cardExtraText: { flex: 1, fontSize: 12, color: C.textSub, lineHeight: 18 },
  cardExtraHeader: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 8 },
  cardExtraLabel: {
    fontSize: 10, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.8,
    color: C.textHint, marginBottom: 2,
  },
  cardExtraTitle: { fontSize: 13, fontWeight: '600', color: C.text, marginBottom: 2 },
  cardExtraMeta: { fontSize: 12, color: C.textSub },
  nextClassRow: { paddingTop: 8, gap: 2 },
  nextClassRowBorder: { borderTopWidth: 1, borderTopColor: C.border, marginTop: 8 },
})
