import { useState, useCallback } from 'react'
import {
  View, Text, ScrollView, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import { findSession } from '../services/attendance'
import { C } from '../theme'

const STATUS_CONFIG = {
  present: {
    rowBg: C.greenLt, rowBorder: '#9DE8C5', iconBg: C.green, icon: 'checkmark', labelColor: C.greenDk,
    info: null,
  },
  late: {
    rowBg: C.yellowLt, rowBorder: '#FDE68A', iconBg: C.yellow, icon: 'time-outline', labelColor: C.yellowDk,
    info: 'Late still counts as attended.',
  },
  excused: {
    rowBg: C.blueLt, rowBorder: '#93C5FD', iconBg: C.primary, icon: 'document-text-outline',
    labelColor: C.primary,
    info: "Excused classes don't count against your attendance rate.",
  },
  absent: {
    rowBg: C.redLt, rowBorder: '#f5c5c5', iconBg: C.red, icon: 'close', labelColor: C.redDk,
    info: 'You were not recorded in this class. If you were there, talk to your lecturer.',
  },
  not_recorded: {
    rowBg: C.gray100, rowBorder: C.border, iconBg: C.gray400, icon: 'radio-button-on',
    labelColor: C.gray600,
    info: 'This class is still running. Your status updates when the camera sees you or the lecturer marks you.',
  },
}

function InfoRow({ iconBg, icon, iconColor, label, value, valueBold, borderless }) {
  return (
    <View style={[styles.infoRow, borderless && { borderBottomWidth: 0 }]}>
      <View style={[styles.infoIcon, { backgroundColor: iconBg }]}>
        <Ionicons name={icon} size={16} color={iconColor} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.infoLbl}>{label}</Text>
        <Text style={[styles.infoVal, valueBold && { fontWeight: '700' }]}>{value}</Text>
      </View>
    </View>
  )
}

export default function AttSessionDetail({ route, navigation }) {
  const { state, loadAttendanceCourses } = useStudent()
  const { courseId, sessionId } = route.params ?? {}
  const [refreshing, setRefreshing] = useState(false)

  const found = findSession(state.attendanceCourses ?? [], courseId, sessionId)
  const session = found?.session

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadAttendanceCourses()
    setRefreshing(false)
  }, [loadAttendanceCourses])

  if (!session) {
    return (
      <View style={styles.flex}>
        <Topbar title="Session Detail" onBack={() => navigation.goBack()} />
        <View style={styles.notFound}>
          <Text style={styles.notFoundText}>This class is no longer in your attendance history.</Text>
        </View>
      </View>
    )
  }

  const cfg = STATUS_CONFIG[session.status] ?? STATUS_CONFIG.not_recorded
  const showCheckin = session.status === 'present' || session.status === 'late'

  return (
    <View style={styles.flex}>
      <Topbar title="Session Detail" onBack={() => navigation.goBack()} />
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* Hero */}
        <View style={styles.hero}>
          <Text style={styles.heroTitle}>{`${session.courseCode} — ${session.courseName}`}</Text>
          <Text style={styles.heroMeta}>{`${session.classLabel} · ${session.dateLong}`}</Text>

          <View style={[styles.statusRow, { backgroundColor: cfg.rowBg, borderColor: cfg.rowBorder }]}>
            <View style={[styles.statusIcon, { backgroundColor: cfg.iconBg }]}>
              <Ionicons name={cfg.icon} size={18} color="#fff" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.statusLabel, { color: cfg.labelColor }]}>Your Status</Text>
              <Text testID="att-detail-status" style={[styles.statusVal, { color: cfg.labelColor }]}>
                {session.label}
              </Text>
            </View>
            {session.isLive && (
              <View style={styles.liveChip}>
                <View style={styles.liveDot} />
                <Text style={styles.liveText}>Live Now</Text>
              </View>
            )}
          </View>
        </View>

        {/* Session info */}
        <Text style={styles.sectionTitle}>Session Info</Text>
        <View style={styles.card}>
          <InfoRow iconBg={C.blueLt} icon="time-outline" iconColor={C.primary}
            label="Class time" value={session.time ?? '—'} />

          {showCheckin && (
            <InfoRow iconBg={C.greenLt} icon="log-in-outline" iconColor={C.green}
              label="Check-in time" value={session.checkinTime ?? '—'} valueBold />
          )}

          <InfoRow iconBg={C.gray100} icon="location-outline" iconColor={C.gray500}
            label="Venue" value={session.venue} />

          <InfoRow iconBg={C.gray100} icon="person-outline" iconColor={C.gray500}
            label="Lecturer" value={session.lecturer} borderless={!session.overridden} />

          {session.overridden && (
            <InfoRow iconBg={C.orangeLt} icon="create-outline" iconColor={C.orange}
              label="Changed by your lecturer" value="Yes" borderless />
          )}
        </View>

        {cfg.info && (
          <View style={[styles.infoBanner, { backgroundColor: cfg.rowBg, borderColor: cfg.rowBorder }]}>
            <Ionicons name="information-circle-outline" size={15} color={cfg.labelColor} style={{ marginTop: 1 }} />
            <Text style={[styles.infoBannerText, { color: cfg.labelColor }]}>{cfg.info}</Text>
          </View>
        )}

        <View style={{ height: 28 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  notFound: {
    padding: 40,
    alignItems: 'center',
  },
  notFoundText: {
    fontSize: 14,
    color: C.textSub,
    textAlign: 'center',
  },
  hero: {
    backgroundColor: C.card,
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  heroTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: C.text,
  },
  heroMeta: {
    fontSize: 13,
    color: C.textSub,
    marginTop: 4,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 14,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  statusIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusLabel: {
    fontSize: 11,
    fontWeight: '600',
  },
  statusVal: {
    fontSize: 16,
    fontWeight: '700',
    marginTop: 1,
  },
  liveChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: C.redLt,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: C.red,
  },
  liveText: {
    fontSize: 11,
    fontWeight: '700',
    color: C.redDk,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  card: {
    backgroundColor: C.card,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: C.border,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  infoIcon: {
    width: 36,
    height: 36,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoLbl: {
    fontSize: 11,
    color: C.textSub,
    marginBottom: 1,
  },
  infoVal: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  infoBanner: {
    flexDirection: 'row',
    gap: 8,
    margin: 16,
    marginBottom: 0,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
  },
  infoBannerText: {
    flex: 1,
    fontSize: 12,
    lineHeight: 18,
  },
})
