import { useCallback, useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Linking, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import * as api from '../services/api'
import { formatDashboardTime, formatMoodleDate, isDashboardStale, safeMoodleUrl } from '../services/dashboard'
import { C } from '../theme'

// Section accents give each block its own colour so the page has a clear visual focus
const ACCENTS = {
  today:      { dot: C.green,  soft: C.greenLt,  dark: C.greenDk },
  spectrum:   { dot: C.orange, soft: C.orangeLt, dark: C.orangeDk },
  classes:    { dot: C.purple, soft: C.purpleLt, dark: C.purple },
}

// Slot type chips: Lecture and Tutorial get different colours
const SLOT_CHIP = {
  LECTURE:   { backgroundColor: C.greenLt,  color: C.greenDk },
  TUTORIAL:  { backgroundColor: C.orangeLt, color: C.orangeDk },
  OTHER:     { backgroundColor: C.gray100,  color: C.gray600 },
}

// Attendance status → chip colours. "Not recorded" is grey, not blue.
const STATUS_STYLE = {
  present:      { label: 'Present',      style: { backgroundColor: C.greenLt,  color: C.greenDk } },
  late:         { label: 'Late',         style: { backgroundColor: C.yellowLt, color: C.yellowDk } },
  excused:      { label: 'Excused',      style: { backgroundColor: C.blueLt,   color: C.blueDk } },
  absent:       { label: 'Absent',       style: { backgroundColor: C.redLt,    color: C.redDk } },
  not_recorded: { label: 'Not recorded', style: { backgroundColor: C.gray100,  color: C.gray600 } },
}
const statusChip = status => STATUS_STYLE[status] ?? { label: 'No attendance yet', style: { backgroundColor: C.gray100, color: C.gray600 } }

const Section = ({ title, accent, meta, children }) => (
  <View style={s.section}>
    <View style={s.sectionHead}>
      <Text style={[s.sectionText, { color: accent.dark }]}>{title}</Text>
      {meta ? <Text style={s.sectionMeta}>{meta}</Text> : null}
    </View>
    {children}
  </View>
)
const Empty = ({ icon, title, text, accent }) => (
  <View style={[s.empty, { borderColor: accent.soft }]}>
    <Ionicons name={icon} size={22} color={accent.dark} />
    <View style={s.grow}>
      <Text style={s.cardTitle}>{title}</Text>
      {text ? <Text style={s.meta}>{text}</Text> : null}
    </View>
  </View>
)

export default function Home({ navigation }) {
  const { state, loadClasses } = useStudent(), insets = useSafeAreaInsets()
  const [data, setData] = useState(null), [unread, setUnread] = useState(0), [loading, setLoading] = useState(true), [refreshing, setRefreshing] = useState(false), [error, setError] = useState('')
  const load = useCallback(async (refresh = false) => { refresh ? setRefreshing(true) : setLoading(true); setError(''); try { const [summary, count] = await Promise.all([api.getDashboard(), api.getNotificationUnreadCount()]); setData(summary); setUnread(count) } catch { setError('Dashboard could not be refreshed. Last loaded information is kept on screen.') } finally { setLoading(false); setRefreshing(false) } }, [])
  useEffect(() => { loadClasses() }, [loadClasses])
  useFocusEffect(useCallback(() => {
    let active = true
    load()
    // Discovery covers any enrolled occurrence, including a class opened after Home loaded.
    const timer = setInterval(async () => {
      try {
        const summary = await api.getDashboard()
        if (active) setData(summary)
      } catch { /* keep the last snapshot until the next refresh */ }
    }, 15000)
    return () => { active = false; clearInterval(timer) }
  }, [load]))
  const openMoodle = async value => { const url = safeMoodleUrl(value); if (url && await Linking.canOpenURL(url)) await Linking.openURL(url) }
  const notices = data?.notifications ?? [], session = data?.session
  const liveSessions = data?.live_sessions ?? []

  // Enrolled classes are grouped by course, not by weekly occurrence —
  // each course keeps every occurrence (Lecture / Tutorial) with its own time and room
  const courses = useMemo(() => {
    const seen = new Map()
    for (const c of state.classes) {
      if (!seen.has(c.code)) seen.set(c.code, { id: c.id, code: c.code, name: c.name, slots: [] })
      if (c.day_of_week) seen.get(c.code).slots.push({
        label: c.label ?? c.type ?? '',
        text: `${c.day_of_week} ${c.start_time}${c.end_time ? `–${c.end_time}` : ''}`,
        venue: c.venue,
      })
    }
    return [...seen.values()]
  }, [state.classes])

  // Today's class card state: live session → open/closed; no session yet → upcoming
  const todayState = c => {
    if (session?.occurrence_id === c.occurrence_id) {
      return session.status === 'open'
        ? { chip: 'Live now', style: [s.chip, s.chipLive], time: null }
        : { chip: 'Ended', style: [s.chip, s.chipGray], time: null }
    }
    return { chip: 'Upcoming', style: [s.chip, s.chipBlue], time: c.start_time ? `Starts ${c.start_time}` : null }
  }
  // A class with a session deep-links to its session detail; otherwise to the attendance tab
  const openClass = c => {
    if (session?.occurrence_id === c.occurrence_id) {
      navigation.navigate('Attendance', { screen: 'AttSessionDetail', params: { courseId: c.course_id, sessionId: session.id } })
    } else navigation.navigate('Attendance')
  }

  return <ScrollView style={s.page} contentContainerStyle={[s.content, { paddingTop: insets.top + 12 }]} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)}/>}>
    <View style={s.topbar}><View style={s.brand}><View style={s.logoIcon}><Ionicons name="school" size={18} color={C.primary}/></View><Text style={s.brandName}>SmartClass</Text></View><View style={s.headerActions}>
      <TouchableOpacity style={s.bell} onPress={() => navigation.navigate('Notifications')} accessibilityLabel="Notifications" testID="home-notifications"><Ionicons name="notifications-outline" size={20} color={C.text}/>{unread ? <View style={s.badge}><Text style={s.badgeText}>{unread > 9 ? '9+' : unread}</Text></View> : null}</TouchableOpacity>
      <TouchableOpacity style={s.profileBtn} accessibilityLabel="Profile" onPress={() => navigation.navigate('Profile')}><Text style={s.profileInitials}>{(state.student?.name ?? 'Me').split(' ').filter(Boolean).map(w => w[0]).slice(0, 2).join('').toUpperCase()}</Text></TouchableOpacity>
    </View></View>
    <View style={s.header}><View style={s.grow}><Text style={s.title}>Hello, {state.student?.name?.split(' ')[0] ?? 'student'}</Text><Text style={s.meta}>Here’s what needs your attention today.</Text></View></View>
    {error ? <View style={s.error}><Text style={s.errorText}>{error}</Text><TouchableOpacity onPress={() => load()}><Text style={s.retry}>Retry</Text></TouchableOpacity></View> : null}
    {loading && !data ? <ActivityIndicator style={{ marginTop: 50 }} color={C.primary}/> : null}
    {data ? <>
      {notices.length ? <Section title="Priority notices" accent={ACCENTS.today}>{notices.map(n => <TouchableOpacity key={n.id} style={[s.notice, n.priority === 'urgent' ? s.urgent : s.important]} onPress={() => navigation.navigate('Notifications')}><Ionicons name="alert-circle-outline" size={19} color={n.priority === 'urgent' ? C.redDk : C.orangeDk}/><View style={s.grow}><Text style={s.cardTitle}>{n.title}</Text><Text style={s.meta}>{n.message}</Text></View></TouchableOpacity>)}</Section> : null}

      {liveSessions.length ? <Section title="Live classes" accent={ACCENTS.today}>
        {liveSessions.map(live => <TouchableOpacity
          key={live.id}
          testID={`join-live-class-${live.course_code}`}
          accessibilityRole="button"
          accessibilityLabel={`Join live class ${live.course_code}`}
          style={[s.card, s.cardAccent(C.green)]}
          onPress={() => navigation.navigate('LiveClass', {
            sessionId: live.id, courseCode: live.course_code, courseName: live.course_name,
          })}
        >
          <View style={s.row}>
            <View style={s.grow}>
              <Text style={[s.code, { color: C.greenDk }]}>{live.course_code} · Live now</Text>
              <Text style={s.cardTitle}>{live.course_name}</Text>
            </View>
            <Text style={[s.chip, s.chipLive]}>Join</Text>
          </View>
        </TouchableOpacity>)}
      </Section> : null}

      <Section title="Today’s classes" accent={ACCENTS.today}>
        {data.today_classes.map(c => { const t = todayState(c); const chip = c.attendance_status ? statusChip(c.attendance_status) : null; return <TouchableOpacity key={c.occurrence_id} style={[s.card, s.cardAccent(ACCENTS.today.soft)]} onPress={() => openClass(c)}>
          <View style={s.row}><View style={s.grow}><Text style={s.code}>{c.course_code}</Text><Text style={s.cardTitle}>{c.course_name}</Text><Text style={s.meta}>{[c.start_time && c.end_time ? `${c.start_time}–${c.end_time}` : null, c.room].filter(Boolean).join(' · ') || 'Time and room pending'}</Text></View><View style={s.stateCol}>
            <Text style={t.style}>{t.chip}</Text>
            {t.time ? <Text style={s.chipTime}>{t.time}</Text> : null}
            {chip ? <Text style={[s.chip, chip.style]}>{chip.label}</Text> : null}
          </View></View>
        </TouchableOpacity> })}
        {!data.today_classes.length ? <Empty icon="calendar-outline" title="No classes today" text="Use this time to review upcoming work." accent={ACCENTS.today}/> : null}
      </Section>

      <Section title="SPeCTRUM" accent={ACCENTS.spectrum} meta={data.moodle.available ? `${isDashboardStale(data.moodle.refreshed_at) ? 'May be outdated · ' : ''}Updated ${formatDashboardTime(data.moodle.refreshed_at)}` : 'SPeCTRUM data is unavailable'}>
        {data.moodle.available ? <>
          <Text style={s.groupLabel}>Upcoming deadlines</Text>
          {data.moodle.deadlines.map(x => <TouchableOpacity key={`d-${x.id}`} style={[s.card, s.cardAccent(ACCENTS.spectrum.soft)]} disabled={!safeMoodleUrl(x.link)} onPress={() => openMoodle(x.link)}><View style={s.row}><Ionicons name="calendar-outline" size={18} color={C.orangeDk}/><View style={s.grow}><Text style={s.cardTitle}>{x.title}</Text><Text style={s.meta}>{x.course_code} · Due {formatMoodleDate(x.date)}</Text></View>{safeMoodleUrl(x.link) ? <Ionicons name="open-outline" size={16} color={C.primary}/> : null}</View></TouchableOpacity>)}
          {!data.moodle.deadlines.length ? <Empty icon="calendar-clear-outline" title="No upcoming deadlines" accent={ACCENTS.spectrum}/> : null}
          <Text style={s.groupLabel}>Announcements</Text>
          {data.moodle.announcements.map(x => <TouchableOpacity key={`a-${x.id}`} style={[s.card, s.cardAccent(ACCENTS.spectrum.soft)]} disabled={!safeMoodleUrl(x.link)} onPress={() => openMoodle(x.link)}><View style={s.row}><Ionicons name="megaphone-outline" size={18} color={C.orangeDk}/><View style={s.grow}><Text style={s.cardTitle}>{x.title}</Text><Text style={s.meta}>{x.course_code} · {formatMoodleDate(x.date)}</Text></View>{safeMoodleUrl(x.link) ? <Ionicons name="open-outline" size={16} color={C.primary}/> : null}</View></TouchableOpacity>)}
          {!data.moodle.announcements.length ? <Empty icon="megaphone-outline" title="No recent announcements" accent={ACCENTS.spectrum}/> : null}
        </> : null}
      </Section>

      <Section title="Enrolled classes" accent={ACCENTS.classes}>
        {courses.map(c => <TouchableOpacity key={c.code} style={[s.card, s.cardAccent(ACCENTS.classes.soft)]} onPress={() => navigation.navigate('Attendance')}>
          <View style={s.grow}><Text style={[s.code, { color: ACCENTS.classes.dark }]}>{c.code}</Text><Text style={s.cardTitle}>{c.name}</Text></View>
          <View style={s.slotList}>{c.slots.map((sl, i) => <View key={`${c.code}-${i}`} style={s.slotRow}>
            {sl.label ? <Text style={[s.slotChip, SLOT_CHIP[sl.label.toUpperCase()] ?? SLOT_CHIP.OTHER]}>{sl.label}</Text> : null}
            <Text style={s.slotText}>{[sl.text, sl.venue].filter(Boolean).join(' · ')}</Text>
          </View>)}
          </View>
        </TouchableOpacity>)}
        {!courses.length ? <Empty icon="school-outline" title="No enrolled classes" accent={ACCENTS.classes}/> : null}
      </Section>
    </> : null}<View style={{ height: 20 }}/>
  </ScrollView>
}

const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: C.bg },
  content: { paddingHorizontal: 16, paddingBottom: 20 },
  topbar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logoIcon: { width: 32, height: 32, borderRadius: 8, backgroundColor: C.blueLt, alignItems: 'center', justifyContent: 'center' },
  brandName: { fontSize: 18, fontWeight: '800', color: C.text, letterSpacing: -0.3 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  profileBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: C.primary, alignItems: 'center', justifyContent: 'center' },
  profileInitials: { fontSize: 13, fontWeight: '700', color: '#fff' },
  header: { marginBottom: 16 },
  grow: { flex: 1 },
  title: { fontSize: 23, fontWeight: '800', color: C.text, marginTop: 3 },
  meta: { fontSize: 12, color: C.textSub, lineHeight: 17, marginTop: 3 },
  bell: { width: 44, height: 44, borderRadius: 12, backgroundColor: C.card, borderWidth: 1, borderColor: C.border, alignItems: 'center', justifyContent: 'center' },
  badge: { position: 'absolute', right: 3, top: 3, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center' },
  badgeText: { fontSize: 9, fontWeight: '800', color: '#fff' },
  section: { marginTop: 14, marginBottom: 4 },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 10 },
  sectionText: { fontSize: 13, fontWeight: '800', letterSpacing: .6, textTransform: 'uppercase' },
  sectionMeta: { fontSize: 11, color: C.textSub, flexShrink: 1, textAlign: 'right' },
  groupLabel: { fontSize: 12, fontWeight: '700', color: C.text, marginTop: 12, marginBottom: 6 },
  card: { padding: 14, borderWidth: 1, borderColor: C.border, borderRadius: 12, backgroundColor: C.card, marginBottom: 8 },
  cardAccent: color => ({ borderLeftWidth: 4, borderLeftColor: color }),
  slotList: { marginTop: 8, gap: 6 },
  slotRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  slotChip: { fontSize: 10, fontWeight: '800', paddingVertical: 3, paddingHorizontal: 8, borderRadius: 7, overflow: 'hidden', textTransform: 'uppercase', letterSpacing: .3 },
  slotText: { fontSize: 12, color: C.textSub },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  stateCol: { alignItems: 'flex-end', gap: 5 },
  code: { fontSize: 11, fontWeight: '800', color: C.primary, marginBottom: 2 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  chip: { fontSize: 10, fontWeight: '700', paddingVertical: 4, paddingHorizontal: 8, borderRadius: 7, overflow: 'hidden' },
  chipLive: { color: '#fff', backgroundColor: C.green },
  chipBlue: { color: C.blueDk, backgroundColor: C.blueLt },
  chipGray: { color: C.gray600, backgroundColor: C.gray100 },
  chipTime: { fontSize: 10, fontWeight: '600', color: C.textSub },
  empty: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderWidth: 1, borderStyle: 'dashed', borderRadius: 12, backgroundColor: C.card, marginBottom: 8 },
  notice: { flexDirection: 'row', gap: 9, padding: 13, borderRadius: 11, borderLeftWidth: 4, marginBottom: 8 },
  urgent: { backgroundColor: C.redLt, borderLeftColor: C.red },
  important: { backgroundColor: C.orangeLt, borderLeftColor: C.orange },
  error: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 11, borderRadius: 10, backgroundColor: C.redLt },
  errorText: { flex: 1, fontSize: 12, color: C.redDk },
  retry: { fontSize: 12, fontWeight: '800', color: C.redDk },
})
