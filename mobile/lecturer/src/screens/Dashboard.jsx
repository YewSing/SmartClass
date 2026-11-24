import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useLecturer } from '../context/LecturerContext'
import Badge from '../components/Badge'
import AttendanceCounts from '../components/AttendanceCounts'
import InteractionHomeCard from '../components/InteractionHomeCard'
import NotificationBell from '../components/NotificationBell'
import {
  useDashboard, SectionTitle, LoadingCard, ErrorCard, EmptyRow, PriorityNotifications, dashStyles,
} from '../components/DashboardParts'
import * as api from '../services/api'
import { sessionCounts } from '../services/attendance'
import {
  classTypeLabel, rateLabel, rateVariant, overviewCounts,
} from '../services/dashboard'
import { pendingLabel } from '../services/faceReview'
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
    .filter(c => c.day_of_week && c.start_time && c.end_time)   // a class with no schedule has no "next"
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

// The latest session's numbers from GET /lecturer/dashboard (FR-202, S18). Today's classes aren't
// listed again: the session card above shows the class running now, or the next ones.
function LatestOverview({ data, openClass, openInteraction, refreshKey }) {
  const { attendance_overview: o } = data
  return (
    <>
          <SectionTitle>{o?.session_status === 'open' ? 'Current class' : 'Latest class'}</SectionTitle>
          {o ? (
            <TouchableOpacity style={dashStyles.card} onPress={() => openClass(o.occurrence_id)} testID="dash-overview">
              <View style={styles.overviewTop}>
                <View style={dashStyles.rowMain}>
                  <Text style={dashStyles.code}>{o.course_code} · {classTypeLabel(o)}</Text>
                  <Text style={dashStyles.rowSub}>
                    {o.session_status === 'open' ? 'Live now' : `Ended · ${o.date ?? ''}`} · {o.enrolled} enrolled
                  </Text>
                </View>
                {o.session_status === 'closed'
                  ? <Badge variant={rateVariant(o.rate)}>{rateLabel(o.rate)}</Badge>
                  : <Badge variant="green" dot>Live</Badge>}
              </View>
              <View style={styles.attendCounts}>
                <AttendanceCounts counts={overviewCounts(o)} open={o.session_status === 'open'} testIDPrefix="dash-count" />
              </View>
            </TouchableOpacity>
          ) : (
            <View style={dashStyles.card}>
              <EmptyRow text="No attendance taken yet." testID="dash-overview-empty" />
            </View>
          )}
          {/* What that class asked, voted and pressed (Module 5) */}
          {o ? (
            <>
              <SectionTitle>Interaction</SectionTitle>
              <InteractionHomeCard
                sessionId={o.session_id} live={o.session_status === 'open'} label={o.course_code}
                testID="dash-overview-summary" refreshKey={refreshKey} onPress={() => openInteraction(o)}
              />
            </>
          ) : null}
    </>
  )
}

const EXTEND_MINUTES = 15

// End early or add time to the running class from the session card (FR-315: M3's extend and
// close, through LecturerContext)
function SessionControls({ session }) {
  const { doExtendSession, doCloseSession } = useLecturer()
  const [busy, setBusy] = useState(false)
  const [confirmEnd, setConfirmEnd] = useState(false)

  const run = async (fn) => {
    setBusy(true)
    try { await fn() } catch { /* toast shown in context */ } finally { setBusy(false); setConfirmEnd(false) }
  }

  if (confirmEnd) {
    return (
      <View style={styles.controls}>
        <Text style={styles.cardExtraText}>
          End the class now? Anyone not recorded is marked Absent and the marks are sent to SPeCTRUM.
        </Text>
        <View style={styles.btnRow}>
          <TouchableOpacity style={[styles.ctrlBtn, styles.ctrlOutline]} disabled={busy}
            testID="home-session-keep" onPress={() => setConfirmEnd(false)}>
            <Text style={styles.ctrlOutlineText}>Keep running</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.ctrlBtn, styles.ctrlDanger, busy && styles.btnDisabled]} disabled={busy}
            testID="home-session-end-confirm" onPress={() => run(() => doCloseSession(session.id))}>
            <Ionicons name="stop-circle-outline" size={15} color="#fff" />
            <Text style={styles.toggleText}>{busy ? 'Ending…' : 'End now'}</Text>
          </TouchableOpacity>
        </View>
      </View>
    )
  }
  return (
    <View style={[styles.btnRow, styles.controls]}>
      <TouchableOpacity style={[styles.ctrlBtn, styles.ctrlOutline, busy && styles.btnDisabled]} disabled={busy}
        testID="home-session-extend" onPress={() => run(() => doExtendSession(session.id, EXTEND_MINUTES))}>
        <Ionicons name="add-circle-outline" size={15} color={C.text} />
        <Text style={styles.ctrlOutlineText}>+{EXTEND_MINUTES} min</Text>
      </TouchableOpacity>
      <TouchableOpacity style={[styles.ctrlBtn, styles.ctrlDanger, busy && styles.btnDisabled]} disabled={busy}
        testID="home-session-end" onPress={() => setConfirmEnd(true)}>
        <Ionicons name="stop-circle-outline" size={15} color="#fff" />
        <Text style={styles.toggleText}>End class</Text>
      </TouchableOpacity>
    </View>
  )
}

export default function Dashboard({ navigation }) {
  const {
    state, loadClasses, loadAllClasses, loadSessions, doOpenSession, selectSession, feed,
    markNotificationRead, openNotificationLink,
  } = useLecturer()
  const { sessions, classes, allClasses, lecturer } = state
  const insets = useSafeAreaInsets()
  const [starting, setStarting] = useState(false)
  const { dash, dispatch: dashDispatch, refresh: refreshDash } = useDashboard(api.getDashboard, feed.unread)

  const openPriority = useCallback(async (n) => {
    if (!(await markNotificationRead(n))) return
    dashDispatch({ type: 'read', id: n.id })
    if (n.link) openNotificationLink(n.link)
  }, [markNotificationRead, openNotificationLink, dashDispatch])

  useEffect(() => {
    loadClasses()
    loadAllClasses()
  }, [])
  // The schedule opens and closes classes by itself, so re-read the sessions on every visit
  useFocusEffect(useCallback(() => { loadSessions() }, [loadSessions]))

  // Face enrolments waiting for this lecturer (FR-113); a failed count just hides the banner
  const [pendingFaces, setPendingFaces] = useState(0)
  const loadPendingFaces = useCallback(async () => {
    try { setPendingFaces((await api.getPendingFaceSubmissions()).length) } catch { setPendingFaces(0) }
  }, [])
  useFocusEffect(useCallback(() => { loadPendingFaces() }, [loadPendingFaces]))

  const [refreshing, setRefreshing] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)   // a pull to refresh re-reads the interaction card too
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    setRefreshKey(k => k + 1)
    await Promise.all([loadClasses(), loadSessions(), loadAllClasses(), loadPendingFaces(), refreshDash()])
    setRefreshing(false)
  }, [loadClasses, loadSessions, loadAllClasses, loadPendingFaces, refreshDash])

  const activeSession = sessions.find(s => s.open)
  const sessionOpen   = Boolean(activeSession)
  const firstClass    = classes[0]
  const nextClasses   = useMemo(() => computeNextClasses(allClasses), [allClasses])
  const nextClass     = nextClasses[0] ?? null

  const openLive = (session) => {
    selectSession(session)
    navigation.navigate('AttendanceDetail')
  }

  // Start the current class; if the schedule opened it since this screen loaded, go to it
  // instead (that used to give a 409)
  const handleSessionButton = async () => {
    if (starting || !firstClass) return
    setStarting(true)
    try {
      const running = (await api.getSessions()).find(s => s.open && s.class_id === firstClass.id)
      openLive(running ?? await doOpenSession(firstClass.id))
      if (running) loadSessions()
    } catch { /* toast shown in context */ } finally {
      setStarting(false)
    }
  }

  const badgeVariant = sessionOpen ? 'green' : firstClass ? 'yellow' : 'gray'
  const badgeText    = sessionOpen ? 'Session Open' : firstClass ? 'Class Ongoing' : 'No Class Now'

  const headerTitle = firstClass
    ? `${firstClass.code} — ${firstClass.name}`
    : nextClass
      ? `${nextClass.code} — ${nextClass.name}`
      : 'No classes this week'

  const headerClassId = firstClass?.id ?? nextClass?.id
  const openClass = (classId) => navigation.navigate('ClassDetail', { classId })

  const headerMeta = firstClass
    ? [
        firstClass.day_of_week,
        firstClass.start_time && firstClass.end_time
          ? `${firstClass.start_time}–${firstClass.end_time}`
          : null,
        firstClass.room ?? null,
      ].filter(Boolean).join(' · ')
    : nextClass
      ? `Next: ${nextLabel(nextClass)}`
      : ''

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
        <View style={styles.headerActions}>
          <NotificationBell count={feed.unread} onPress={() => navigation.navigate('Notifications')} />
          <TouchableOpacity style={styles.profileBtn} accessibilityLabel="Profile" onPress={() => navigation.navigate('Profile')}>
            <Text style={styles.profileInitials}>{lecturer?.initials ?? 'ME'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {dash.status === 'error' && <ErrorCard message={dash.error} onRetry={refreshDash} />}
      {dash.status === 'ready' && dash.error ? <ErrorCard inline message={dash.error} onRetry={refreshDash} /> : null}
      {/* Unread urgent/important stay on top until read (FR-208) */}
      {dash.data ? <PriorityNotifications items={dash.data.priority_notifications} onOpen={openPriority} /> : null}

      {/* Dash header card */}
      <View style={styles.dashHeader}>
        <View style={styles.dashHeaderTop}>
          <TouchableOpacity
            style={styles.tappableClass}
            testID="home-class-card"
            disabled={!headerClassId}
            onPress={() => openClass(headerClassId)}
          >
            <View style={styles.tappableText}>
              <Text style={styles.className}>{headerTitle}</Text>
              {headerMeta ? <Text style={styles.classMeta}>{headerMeta}</Text> : null}
            </View>
            {headerClassId ? <Ionicons name="chevron-forward" size={16} color={C.gray300} /> : null}
          </TouchableOpacity>
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
          {/* Once the class is open the card controls it (End class / +15 min below); the
              Attendance card opens the live screen */}
          {!sessionOpen && (
            <TouchableOpacity
              style={[styles.sessionToggleBtn, styles.toggleOpen, (starting || !firstClass) && styles.btnDisabled]}
              testID="home-start-now"
              onPress={handleSessionButton}
              disabled={starting || !firstClass}
            >
              <Ionicons name="play-circle-outline" size={16} color="#fff" />
              <Text style={styles.toggleText}>{starting ? ' …' : ' Start now'}</Text>
            </TouchableOpacity>
          )}
        </View>

        {sessionOpen && <SessionControls session={activeSession} />}

        {!sessionOpen && (
          <>
            <View style={styles.cardDivider} />
            {firstClass ? (
              <View style={styles.cardExtra}>
                <Ionicons name="school" size={14} color={C.green} style={{ marginTop: 1 }} />
                <Text style={styles.cardExtraText}>
                  {firstClass.code} is ongoing — tap Start now to take attendance.
                </Text>
              </View>
            ) : nextClasses.length ? (
              <View>
                <View style={styles.cardExtraHeader}>
                  <Ionicons name="calendar-outline" size={13} color={C.textSub} />
                  <Text style={styles.cardExtraLabel}>Upcoming</Text>
                </View>
                {nextClasses.map((c, i) => (
                  <TouchableOpacity
                    key={c.id}
                    style={[styles.nextClassRow, i > 0 && styles.nextClassRowBorder]}
                    testID="home-upcoming-class"
                    onPress={() => openClass(c.id)}
                  >
                    <View style={styles.tappableText}>
                      <Text style={styles.cardExtraTitle}>{c.code} — {c.name}</Text>
                      <Text style={styles.cardExtraMeta}>
                        {nextLabel(c)}{c.room ? ` · ${c.room}` : ''}
                      </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={C.gray300} />
                  </TouchableOpacity>
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

      {pendingFaces > 0 && (
        <TouchableOpacity
          style={styles.faceBanner}
          testID="home-face-review"
          onPress={() => navigation.navigate('FaceVerification')}
        >
          <Ionicons name="id-card-outline" size={18} color={C.orangeDk} />
          <Text style={styles.faceBannerText}>{pendingLabel(pendingFaces)}</Text>
          <Ionicons name="chevron-forward" size={16} color={C.orangeDk} />
        </TouchableOpacity>
      )}

      {sessionOpen && (
        <>
          {/* Attendance */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Attendance</Text>
          </View>
          <TouchableOpacity
            style={styles.card}
            testID="home-attendance"
            onPress={() => openLive(activeSession)}
          >
            <Text style={styles.cardExtraMeta}>{activeSession.class_code} · live</Text>
            <View style={styles.attendCounts}>
              <AttendanceCounts counts={sessionCounts(activeSession)} open testIDPrefix="home-count" />
            </View>
            <View style={styles.cardFooter}>
              <Ionicons name="chevron-forward" size={12} color={C.textHint} />
              <Text style={styles.cardFooterText}> Tap to view full attendance</Text>
            </View>
          </TouchableOpacity>

          {/* The running class's questions, polls and signals (Module 5) */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Interaction</Text>
          </View>
          <InteractionHomeCard
            sessionId={activeSession.id} live label={activeSession.class_code}
            testID="home-interaction" refreshKey={refreshKey}
            onPress={() => navigation.navigate('LiveInteraction', { sessionId: activeSession.id })}
          />
        </>
      )}

      {dash.status === 'loading' && <LoadingCard />}
      {dash.data ? (
        // While a class is live the card above has its live numbers; otherwise the latest session's
        !sessionOpen && (
          <LatestOverview data={dash.data} openClass={openClass} refreshKey={refreshKey}
            openInteraction={(o) => navigation.navigate(
              o.session_status === 'open' ? 'LiveInteraction' : 'InteractionSummary', { sessionId: o.session_id })} />
        )
      ) : null}

      {/* Every class taught, to set its schedule or start it (FR-301, FR-316) */}
      {allClasses.length > 0 && (
        <>
          <View style={[styles.sectionHeader, { paddingTop: 4 }]}>
            <Text style={styles.sectionTitle}>My classes</Text>
          </View>
          <View style={styles.card}>
            {allClasses.map((c, i) => (
              <TouchableOpacity
                key={c.id}
                style={[styles.myClassRow, i > 0 && styles.nextClassRowBorder]}
                testID="home-my-class"
                onPress={() => openClass(c.id)}
              >
                <View style={styles.tappableText}>
                  <Text style={styles.cardExtraTitle}>
                    {c.code} {c.type === 'LECTURE' ? 'Lecture' : (c.label ?? 'Tutorial')}
                  </Text>
                  <Text style={styles.cardExtraMeta}>
                    {c.day_of_week ? `${c.day_of_week} ${c.start_time}–${c.end_time}` : 'No fixed time'}
                    {c.room ? ` · ${c.room}` : ''}
                  </Text>
                </View>
                {sessions.some(s => s.class_id === c.id && s.open)
                  ? <Badge variant="green" dot>Live</Badge>
                  : null}
                <Ionicons name="chevron-forward" size={16} color={C.gray300} />
              </TouchableOpacity>
            ))}
          </View>
        </>
      )}

      <View style={{ height: 20 }} />
    </ScrollView>
  </>)
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: {
    backgroundColor: C.bg,
    paddingHorizontal: 16,
    paddingBottom: 20,
  },
  faceBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: C.orangeLt,
    borderWidth: 1,
    borderColor: C.orange,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginTop: 12,
  },
  faceBannerText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: C.orangeDk,
  },
  appHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  logoIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandName: {
    fontSize: 18,
    fontWeight: '800',
    color: C.text,
    letterSpacing: -0.3,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  profileBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileInitials: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
  dashHeader: {
    backgroundColor: C.card,
    borderRadius: 14,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  dashHeaderTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
    marginBottom: 10,
  },
  className: {
    fontSize: 16,
    fontWeight: '700',
    color: C.text,
    marginBottom: 2,
  },
  classMeta: {
    fontSize: 12,
    color: C.textSub,
  },
  dashHeaderBot: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  metaSmall: {
    fontSize: 12,
    color: C.textSub,
  },
  rowGap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  sessionToggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    gap: 4,
  },
  toggleOpen: {
    backgroundColor: C.green,
  },
  toggleText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
  btnDisabled: {
    opacity: 0.45,
  },
  controls: {
    marginTop: 12,
    gap: 8,
  },
  btnRow: {
    flexDirection: 'row',
    gap: 8,
  },
  ctrlBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    paddingVertical: 9,
    borderRadius: 8,
  },
  ctrlOutline: {
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: C.card,
  },
  ctrlDanger: {
    backgroundColor: C.red,
  },
  ctrlOutlineText: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
    marginBottom: 6,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.border,
  },
  attendCounts: {
    marginTop: 8,
    marginBottom: 12,
  },
  overviewTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  cardFooterText: {
    fontSize: 12,
    color: C.textHint,
  },
  cardDivider: {
    height: 1,
    backgroundColor: C.border,
    marginVertical: 12,
  },
  cardExtra: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  cardExtraText: {
    flex: 1,
    fontSize: 12,
    color: C.textSub,
    lineHeight: 18,
  },
  cardExtraHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginBottom: 8,
  },
  cardExtraLabel: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    color: C.textHint,
    marginBottom: 2,
  },
  cardExtraTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
    marginBottom: 2,
  },
  cardExtraMeta: {
    fontSize: 12,
    color: C.textSub,
  },
  nextClassRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: 8,
    gap: 8,
  },
  tappableClass: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  tappableText: {
    flex: 1,
    gap: 2,
  },
  myClassRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    gap: 8,
  },
  nextClassRowBorder: {
    borderTopWidth: 1,
    borderTopColor: C.border,
    marginTop: 8,
  },
})
