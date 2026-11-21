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
import * as api from '../services/api'
import { sessionCounts } from '../services/attendance'
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

export default function Dashboard({ navigation }) {
  const {
    state, loadClasses, loadAllClasses, loadSessions, doOpenSession, selectSession, showToast,
  } = useLecturer()
  const { sessions, classes, allClasses, lecturer } = state
  const insets = useSafeAreaInsets()
  const [starting, setStarting] = useState(false)
  const [confirmEnd, setConfirmEnd] = useState(false)

  const EXTEND_MINUTES = 15

  // ── Interaction session toggle (UC-501, S26): open/close lives on Home ──
  const [openInteractions, setOpenInteractions] = useState([])

  const loadOpenInteractions = useCallback(async () => {
    try { setOpenInteractions(await api.getOpenInteractions()) } catch { /* card hides on failure */ }
  }, [])

  useEffect(() => { loadClasses(); loadAllClasses(); loadOpenInteractions() }, [])
  // The schedule opens and closes classes by itself, so re-read on every visit
  useFocusEffect(useCallback(() => { loadSessions(); loadOpenInteractions() }, [loadSessions, loadOpenInteractions]))

  // Face enrolments waiting for this lecturer (FR-113); a failed count just hides the banner
  const [pendingFaces, setPendingFaces] = useState(0)
  const loadPendingFaces = useCallback(async () => {
    try { setPendingFaces((await api.getPendingFaceSubmissions()).length) } catch { setPendingFaces(0) }
  }, [])
  useFocusEffect(useCallback(() => { loadPendingFaces() }, [loadPendingFaces]))

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadClasses(), loadSessions(), loadAllClasses(), loadPendingFaces(), loadOpenInteractions()])
    setRefreshing(false)
  }, [loadClasses, loadSessions, loadAllClasses, loadPendingFaces, loadOpenInteractions])

  const activeSession = sessions.find(s => s.open)
  const sessionOpen   = Boolean(activeSession)
  const firstClass    = classes[0]
  const nextClasses   = useMemo(() => computeNextClasses(allClasses), [allClasses])
  const nextClass     = nextClasses[0] ?? null
  const headerClassId = firstClass?.id ?? nextClass?.id

  const openLive = (session) => {
    selectSession(session)
    navigation.navigate('AttendanceDetail')
  }

  // Open Session starts both the attendance session and the interaction session for the
  // current class; reopening the same class time range reuses the single session record.
  const handleOpenSession = async () => {
    if (starting || !headerClassId) return
    setStarting(true)
    try {
      await doOpenSession(headerClassId)
      await api.openInteraction(headerClassId)
      await loadSessions()
      await loadOpenInteractions()
      showToast('Session opened', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setStarting(false)
    }
  }

  // End Class ends both the attendance session and the interaction session simultaneously.
  const handleEndClass = async () => {
    if (starting) return
    setConfirmEnd(true)
  }

  const doEndClass = async () => {
    setConfirmEnd(false)
    setStarting(true)
    try {
      const calls = []
      if (activeSession) calls.push(api.closeSession(activeSession.id))
      if (currentInteraction) calls.push(api.closeInteraction(currentInteraction.id))
      await Promise.all(calls)
      await loadSessions()
      await loadOpenInteractions()
      showToast('Class ended', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setStarting(false)
    }
  }

  // +15 min extends both sessions by 15 minutes.
  const handleExtendSession = async () => {
    if (starting) return
    setStarting(true)
    try {
      const calls = []
      if (activeSession) calls.push(api.extendSession(activeSession.id, EXTEND_MINUTES))
      if (currentInteraction) calls.push(api.extendInteraction(currentInteraction.id, EXTEND_MINUTES))
      await Promise.all(calls)
      await loadSessions()
      await loadOpenInteractions()
      showToast('Extended by 15 min', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setStarting(false)
    }
  }

  const badgeVariant = sessionOpen ? 'green' : firstClass ? 'yellow' : 'gray'
  const badgeText    = sessionOpen ? 'Session Open' : firstClass ? 'Class Ongoing' : 'No Class Now'

  // Interaction (Module 5): the live session for the current class, if any.
  const currentInteraction = headerClassId
    ? openInteractions.find(i => i.occurrence_id === headerClassId) ?? null
    : openInteractions[0] ?? null

  const headerTitle = firstClass
    ? `${firstClass.code} — ${firstClass.name}`
    : nextClass
      ? `${nextClass.code} — ${nextClass.name}`
      : 'No classes this week'

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
        <TouchableOpacity style={styles.profileBtn} accessibilityLabel="Profile" onPress={() => navigation.navigate('Profile')}>
          <Text style={styles.profileInitials}>{lecturer?.initials ?? 'ME'}</Text>
        </TouchableOpacity>
      </View>

      {/* Dash header card */}
      <View style={styles.dashHeader}>
        <View style={styles.dashHeaderTop}>
          <TouchableOpacity
            style={[styles.tappableClass, { justifyContent: 'space-between', alignItems: 'center' }]}
            testID="home-class-card"
            disabled={!headerClassId}
            onPress={() => openClass(headerClassId)}
          >
            <View style={styles.tappableText}>
              <Text style={styles.className}>{headerTitle}</Text>
              {headerMeta ? <Text style={styles.classMeta}>{headerMeta}</Text> : null}
            </View>
            <Badge variant={badgeVariant} dot>{badgeText}</Badge>
            {headerClassId ? <Ionicons name="chevron-forward" size={16} color={C.gray300} /> : null}
          </TouchableOpacity>
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
          {/* Unified session controls: Open Session starts both sessions; End Class / +15 min
               end or extend both the attendance and interaction session. */}
          <View style={styles.sessionControls}>
            {sessionOpen ? (
              <>
                <TouchableOpacity
                  style={styles.sessionEndBtn}
                  testID="home-end-class"
                  onPress={handleEndClass}
                  disabled={starting}
                  accessibilityLabel="End class"
                >
                  <Ionicons name="stop-circle-outline" size={16} color="#fff" />
                  <Text style={styles.sessionBtnText}>End Class</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.sessionExtendBtn}
                  testID="home-extend-session"
                  onPress={handleExtendSession}
                  disabled={starting}
                  accessibilityLabel="Extend session"
                >
                  <Ionicons name="add-circle-outline" size={16} color="#fff" />
                  <Text style={styles.sessionBtnText}>+15 min</Text>
                </TouchableOpacity>
              </>
            ) : (
              <TouchableOpacity
                style={styles.sessionOpenBtn}
                testID="home-open-session"
                onPress={handleOpenSession}
                disabled={starting || !headerClassId}
                accessibilityLabel="Open session"
              >
                <Ionicons name="play-circle-outline" size={16} color="#fff" />
                <Text style={styles.sessionBtnText}>Open Session</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        {confirmEnd && sessionOpen && (
          <View style={styles.confirmBlock}>
            <Text style={styles.confirmText}>
              End the class now? Anyone not recorded is marked Absent and the marks are sent to SPeCTRUM.
            </Text>
            <View style={styles.btnRow}>
              <TouchableOpacity style={styles.confirmCancel} onPress={() => setConfirmEnd(false)}>
                <Text style={styles.confirmBtnText}>Keep running</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.confirmEndBtn} onPress={doEndClass} disabled={starting}>
                <Text style={styles.confirmBtnText}>{starting ? 'Ending…' : 'End now'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

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

          {/* Quiz section */}
          <View style={[styles.sectionHeader, { paddingTop: 4 }]}>
            <Text style={styles.sectionTitle}>Quiz &amp; Poll</Text>
          </View>
          <TouchableOpacity style={styles.createQuizBtn} onPress={() => navigation.navigate('Quiz', { screen: 'CreateQuiz' })}>
            <View style={styles.createQuizIcon}>
              <Ionicons name="add" size={18} color={C.primary} />
            </View>
            <View style={styles.flex}>
              <Text style={styles.createQuizTitle}>Create Quiz / Poll</Text>
              <Text style={styles.createQuizSub}>Push instantly to all student desks</Text>
            </View>
            <Ionicons name="chevron-forward" size={14} color={C.primary} />
          </TouchableOpacity>
        </>
      )}

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
  sessionControls: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10,
  },
  sessionOpenBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, backgroundColor: C.green, borderRadius: 9,
    paddingHorizontal: 12, paddingVertical: 9,
  },
  sessionEndBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, backgroundColor: C.red, borderRadius: 9,
    paddingHorizontal: 12, paddingVertical: 9,
  },
  sessionExtendBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, backgroundColor: C.primary, borderRadius: 9,
    paddingHorizontal: 12, paddingVertical: 9,
  },
  sessionBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  confirmBlock: {
    backgroundColor: C.card, marginTop: 10, borderRadius: 10,
    borderWidth: 1, borderColor: C.border, padding: 12, gap: 10,
  },
  confirmText: { fontSize: 12, color: C.textSub, lineHeight: 18 },
  btnRow: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 2 },
  confirmCancel: { paddingVertical: 6, paddingHorizontal: 10 },
  confirmEndBtn: {
    backgroundColor: C.red, borderRadius: 8, paddingVertical: 6, paddingHorizontal: 12,
  },
  confirmBtnText: { fontSize: 12, fontWeight: '700', color: '#fff' },
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
  createQuizBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: C.border,
    gap: 12,
  },
  createQuizIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  createQuizTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  createQuizSub: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 1,
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
