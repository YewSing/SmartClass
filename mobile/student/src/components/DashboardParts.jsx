// Pieces of the home dashboard (plan-shino.md S20; FR-201, FR-202, FR-208). The same file is in the
// lecturer app.
import { useCallback, useEffect, useReducer, useRef } from 'react'
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import Badge from './Badge'
import { dashboardReducer, initialDashboard } from '../services/dashboard'
import { priorityBadge, timeLabel } from '../services/notifications'
import { C } from '../theme'

// Loads the dashboard on every visit and whenever the unread count changes (a notification arrived
// live or was read elsewhere), so the priority list stays right without polling. Overlapping
// requests are folded into one more load after the current one.
export function useDashboard(load, unread) {
  const [state, dispatch] = useReducer(dashboardReducer, initialDashboard)
  const busy = useRef(false)
  const again = useRef(false)
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])

  const refresh = useCallback(async () => {
    if (busy.current) { again.current = true; return }
    busy.current = true
    dispatch({ type: 'loading' })
    try {
      const data = await load()
      if (alive.current) dispatch({ type: 'loaded', data })
    } catch (e) {
      if (alive.current) dispatch({ type: 'failed', error: e?.message || "Couldn't load the dashboard." })
    } finally {
      busy.current = false
      if (again.current && alive.current) { again.current = false; refresh() }
    }
  }, [load])

  useFocusEffect(useCallback(() => { refresh() }, [refresh]))
  const seen = useRef(unread)
  useEffect(() => {
    if (seen.current === unread) return
    seen.current = unread
    refresh()
  }, [unread, refresh])

  return { dash: state, dispatch, refresh }
}

export function SectionTitle({ children, right }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{children}</Text>
      {right ?? null}
    </View>
  )
}

export function LoadingCard() {
  return (
    <View style={[styles.card, styles.center]} testID="dash-loading">
      <ActivityIndicator color={C.primary} />
      <Text style={styles.muted}>Loading your dashboard…</Text>
    </View>
  )
}

// First load failed (nothing to show), or a re-load failed (`inline`: the old data stays below)
export function ErrorCard({ message, onRetry, inline = false }) {
  return (
    <View style={[styles.card, styles.errorCard, inline && styles.errorInline]} testID="dash-error">
      <Ionicons name="cloud-offline-outline" size={18} color={C.redDk} />
      <View style={styles.flex1}>
        <Text style={styles.errorTitle}>
          {inline ? "Couldn't refresh the dashboard" : "Couldn't load the dashboard"}
        </Text>
        {message ? <Text style={styles.errorText}>{message}</Text> : null}
      </View>
      <TouchableOpacity onPress={onRetry} style={styles.retry} testID="dash-retry" accessibilityRole="button">
        <Text style={styles.retryText}>Retry</Text>
      </TouchableOpacity>
    </View>
  )
}

export function EmptyRow({ text, testID }) {
  return <Text style={styles.empty} testID={testID}>{text}</Text>
}

// Unread urgent and important notifications, urgent first (FR-208). Opening one marks it read and
// follows its link; it leaves this list once the server has it as read.
export function PriorityNotifications({ items, onOpen }) {
  if (!items?.length) return null
  return (
    <View testID="dash-priority-list">
      <SectionTitle>Needs your attention</SectionTitle>
      {items.map(n => {
        const b = priorityBadge(n.priority)
        return (
          <TouchableOpacity
            key={n.id}
            style={[styles.card, styles.priority, n.priority === 'urgent' ? styles.urgent : styles.important]}
            onPress={() => onOpen(n)}
            testID="dash-priority"
            accessibilityRole="button"
          >
            <View style={styles.priorityTop}>
              <Badge variant={b.variant}>{b.label}</Badge>
              <Text style={styles.time}>{timeLabel(n.created_at)}</Text>
            </View>
            <Text style={styles.priorityTitle}>{n.title}</Text>
            {n.message ? <Text style={styles.priorityMsg} numberOfLines={2}>{n.message}</Text> : null}
          </TouchableOpacity>
        )
      })}
    </View>
  )
}

export const dashStyles = StyleSheet.create({
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 14,
    marginBottom: 10,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 10,
  },
  rowBorder: { borderTopWidth: 1, borderTopColor: C.border },
  rowMain: { flex: 1, gap: 2 },
  rowTitle: { fontSize: 14, fontWeight: '600', color: C.text },
  rowSub: { fontSize: 12, color: C.textSub },
  code: { fontSize: 12, fontWeight: '700', color: C.primary },
  note: { fontSize: 11, color: C.textHint, marginTop: 4 },
})

const styles = StyleSheet.create({
  ...dashStyles,
  flex1: { flex: 1 },
  center: { alignItems: 'center', gap: 8, paddingVertical: 22 },
  muted: { fontSize: 13, color: C.textSub },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 10,
    paddingBottom: 6,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  errorCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: C.redLt, borderColor: '#FECACA' },
  errorInline: { marginTop: 10 },
  errorTitle: { fontSize: 14, fontWeight: '600', color: C.redDk },
  errorText: { fontSize: 12, color: C.redDk, marginTop: 2 },
  retry: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, backgroundColor: C.card, borderWidth: 1, borderColor: '#FECACA' },
  retryText: { fontSize: 13, fontWeight: '600', color: C.redDk },
  empty: { fontSize: 13, color: C.textSub, paddingVertical: 6 },
  priority: { borderLeftWidth: 4, gap: 4 },
  urgent: { borderLeftColor: C.red },
  important: { borderLeftColor: C.orange },
  priorityTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  priorityTitle: { fontSize: 14, fontWeight: '600', color: C.text, marginTop: 2 },
  priorityMsg: { fontSize: 13, color: C.textSub, lineHeight: 18 },
  time: { fontSize: 11, color: C.textHint },
})
