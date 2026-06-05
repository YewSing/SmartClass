import { useEffect, useMemo, useState } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Badge from '../components/Badge'
import ModalRouter from '../components/Modals'
import { QUIZZES } from '../data/mockData'
import { C } from '../theme'

const DAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function nowHHMM() {
  const n = new Date()
  return `${String(n.getHours()).padStart(2, '0')}:${String(n.getMinutes()).padStart(2, '0')}`
}

function computeNextClass(allClasses) {
  if (!allClasses.length) return null
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
    .sort((a, b) => a.daysAway - b.daysAway || a.start_time.localeCompare(b.start_time))[0] ?? null
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

  const activeSession = sessions.find(s => s.open)
  const sessionOpen   = Boolean(activeSession)
  const firstClass    = classes[0]
  const nextClass     = useMemo(() => computeNextClass(allClasses), [allClasses])

  const handleToggleSession = async () => {
    if (toggling) return
    setToggling(true)
    try {
      if (sessionOpen) {
        await doCloseSession(activeSession.id)
      } else if (firstClass) {
        await doOpenSession(firstClass.id)
      }
    } catch { /* toast shown in context */ } finally {
      setToggling(false)
    }
  }

  const badgeVariant = sessionOpen ? 'green' : firstClass ? 'yellow' : 'gray'
  const badgeText    = sessionOpen ? 'Session Open' : firstClass ? 'Class Ongoing' : 'No Class Now'

  const headerTitle = firstClass
    ? `${firstClass.code} — ${firstClass.name}`
    : nextClass
      ? `${nextClass.code} — ${nextClass.name}`
      : 'No classes this week'

  const headerMeta = firstClass
    ? `${firstClass.day_of_week} ${firstClass.start_time}–${firstClass.end_time}${firstClass.room ? ` · ${firstClass.room}` : ''}`
    : nextClass
      ? `Next: ${nextLabel(nextClass)}`
      : ''

  return (<>
    <ScrollView
      style={styles.flex}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + 8 }]}
      showsVerticalScrollIndicator={false}
    >
      {/* App header */}
      <View style={styles.appHeader}>
        <View style={styles.brand}>
          <View style={styles.logoIcon}>
            <Ionicons name="school" size={18} color={C.primary} />
          </View>
          <Text style={styles.brandName}>SmartClass</Text>
        </View>
        <TouchableOpacity style={styles.profileBtn} onPress={() => navigation.navigate('Profile')}>
          <Text style={styles.profileInitials}>{lecturer?.initials ?? 'ME'}</Text>
        </TouchableOpacity>
      </View>

      {/* Dash header card */}
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
      </View>

      {sessionOpen ? (
        <>
          {/* Attendance */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Attendance</Text>
          </View>
          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate('AttendanceSessions')}
          >
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

          {/* Quiz section */}
          <View style={[styles.sectionHeader, { paddingTop: 4 }]}>
            <Text style={styles.sectionTitle}>Quiz &amp; Poll</Text>
          </View>
          <TouchableOpacity style={styles.createQuizBtn} onPress={() => navigation.navigate('CreateQuiz')}>
            <View style={styles.createQuizIcon}>
              <Ionicons name="add" size={18} color={C.primary} />
            </View>
            <View style={styles.flex}>
              <Text style={styles.createQuizTitle}>Create Quiz / Poll</Text>
              <Text style={styles.createQuizSub}>Push instantly to all student desks</Text>
            </View>
            <Ionicons name="chevron-forward" size={14} color={C.primary} />
          </TouchableOpacity>

          {QUIZZES.map(q => (
            <TouchableOpacity key={q.id} style={styles.quizCardItem} onPress={() => openModal('quiz', q)}>
              <View style={styles.quizCardTop}>
                <Text style={styles.quizQ} numberOfLines={2}>{q.question}</Text>
                <Badge variant={q.status === 'active' ? 'blue' : q.status === 'closed' ? 'gray' : 'yellow'}>
                  {q.status.charAt(0).toUpperCase() + q.status.slice(1)}
                </Badge>
              </View>
              <View style={styles.rowGap}>
                <Ionicons name="time-outline" size={11} color={C.textHint} />
                <Text style={styles.metaSmall}>Today, {q.time}{q.timer ? ` · ${q.timer} timer` : ''}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </>
      ) : firstClass ? (
        <View style={styles.emptyState}>
          <Ionicons name="school" size={40} color={C.green} style={{ marginBottom: 12 }} />
          <Text style={styles.emptyTitle}>Class is in Progress</Text>
          <Text style={styles.emptySub}>
            {firstClass.code} is ongoing. Open a session to start attendance tracking.
          </Text>
          <TouchableOpacity
            style={[styles.openSessionBtn, toggling && styles.btnDisabled]}
            onPress={handleToggleSession}
            disabled={toggling}
          >
            <Ionicons name="play-circle-outline" size={16} color="#fff" />
            <Text style={styles.openSessionText}>{toggling ? 'Opening…' : ' Open Session'}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.emptyState}>
          <Ionicons name="hourglass-outline" size={40} color={C.textHint} style={{ marginBottom: 12 }} />
          <Text style={styles.emptyTitle}>No Class Right Now</Text>
          {nextClass ? (
            <View style={styles.nextClassCard}>
              <Text style={styles.nextClassLabel}>Next Class</Text>
              <Text style={styles.nextClassName}>{nextClass.code} — {nextClass.name}</Text>
              <View style={styles.rowGap}>
                <Ionicons name="calendar-outline" size={12} color={C.textSub} />
                <Text style={styles.nextClassMeta}>{nextLabel(nextClass)}</Text>
                {nextClass.room ? (
                  <>
                    <Ionicons name="location-outline" size={12} color={C.textSub} />
                    <Text style={styles.nextClassMeta}>{nextClass.room}</Text>
                  </>
                ) : null}
              </View>
            </View>
          ) : (
            <Text style={styles.emptySub}>No upcoming classes scheduled this week.</Text>
          )}
          <TouchableOpacity style={[styles.openSessionBtn, styles.btnDisabled]} disabled>
            <Ionicons name="play-circle-outline" size={16} color="#fff" />
            <Text style={styles.openSessionText}> Open Session</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Environment strip */}
      <View style={[styles.sectionHeader, { paddingTop: 8, paddingBottom: 6 }]}>
        <Text style={styles.sectionTitle}>Environment</Text>
        <Text style={styles.envHint}>Always live · not session-bound</Text>
      </View>
      <TouchableOpacity style={styles.envStrip} onPress={() => navigation.navigate('Environment')}>
        <View style={styles.envStripTop}>
          <Text style={styles.envStripTitle}>Live Sensors — DK 6</Text>
          <Ionicons name="chevron-forward" size={14} color={C.textSub} />
        </View>
        <View style={styles.envMetrics}>
          {[
            { val: '26.4', unit: '°C', lbl: 'Temp' },
            { val: '1240', unit: 'ppm', lbl: 'CO₂' },
            { val: '420', unit: 'lux', lbl: 'Light' },
            { val: '—', unit: 'pax', lbl: 'Occupancy' },
          ].map(m => (
            <View key={m.lbl} style={styles.envMetric}>
              <Text style={styles.envVal}>{m.val}</Text>
              <Text style={styles.envUnit}>{m.unit}</Text>
              <Text style={styles.envLbl}>{m.lbl}</Text>
            </View>
          ))}
        </View>
      </TouchableOpacity>
      <View style={{ height: 20 }} />
    </ScrollView>
    <ModalRouter navigation={navigation} />
  </>)
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: {
    backgroundColor: C.bg,
    paddingHorizontal: 16,
    paddingBottom: 20,
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
  toggleClose: {
    backgroundColor: C.red,
  },
  toggleText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
  btnDisabled: {
    opacity: 0.45,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
    marginBottom: 6,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: C.textSub,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  envHint: {
    fontSize: 11,
    color: C.textHint,
    fontStyle: 'italic',
  },
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.border,
  },
  attendStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 12,
  },
  attendStat: {
    alignItems: 'center',
  },
  attendNum: {
    fontSize: 28,
    fontWeight: '800',
  },
  attendLbl: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 2,
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
    fontWeight: '700',
    color: C.text,
  },
  createQuizSub: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 1,
  },
  quizCardItem: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: C.border,
    gap: 6,
  },
  quizCardTop: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
  },
  quizQ: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
    lineHeight: 19,
  },
  emptyState: {
    alignItems: 'center',
    padding: 24,
    marginVertical: 16,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: C.text,
    marginBottom: 8,
  },
  emptySub: {
    fontSize: 13,
    color: C.textSub,
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 20,
  },
  openSessionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.green,
    borderRadius: 10,
    paddingHorizontal: 20,
    paddingVertical: 12,
    marginTop: 8,
    gap: 6,
  },
  openSessionText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },
  nextClassCard: {
    backgroundColor: C.gray50,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
    width: '100%',
    gap: 4,
  },
  nextClassLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    color: C.textHint,
    marginBottom: 2,
  },
  nextClassName: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
    marginBottom: 4,
  },
  nextClassMeta: {
    fontSize: 12,
    color: C.textSub,
  },
  envStrip: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  envStripTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  envStripTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
  },
  envMetrics: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  envMetric: {
    alignItems: 'center',
  },
  envVal: {
    fontSize: 18,
    fontWeight: '700',
    color: C.text,
  },
  envUnit: {
    fontSize: 10,
    color: C.textSub,
  },
  envLbl: {
    fontSize: 10,
    color: C.textHint,
    marginTop: 2,
  },
})
