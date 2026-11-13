// FR-201 / FR-204 — student dashboard.
// Layout follows the SmartClassUM dashboard reference: light top app bar,
// a compact live-session strip that links to the Interact page, then full-width
// bordered section cards (Academic Standing & Attendance, Announcements &
// Push Feed, Upcoming Deadlines & Quizzes). Colours reuse the existing theme.
// Frontend only — data comes from module2 fixtures + existing context loaders.
import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import { NOTIFICATIONS, DEADLINES, LIVE_ACTIVITY, PRIORITIES, MY_PROGRESS } from '../data/module2'
import { C } from '../theme'

const PRIORITY_META = {
  urgent:    { label: 'Urgent',    color: C.red,    bg: C.redLt,    text: C.redDk },
  important: { label: 'Important', color: C.orange, bg: C.orangeLt, text: C.orangeDk },
  general:   { label: 'General',   color: C.gray400, bg: C.gray100, text: C.gray600 },
}

const URGENCY_TINT = {
  today: { bg: C.redLt, text: C.redDk },
  soon:  { bg: C.yellowLt, text: C.yellowDk },
  later: { bg: C.gray100, text: C.gray600 },
}

// average quiz score across courses from the M7 fixture (FR-706 own data)
const MY_PROGRESS_AVG = (() => {
  const all = MY_PROGRESS.courses.flatMap(c => c.quizzes)
  if (!all.length) return '—'
  return `${Math.round(all.reduce((a, q) => a + q.score, 0) / all.length)}%`
})()

export default function Home({ navigation }) {
  const { state, loadClasses, loadAttendanceSummary } = useStudent()
  const { student, attendanceSummary } = state
  const insets = useSafeAreaInsets()

  useEffect(() => {
    loadClasses()
    loadAttendanceSummary()
  }, [loadClasses, loadAttendanceSummary])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadClasses(), loadAttendanceSummary()])
    setRefreshing(false)
  }, [loadClasses, loadAttendanceSummary])

  // FR-204 — urgent & important on top, general below.
  const sorted = [...NOTIFICATIONS].sort((a, b) => PRIORITIES[a.priority] - PRIORITIES[b.priority])
  const feed = sorted.slice(0, 4)
  const unreadCount = NOTIFICATIONS.filter(n => !n.read).length

  const present = attendanceSummary?.present ?? 0
  const absent = attendanceSummary?.absent ?? 0
  const totalSessions = present + absent
  const rate = attendanceSummary?.rate ?? (totalSessions ? Math.round((present / totalSessions) * 100) : null)

  return (
    <View style={styles.flex}>
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* ── Top app bar ── */}
        <View style={[styles.topBar, { paddingTop: insets.top + 8 }]}>
          <View style={styles.brandWrap}>
            <View style={styles.logoBox}>
              <Ionicons name="school" size={16} color={C.primary} />
            </View>
            <View>
              <Text style={styles.brandName}>SmartClass</Text>
              <Text style={styles.brandSub}>Student · FSKTM</Text>
            </View>
          </View>
          <View style={styles.topRight}>
            <View style={styles.syncPill}>
              <View style={styles.syncDot} />
              <Text style={styles.syncText}>Moodle Synced</Text>
            </View>
            <TouchableOpacity style={styles.bellBtn} onPress={() => navigation.navigate('Notifications')}>
              <Ionicons name="notifications-outline" size={20} color={C.text} />
              {unreadCount > 0 && (
                <View style={styles.bellBadge}>
                  <Text style={styles.bellBadgeText}>{unreadCount}</Text>
                </View>
              )}
            </TouchableOpacity>
            <TouchableOpacity style={styles.avatar} onPress={() => navigation.navigate('Profile')}>
              <Text style={styles.avatarText}>{student?.initials ?? 'ME'}</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* ── Active live session strip → links to Interact page ── */}
        {LIVE_ACTIVITY.open && (
          <TouchableOpacity
            style={styles.liveStrip}
            activeOpacity={0.85}
            onPress={() => navigation.navigate('Interact')}
          >
            <View style={styles.liveLeft}>
              <View style={styles.liveDotWrap}>
                <View style={styles.liveDot} />
                <Text style={styles.liveTag}>ACTIVE LIVE SESSION</Text>
              </View>
              <Text style={styles.liveCourse} numberOfLines={1}>
                {LIVE_ACTIVITY.course} · {LIVE_ACTIVITY.room}
              </Text>
            </View>
            <View style={styles.liveJoin}>
              <Ionicons name="pulse" size={13} color="#fff" />
              <Text style={styles.liveJoinText}>Join</Text>
              <Ionicons name="chevron-forward" size={13} color="#fff" />
            </View>
          </TouchableOpacity>
        )}

        {/* ── Academic standing & attendance ── */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHead}>
            <View style={styles.sectionIconBox}>
              <Ionicons name="stats-chart" size={13} color={C.primary} />
            </View>
            <Text style={styles.sectionTitle}>Academic Standing & Attendance</Text>
          </View>

          <View style={styles.statGrid}>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>ATTENDANCE RATE</Text>
              <View style={styles.statValueRow}>
                <Text style={[styles.statBig, { color: C.primary }]}>
                  {rate != null ? `${rate}%` : '—'}
                </Text>
              </View>
              <Text style={styles.statSub}>{present} present · {absent} absent</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>CLASSES THIS SEM</Text>
              <View style={styles.statValueRow}>
                <Text style={[styles.statBig, { color: C.green }]}>{totalSessions || '—'}</Text>
              </View>
              <Text style={styles.statSub}>recorded so far</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>QUIZ AVG</Text>
              <View style={styles.statValueRow}>
                <Text style={[styles.statBig, { color: C.text }]}>{MY_PROGRESS_AVG}</Text>
              </View>
              <Text style={styles.statSub}>across all courses</Text>
            </View>
          </View>

          {/* Threshold bar — mirrors the reference's 80% faculty threshold bar */}
          <View style={styles.thresholdRow}>
            <Text style={styles.thresholdLbl}>Mandatory 80% attendance threshold</Text>
            <Text style={styles.thresholdSafe}>
              {rate != null && rate >= 80 ? 'Safe margin' : rate != null ? 'Below threshold' : ''}
            </Text>
          </View>
          <View style={styles.thresholdTrack}>
            <View
              style={[
                styles.thresholdFill,
                { width: `${Math.min(rate ?? 0, 100)}%`, backgroundColor: (rate ?? 0) >= 80 ? C.primary : C.red },
              ]}
            />
            {rate != null && (
              <View style={[styles.thresholdMarker, { left: '80%' }]} />
            )}
          </View>
          <TouchableOpacity style={styles.sectionFootLink} onPress={() => navigation.navigate('Attendance')}>
            <Text style={styles.footLinkText}>View full attendance history</Text>
            <Ionicons name="chevron-forward" size={12} color={C.primary} />
          </TouchableOpacity>
        </View>

        {/* ── Announcements & push feed (FR-204/206) ── */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHead}>
            <View style={styles.sectionIconBox}>
              <Ionicons name="megaphone-outline" size={13} color={C.primary} />
            </View>
            <Text style={styles.sectionTitle}>Announcements & Push Feed</Text>
            {unreadCount > 0 && (
              <View style={styles.newChip}><Text style={styles.newChipText}>{unreadCount} New</Text></View>
            )}
          </View>

          {feed.map((n, i) => {
            const p = PRIORITY_META[n.priority] ?? PRIORITY_META.general
            return (
              <TouchableOpacity
                key={n.id}
                style={[styles.feedRow, i > 0 && styles.feedRowBorder]}
                activeOpacity={0.7}
                onPress={() => navigation.navigate('Notifications')}
              >
                <View style={[styles.feedDot, { backgroundColor: p.color }]} />
                <View style={styles.feedBody}>
                  <View style={styles.feedTopRow}>
                    <Text style={[styles.feedPriority, { color: p.text }]}>
                      {n.priority === 'urgent' ? '● URGENT' : p.label.toUpperCase()}
                    </Text>
                    <Text style={styles.feedTime}>{n.time}</Text>
                  </View>
                  <Text style={styles.feedTitle} numberOfLines={1}>{n.title}</Text>
                  <Text style={styles.feedText} numberOfLines={2}>{n.body}</Text>
                  {n.priority === 'urgent' && (
                    <TouchableOpacity style={styles.ackBtn} onPress={() => navigation.navigate('Notifications')}>
                      <Text style={styles.ackText}>View details</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </TouchableOpacity>
            )
          })}

          <TouchableOpacity style={styles.sectionFootCenter} onPress={() => navigation.navigate('Notifications')}>
            <Text style={styles.footLinkCenter}>Open Notification Feed</Text>
          </TouchableOpacity>
        </View>

        {/* ── Upcoming deadlines & quizzes ── */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHead}>
            <View style={styles.sectionIconBox}>
              <Ionicons name="document-text-outline" size={13} color={C.primary} />
            </View>
            <Text style={styles.sectionTitle}>Upcoming Deadlines & Quizzes</Text>
            <TouchableOpacity onPress={() => navigation.navigate('Quizzes')}>
              <Text style={styles.seeAll}>View all</Text>
            </TouchableOpacity>
          </View>

          {DEADLINES.map((d, i) => {
            const t = URGENCY_TINT[d.urgency] ?? URGENCY_TINT.later
            return (
              <View key={d.id} style={[styles.deadlineRow, i > 0 && styles.feedRowBorder]}>
                <View style={styles.deadlineIconBox}>
                  <Ionicons
                    name={d.urgency === 'today' ? 'alert-circle' : 'help-circle'}
                    size={18}
                    color={d.urgency === 'today' ? C.primary : C.textSub}
                  />
                </View>
                <View style={styles.deadlineBody}>
                  <View style={styles.deadlineTags}>
                    <View style={styles.courseTag}><Text style={styles.courseTagText}>{d.course}</Text></View>
                    <Text style={[styles.deadlineDue, { color: t.text }]}>⏱ {d.due}</Text>
                  </View>
                  <Text style={styles.deadlineTitle} numberOfLines={1}>{d.title}</Text>
                  <Text style={styles.deadlineMeta} numberOfLines={1}>{d.questions}</Text>
                </View>
                <TouchableOpacity style={styles.launchBtn} onPress={() => navigation.navigate('Quizzes')}>
                  <Text style={styles.launchBtnText}>Launch</Text>
                </TouchableOpacity>
              </View>
            )
          })}
        </View>

        {/* ── Quick links ── */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHead}>
            <View style={styles.sectionIconBox}>
              <Ionicons name="apps-outline" size={13} color={C.primary} />
            </View>
            <Text style={styles.sectionTitle}>Quick Access</Text>
          </View>
          <View style={styles.quickGrid}>
            <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('MyProgress')}>
              <View style={[styles.quickIcon, { backgroundColor: C.blueLt }]}>
                <Ionicons name="trending-up" size={18} color={C.primary} />
              </View>
              <Text style={styles.quickLbl}>My Progress</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('Attendance')}>
              <View style={[styles.quickIcon, { backgroundColor: C.greenLt }]}>
                <Ionicons name="calendar" size={18} color={C.green} />
              </View>
              <Text style={styles.quickLbl}>Attendance</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('Participation')}>
              <View style={[styles.quickIcon, { backgroundColor: C.purpleLt }]}>
                <Ionicons name="stats-chart" size={18} color={C.purple} />
              </View>
              <Text style={styles.quickLbl}>Participation</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.quickBtn} onPress={() => navigation.navigate('Interact')}>
              <View style={[styles.quickIcon, { backgroundColor: C.redLt }]}>
                <Ionicons name="pulse" size={18} color={C.red} />
              </View>
              <Text style={styles.quickLbl}>Interact</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },

  /* top app bar */
  topBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingBottom: 12, backgroundColor: C.card,
    borderBottomWidth: 1, borderBottomColor: C.border,
  },
  brandWrap: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logoBox: {
    width: 32, height: 32, borderRadius: 8, backgroundColor: C.blueLt,
    alignItems: 'center', justifyContent: 'center',
  },
  brandName: { fontSize: 15, fontWeight: '800', color: C.primary },
  brandSub: { fontSize: 9, fontWeight: '600', color: C.textHint, letterSpacing: 0.4 },
  topRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  syncPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: C.greenLt, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 20,
  },
  syncDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: C.green },
  syncText: { fontSize: 10, fontWeight: '700', color: C.greenDk },
  bellBtn: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: C.bg,
    borderWidth: 1, borderColor: C.border, alignItems: 'center', justifyContent: 'center',
  },
  bellBadge: {
    position: 'absolute', top: -2, right: -2, minWidth: 16, height: 16, borderRadius: 8,
    backgroundColor: C.red, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4,
  },
  bellBadgeText: { fontSize: 9, fontWeight: '800', color: '#fff' },
  avatar: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { fontSize: 12, fontWeight: '800', color: '#fff' },

  /* live session strip */
  liveStrip: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: C.primary, marginHorizontal: 16, marginTop: 12,
    borderRadius: 12, paddingVertical: 11, paddingHorizontal: 14,
  },
  liveLeft: { flex: 1, marginRight: 8 },
  liveDotWrap: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 },
  liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#fff' },
  liveTag: { fontSize: 9, fontWeight: '900', color: '#fff', letterSpacing: 1 },
  liveCourse: { fontSize: 12, fontWeight: '600', color: '#DBEAFE' },
  liveJoin: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: 'rgba(255,255,255,0.2)', paddingHorizontal: 12,
    paddingVertical: 8, borderRadius: 9,
  },
  liveJoinText: { fontSize: 12, fontWeight: '800', color: '#fff' },

  /* section cards */
  sectionCard: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 14,
    borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  sectionIconBox: {
    width: 26, height: 26, borderRadius: 7, backgroundColor: C.blueLt,
    alignItems: 'center', justifyContent: 'center',
  },
  sectionTitle: { flex: 1, fontSize: 14, fontWeight: '800', color: C.text },
  seeAll: { fontSize: 11, fontWeight: '700', color: C.primary },

  /* stat grid (attendance) */
  statGrid: { flexDirection: 'row', gap: 8 },
  statBox: {
    flex: 1, backgroundColor: C.gray50, borderRadius: 10,
    borderWidth: 1, borderColor: C.border, padding: 10,
  },
  statLabel: { fontSize: 8, fontWeight: '800', color: C.textHint, letterSpacing: 0.5 },
  statValueRow: { marginTop: 4 },
  statBig: { fontSize: 22, fontWeight: '900' },
  statSub: { fontSize: 9, color: C.textSub, marginTop: 2 },
  thresholdRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 14,
  },
  thresholdLbl: { fontSize: 11, fontWeight: '600', color: C.text },
  thresholdSafe: { fontSize: 10, fontWeight: '700', color: C.greenDk },
  thresholdTrack: {
    height: 10, borderRadius: 5, backgroundColor: C.gray100,
    overflow: 'hidden', marginTop: 6, position: 'relative',
  },
  thresholdFill: { height: 10, borderRadius: 5 },
  thresholdMarker: {
    position: 'absolute', top: -2, bottom: -2, width: 2,
    backgroundColor: C.text, borderRadius: 1,
  },
  sectionFootLink: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end',
    gap: 2, marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: C.border,
  },
  footLinkText: { fontSize: 11, fontWeight: '700', color: C.primary },
  sectionFootCenter: {
    alignItems: 'center', marginTop: 12, paddingVertical: 10,
    borderTopWidth: 1, borderTopColor: C.border,
    backgroundColor: C.gray50, borderRadius: 9,
  },
  footLinkCenter: { fontSize: 12, fontWeight: '700', color: C.text },

  /* announcement feed rows */
  feedRow: { flexDirection: 'row', gap: 10, paddingVertical: 10 },
  feedRowBorder: { borderTopWidth: 1, borderTopColor: C.border },
  feedDot: { width: 8, height: 8, borderRadius: 4, marginTop: 5 },
  feedBody: { flex: 1 },
  feedTopRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  feedPriority: { fontSize: 9, fontWeight: '900', letterSpacing: 0.6 },
  feedTime: { fontSize: 10, color: C.textHint },
  feedTitle: { fontSize: 13, fontWeight: '700', color: C.text, marginTop: 2 },
  feedText: { fontSize: 11, color: C.textSub, lineHeight: 16, marginTop: 2 },
  ackBtn: { alignSelf: 'flex-end', marginTop: 6, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 7, backgroundColor: C.blueLt },
  ackText: { fontSize: 10, fontWeight: '800', color: C.primary },
  newChip: { backgroundColor: C.blueLt, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  newChipText: { fontSize: 9, fontWeight: '800', color: C.primary },

  /* deadlines */
  deadlineRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 },
  deadlineIconBox: {
    width: 38, height: 38, borderRadius: 10, backgroundColor: C.blueLt,
    alignItems: 'center', justifyContent: 'center',
  },
  deadlineBody: { flex: 1 },
  deadlineTags: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 },
  courseTag: { backgroundColor: C.blueLt, paddingHorizontal: 6, paddingVertical: 1, borderRadius: 5 },
  courseTagText: { fontSize: 9, fontWeight: '800', color: C.primary },
  deadlineDue: { fontSize: 10, fontWeight: '800' },
  deadlineTitle: { fontSize: 13, fontWeight: '700', color: C.text },
  deadlineMeta: { fontSize: 11, color: C.textSub, marginTop: 2 },
  launchBtn: {
    backgroundColor: C.primary, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8,
  },
  launchBtnText: { fontSize: 11, fontWeight: '800', color: '#fff' },

  /* quick access */
  quickGrid: { flexDirection: 'row', gap: 8 },
  quickBtn: {
    flex: 1, alignItems: 'center', gap: 6, paddingVertical: 12,
    borderRadius: 10, borderWidth: 1, borderColor: C.border, backgroundColor: C.gray50,
  },
  quickIcon: {
    width: 34, height: 34, borderRadius: 9, alignItems: 'center', justifyContent: 'center',
  },
  quickLbl: { fontSize: 9, fontWeight: '700', color: C.textSub, textAlign: 'center' },
})
