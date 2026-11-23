import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl, Linking,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { LinearGradient } from 'expo-linear-gradient'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import Badge from '../components/Badge'
import NotificationBell from '../components/NotificationBell'
import {
  useDashboard, SectionTitle, LoadingCard, ErrorCard, EmptyRow, PriorityNotifications, dashStyles,
} from '../components/DashboardParts'
import * as api from '../services/api'
import {
  attendanceBadge, classTypeLabel, classMeta, rateLabel, rateVariant, dueLabel, refreshedLabel, moodleLink,
} from '../services/dashboard'
import { timeLabel } from '../services/notifications'
import { liveClasses } from '../services/interaction'
import { C } from '../theme'

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning,'
  if (h < 17) return 'Good afternoon,'
  return 'Good evening,'
}

// A Moodle item (FR-203): tapping opens it in SPeCTRUM
function MoodleRow({ item, sub, first, testID }) {
  const link = moodleLink(item)
  return (
    <TouchableOpacity
      style={[dashStyles.row, !first && dashStyles.rowBorder]}
      disabled={!link}
      onPress={() => Linking.openURL(link).catch(() => {})}
      testID={testID}
      accessibilityRole="link"
    >
      <View style={dashStyles.rowMain}>
        <Text style={dashStyles.rowTitle} numberOfLines={2}>{item.title}</Text>
        <Text style={dashStyles.rowSub}>{[item.course_code, sub].filter(Boolean).join(' · ')}</Text>
      </View>
      {link ? <Ionicons name="open-outline" size={16} color={C.gray400} /> : null}
    </TouchableOpacity>
  )
}

const isLiveClass = (c) => liveClasses([c]).length === 1

function Dashboard({ data, navigation }) {
  const { today_classes: today, attendance_rates: rates, moodle } = data
  return (
    <>
      <SectionTitle right={(
        <TouchableOpacity onPress={() => navigation.navigate('MyQuestions')} testID="dash-my-questions"
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }} accessibilityRole="button">
          <Text style={styles.link}>My questions</Text>
        </TouchableOpacity>
      )}>Today</SectionTitle>
      <View style={dashStyles.card}>
        {today.length === 0 ? <EmptyRow text="No classes today." testID="dash-today-empty" /> : today.map((c, i) => {
          const b = attendanceBadge(c)
          const live = isLiveClass(c)
          return (
            <View key={`${c.occurrence_id}`} style={i > 0 && dashStyles.rowBorder}>
              <TouchableOpacity
                style={dashStyles.row}
                onPress={() => navigation.navigate('Attendance')}
                testID="dash-today-class"
              >
                <View style={dashStyles.rowMain}>
                  <Text style={dashStyles.code}>{c.course_code} · {classTypeLabel(c)}</Text>
                  <Text style={dashStyles.rowTitle}>{c.course_name}</Text>
                  {classMeta(c) ? <Text style={dashStyles.rowSub}>{classMeta(c)}</Text> : null}
                </View>
                <Badge variant={b.variant} dot>{b.label}</Badge>
              </TouchableOpacity>
              {live ? (
                // FR-501: the class interaction is open while the class session runs
                <TouchableOpacity
                  style={styles.join}
                  onPress={() => navigation.navigate('LiveClass', { sessionId: c.session_id })}
                  testID="dash-live-join"
                  accessibilityRole="button"
                  accessibilityLabel={`Join the live class, ${c.course_code}`}
                >
                  <View style={styles.liveDot} />
                  <Text style={styles.joinText}>Join live class</Text>
                  <Ionicons name="chevron-forward" size={16} color={C.primary} />
                </TouchableOpacity>
              ) : null}
            </View>
          )
        })}
      </View>

      <SectionTitle>Attendance rate</SectionTitle>
      <View style={dashStyles.card}>
        {rates.length === 0 ? <EmptyRow text="No attendance recorded yet." testID="dash-rates-empty" /> : rates.map((r, i) => (
          <TouchableOpacity
            key={r.course_id}
            style={[dashStyles.row, i > 0 && dashStyles.rowBorder]}
            onPress={() => navigation.navigate('Attendance')}
            testID="dash-rate"
          >
            <View style={dashStyles.rowMain}>
              <Text style={dashStyles.code}>{r.course_code}</Text>
              <Text style={dashStyles.rowSub}>
                {r.closed_sessions} class{r.closed_sessions === 1 ? '' : 'es'} · {r.present} present · {r.late} late · {r.absent} absent
              </Text>
            </View>
            <Badge variant={rateVariant(r.rate)}>{rateLabel(r.rate)}</Badge>
          </TouchableOpacity>
        ))}
      </View>

      <SectionTitle>From SPeCTRUM</SectionTitle>
      <View style={dashStyles.card} testID="dash-moodle">
        <Text style={styles.subHead}>Upcoming deadlines</Text>
        {moodle.deadlines.length === 0
          ? <EmptyRow text="No upcoming deadlines." testID="dash-deadlines-empty" />
          : moodle.deadlines.map((d, i) => (
            <MoodleRow key={`d${d.id}`} item={d} sub={dueLabel(d.date)} first={i === 0} testID="dash-deadline" />
          ))}
        <Text style={[styles.subHead, styles.subHeadGap]}>Announcements</Text>
        {moodle.announcements.length === 0
          ? <EmptyRow text="No announcements." testID="dash-announcements-empty" />
          : moodle.announcements.map((a, i) => (
            <MoodleRow key={`a${a.id}`} item={a} sub={timeLabel(a.date)} first={i === 0} testID="dash-announcement" />
          ))}
        <Text style={dashStyles.note} testID="dash-moodle-refreshed">{refreshedLabel(moodle.refreshed_at)}</Text>
      </View>
    </>
  )
}

export default function Home({ navigation }) {
  const { state, loadClasses, feed, markNotificationRead, openNotificationLink } = useStudent()
  const { classes, student } = state
  const insets = useSafeAreaInsets()
  const { dash, dispatch: dashDispatch, refresh } = useDashboard(api.getDashboard, feed.unread)

  useEffect(() => { loadClasses() }, [loadClasses])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadClasses(), refresh()])
    setRefreshing(false)
  }, [loadClasses, refresh])

  const openPriority = useCallback(async (n) => {
    if (!(await markNotificationRead(n))) return
    dashDispatch({ type: 'read', id: n.id })
    if (n.link) openNotificationLink(n.link)
  }, [markNotificationRead, openNotificationLink, dashDispatch])

  const todayCount = dash.data?.today_classes?.length

  return (
    <View style={styles.flex}>
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
          style={[styles.banner, { paddingTop: insets.top + 20 }]}
        >
          <View style={styles.bannerTop}>
            <Text style={styles.greetingText}>{greeting()}</Text>
            <NotificationBell light count={feed.unread} onPress={() => navigation.navigate('Notifications')} />
          </View>
          <Text style={styles.greetingName}>{student?.name ?? '—'}</Text>
          <Text style={styles.greetingSub}>
            {todayCount != null
              ? (todayCount ? `${todayCount} class${todayCount !== 1 ? 'es' : ''} today` : 'No classes today')
              : classes.length > 0
                ? `${classes.length} enrolled class${classes.length !== 1 ? 'es' : ''}`
                : 'Loading classes…'}
          </Text>
        </LinearGradient>

        <View style={styles.dash}>
          {dash.status === 'loading' && <LoadingCard />}
          {dash.status === 'error' && <ErrorCard message={dash.error} onRetry={refresh} />}
          {dash.status === 'ready' && dash.error ? <ErrorCard inline message={dash.error} onRetry={refresh} /> : null}
          {dash.data ? (
            <>
              <PriorityNotifications items={dash.data.priority_notifications} onOpen={openPriority} />
              <Dashboard data={dash.data} navigation={navigation} />
            </>
          ) : null}
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>My Classes</Text>
        </View>

        {classes.map(cls => (
          <TouchableOpacity
            key={cls.id}
            style={styles.classCard}
            activeOpacity={0.7}
            onPress={() => navigation.navigate('Attendance')}
          >
            <View style={[styles.accent, { backgroundColor: cls.accentColor }]} />
            <View style={styles.classBody}>
              <View style={styles.codeRow}>
                <Text style={styles.classCode}>{cls.code}</Text>
                <Badge variant={cls.type === 'LECTURE' ? 'blue' : 'green'}>
                  {cls.type === 'LECTURE' ? 'Lecture' : (cls.label ?? 'Tutorial')}
                </Badge>
              </View>
              <Text style={styles.classTitle}>{cls.name}</Text>
              {cls.venue ? (
                <View style={styles.metaRow}>
                  <Ionicons name="location-outline" size={12} color={C.textSub} />
                  <Text style={styles.metaText}>{cls.venue}</Text>
                </View>
              ) : null}
            </View>
            <View style={styles.cardArrow}>
              <Ionicons name="chevron-forward" size={20} color={C.gray400} />
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
  flex: { flex: 1, backgroundColor: C.bg },
  banner: {
    paddingHorizontal: 20,
    paddingBottom: 28,
  },
  bannerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  greetingText: {
    fontSize: 14,
    color: '#DBEAFE',
    fontWeight: '500',
  },
  greetingName: {
    fontSize: 24,
    fontWeight: '800',
    color: '#fff',
    marginTop: 4,
  },
  greetingSub: {
    fontSize: 13,
    color: '#BFDBFE',
    marginTop: 6,
  },
  dash: {
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  subHead: {
    fontSize: 12,
    fontWeight: '600',
    color: C.textSub,
    marginBottom: 2,
  },
  subHeadGap: {
    marginTop: 12,
  },
  link: {
    fontSize: 13,
    fontWeight: '500',
    color: C.primary,
  },
  join: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.blueLt,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    marginBottom: 10,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: C.green,
  },
  joinText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: C.primary,
  },
  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  sectionTitle: {
    fontSize: 13,
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
    paddingVertical: 14,
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
    fontSize: 15,
    fontWeight: '700',
    color: C.text,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 6,
  },
  metaText: {
    fontSize: 12,
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
