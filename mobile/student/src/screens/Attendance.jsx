import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import Badge from '../components/Badge'
import { C } from '../theme'

const STATUS_BADGE = {
  present: { variant: 'green',  label: 'Present' },
  absent:  { variant: 'red',    label: 'Absent' },
  unid:    { variant: 'orange', label: 'Unidentified' },
  pending: { variant: 'blue',   label: 'In Progress', dot: true },
}

export default function Attendance({ navigation }) {
  const { state, loadAttendanceSummary, loadAttendanceGroups } = useStudent()
  const { attendanceSummary, attendanceGroups } = state
  const insets = useSafeAreaInsets()
  const [collapsed, setCollapsed] = useState({})
  const [activeFilter, setActiveFilter] = useState('All Classes')

  useEffect(() => {
    loadAttendanceSummary()
    loadAttendanceGroups()
  }, [loadAttendanceSummary, loadAttendanceGroups])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadAttendanceSummary(), loadAttendanceGroups()])
    setRefreshing(false)
  }, [loadAttendanceSummary, loadAttendanceGroups])

  const toggleGroup = (id) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))

  const summary = attendanceSummary ?? { present: 0, absent: 0, rate: '—' }
  const filters = ['All Classes', ...attendanceGroups.map(g => g.id.toUpperCase())]
  const visibleGroups = activeFilter === 'All Classes'
    ? attendanceGroups
    : attendanceGroups.filter(g => g.label.toUpperCase().includes(activeFilter))

  return (
    <View style={styles.flex}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <Text style={styles.headerTitle}>My Attendance</Text>
        <Text style={styles.headerSub}>All enrolled classes</Text>
      </View>

      {/* Summary stat row */}
      <View style={styles.summaryBar}>
        <View style={styles.statChip}>
          <Text style={[styles.statNum, { color: C.green }]}>{summary.present}</Text>
          <Text style={styles.statLbl}>Present</Text>
        </View>
        <View style={styles.statChip}>
          <Text style={[styles.statNum, { color: C.red }]}>{summary.absent}</Text>
          <Text style={styles.statLbl}>Absent</Text>
        </View>
        <View style={styles.statChip}>
          <Text style={[styles.statNum, { color: C.primary }]}>{summary.rate}</Text>
          <Text style={styles.statLbl}>Rate</Text>
        </View>
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
        {visibleGroups.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No attendance records yet.</Text>
          </View>
        ) : visibleGroups.map(group => (
          <View key={group.id}>
            <TouchableOpacity style={styles.groupHeader} onPress={() => toggleGroup(group.id)}>
              <Text style={styles.groupLabel}>{group.label}</Text>
              <Ionicons
                name={collapsed[group.id] ? 'chevron-forward' : 'chevron-down'}
                size={12}
                color={C.textSub}
              />
            </TouchableOpacity>

            {!collapsed[group.id] && group.sessions.length === 0 && (
              <Text style={styles.noRecordText}>No attendance records for this class yet.</Text>
            )}

            {!collapsed[group.id] && group.sessions.map(session => {
              const badge = STATUS_BADGE[session.variant] ?? STATUS_BADGE.absent
              return (
                <TouchableOpacity
                  key={session.id}
                  style={[styles.sessionRow, session.detail.isLive && styles.sessionRowLive]}
                  onPress={() => navigation.navigate('AttSessionDetail', {
                    sessionId: session.id,
                    session: session.detail,
                    variant: session.variant,
                  })}
                >
                  <View style={[styles.dateBlock, { backgroundColor: session.dateBg }]}>
                    <Text style={[styles.dateDay, { color: session.dateColor }]}>{session.day}</Text>
                    <Text style={[styles.dateMonth, { color: session.dateColor }]}>{session.month}</Text>
                  </View>
                  <View style={styles.sessionInfo}>
                    <Text style={styles.sessionTitle} numberOfLines={1}>{session.title}</Text>
                    <Text style={styles.sessionSub} numberOfLines={1}>{session.sub}</Text>
                  </View>
                  <Badge variant={badge.variant} dot={!!badge.dot}>{badge.label}</Badge>
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
  summaryBar: {
    flexDirection: 'row',
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  statChip: {
    flex: 1,
    alignItems: 'center',
  },
  statNum: {
    fontSize: 20,
    fontWeight: '800',
  },
  statLbl: {
    fontSize: 11,
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
  groupHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  groupLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
  },
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: C.border,
    gap: 14,
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
  },
  noRecordText: {
    fontSize: 13,
    color: C.textHint,
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
})
