// FR-205..FR-208 — in-app notification feed (student side).
// Ordered by priority (urgent → important → general), then by time received.
import { useState } from 'react'
import { View, Text, ScrollView, TouchableOpacity, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { NOTIFICATIONS, PRIORITIES } from '../data/module2'
import { C } from '../theme'

const PRIORITY_META = {
  urgent: { label: 'Urgent', variant: 'red', icon: 'notifications' },
  important: { label: 'Important', variant: 'orange', icon: 'alert-circle' },
  general: { label: 'General', variant: 'gray', icon: 'chatbubble-ellipses' },
}

export default function Notifications() {
  const [items, setItems] = useState(NOTIFICATIONS)
  const [filter, setFilter] = useState('all')

  const sorted = [...items].sort(
    (a, b) => PRIORITIES[a.priority] - PRIORITIES[b.priority]
  )
  const visible = filter === 'all' ? sorted : sorted.filter(n => n.priority === filter)
  const unread = items.filter(n => !n.read).length

  const markAllRead = () => setItems(prev => prev.map(n => ({ ...n, read: true })))
  const toggleRead = (id) =>
    setItems(prev => prev.map(n => n.id === id ? { ...n, read: !n.read } : n))

  return (
    <View style={styles.flex}>
      <Topbar
        title="Notifications"
        sub={`${unread} unread`}
        right={
          <TouchableOpacity onPress={markAllRead} style={styles.markBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Text style={styles.markText}>Mark all read</Text>
          </TouchableOpacity>
        }
      />

      {/* Filter pills */}
      <View style={styles.filterRow}>
        {['all', 'urgent', 'important', 'general'].map(f => (
          <TouchableOpacity
            key={f}
            style={[styles.pill, filter === f && styles.pillActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.pillText, filter === f && styles.pillTextActive]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {visible.map((n, idx) => {
          const meta = PRIORITY_META[n.priority]
          const showGroup = idx === 0 || visible[idx - 1].priority !== n.priority
          return (
            <View key={n.id}>
              {showGroup && (
                <View style={styles.groupHeader}>
                  <Ionicons name={meta.icon} size={12} color={C.textHint} />
                  <Text style={styles.groupLabel}>{meta.label}</Text>
                  <View style={styles.groupLine} />
                </View>
              )}
              <TouchableOpacity
                style={[styles.card, !n.read && styles.cardUnread]}
                activeOpacity={0.7}
                onPress={() => toggleRead(n.id)}
              >
                <View style={styles.cardTop}>
                  {!n.read && <View style={styles.unreadDot} />}
                  <Text style={styles.cardTitle} numberOfLines={1}>{n.title}</Text>
                  <Badge variant={meta.variant}>{meta.label}</Badge>
                </View>
                <Text style={styles.cardBody} numberOfLines={3}>{n.body}</Text>
                <View style={styles.cardMeta}>
                  {n.course && <Text style={styles.courseTag}>{n.course}</Text>}
                  <Ionicons name="time-outline" size={11} color={C.textHint} />
                  <Text style={styles.timeText}>{n.time}</Text>
                </View>
              </TouchableOpacity>
            </View>
          )
        })}
        {visible.length === 0 && (
          <View style={styles.empty}>
            <Ionicons name="notifications-off-outline" size={34} color={C.gray300} />
            <Text style={styles.emptyText}>No notifications here.</Text>
          </View>
        )}
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  markBtn: { paddingVertical: 4 },
  markText: { fontSize: 12, fontWeight: '700', color: C.primary },
  filterRow: {
    flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 10,
    gap: 8, backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  pill: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, backgroundColor: C.gray100 },
  pillActive: { backgroundColor: C.primary },
  pillText: { fontSize: 12, fontWeight: '600', color: C.textSub },
  pillTextActive: { color: '#fff' },
  groupHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 16, paddingTop: 14, paddingBottom: 6,
  },
  groupLabel: {
    fontSize: 11, fontWeight: '700', color: C.textHint,
    textTransform: 'uppercase', letterSpacing: 0.6,
  },
  groupLine: { flex: 1, height: 1, backgroundColor: C.border },
  card: {
    backgroundColor: C.card, marginHorizontal: 16, marginBottom: 8,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 12,
  },
  cardUnread: { borderColor: C.primary, backgroundColor: C.blueLt },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  unreadDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: C.primary },
  cardTitle: { flex: 1, fontSize: 13, fontWeight: '700', color: C.text },
  cardBody: { fontSize: 12, color: C.textSub, lineHeight: 18, marginBottom: 8 },
  cardMeta: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  courseTag: {
    fontSize: 10, fontWeight: '800', color: C.primary,
    backgroundColor: C.blueLt, paddingHorizontal: 6, paddingVertical: 1, borderRadius: 5,
  },
  timeText: { fontSize: 11, color: C.textHint },
  empty: { alignItems: 'center', padding: 40, gap: 8 },
  emptyText: { fontSize: 13, color: C.textHint },
})
