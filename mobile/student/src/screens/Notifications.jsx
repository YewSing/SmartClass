// Notification centre (FR-208, FR-209, FR-213; plan-shino.md S19): newest first, pull to refresh,
// older pages on scroll, mark one (by opening it) or all read, tap opens the notification's
// screen. New notifications arrive live through the context's websocket.
import { useCallback, useEffect, useState } from 'react'
import { View, Text, FlatList, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useStudent as useApp } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { priorityBadge, timeLabel } from '../services/notifications'
import { C } from '../theme'

export default function Notifications({ navigation }) {
  const { feed, loadNotifications, markNotificationRead, markAllNotificationsRead, openNotificationLink } = useApp()
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    const ok = await loadNotifications()
    setFailed(!ok)
  }, [loadNotifications])

  useEffect(() => { load() }, [load])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }, [load])

  const onMore = useCallback(async () => {
    if (loadingMore || !feed.nextCursor) return
    setLoadingMore(true)
    await loadNotifications({ more: true })
    setLoadingMore(false)
  }, [loadingMore, feed.nextCursor, loadNotifications])

  const onOpen = useCallback(async (n) => {
    markNotificationRead(n)
    if (n.link) await openNotificationLink(n.link)
  }, [markNotificationRead, openNotificationLink])

  const now = new Date()

  const renderItem = ({ item: n }) => {
    const badge = priorityBadge(n.priority)
    return (
      <TouchableOpacity
        style={[styles.item, !n.read && styles.itemUnread]}
        onPress={() => onOpen(n)}
        testID="notif-item"
        accessibilityRole="button"
        accessibilityLabel={`${n.read ? '' : 'Unread. '}${n.title}`}
      >
        <View style={[styles.dot, n.read && styles.dotRead]} testID={n.read ? 'notif-read' : 'notif-unread'} />
        <View style={styles.itemBody}>
          <View style={styles.itemTop}>
            <Text style={[styles.title, !n.read && styles.titleUnread]} numberOfLines={2}>{n.title}</Text>
            <Text style={styles.time}>{timeLabel(n.created_at, now)}</Text>
          </View>
          <Text style={styles.message}>{n.message}</Text>
          {n.priority !== 'general' ? (
            <View style={styles.badgeRow}><Badge variant={badge.variant}>{badge.label}</Badge></View>
          ) : null}
        </View>
      </TouchableOpacity>
    )
  }

  let empty = null
  if (!feed.loaded && !failed) {
    empty = <ActivityIndicator style={styles.spinner} color={C.primary} accessibilityLabel="Loading notifications" />
  } else if (failed && !feed.items.length) {
    empty = (
      <View style={styles.empty}>
        <Ionicons name="cloud-offline-outline" size={36} color={C.gray400} />
        <Text style={styles.emptyTitle}>Couldn't load notifications</Text>
        <TouchableOpacity style={styles.retry} onPress={load} testID="notif-retry">
          <Text style={styles.retryText}>Try again</Text>
        </TouchableOpacity>
      </View>
    )
  } else {
    empty = (
      <View style={styles.empty} testID="notif-empty">
        <Ionicons name="notifications-off-outline" size={36} color={C.gray400} />
        <Text style={styles.emptyTitle}>No notifications yet</Text>
        <Text style={styles.emptyText}>Class updates, quizzes and announcements will show up here.</Text>
      </View>
    )
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Notifications"
        sub={feed.unread ? `${feed.unread} unread` : 'All caught up'}
        onBack={() => navigation.goBack()}
        right={
          <TouchableOpacity
            onPress={() => navigation.navigate('NotificationPrefs')}
            testID="notif-prefs"
            accessibilityLabel="Notification settings"
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Ionicons name="settings-outline" size={21} color={C.text} />
          </TouchableOpacity>
        }
      />
      {feed.unread > 0 ? (
        <View style={styles.actions}>
          <TouchableOpacity onPress={markAllNotificationsRead} testID="notif-mark-all" style={styles.markAll}>
            <Ionicons name="checkmark-done-outline" size={16} color={C.primary} />
            <Text style={styles.markAllText}>Mark all as read</Text>
          </TouchableOpacity>
        </View>
      ) : null}
      <FlatList
        data={feed.items}
        keyExtractor={n => String(n.id)}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        ListEmptyComponent={empty}
        onEndReached={onMore}
        onEndReachedThreshold={0.4}
        ListFooterComponent={loadingMore ? <ActivityIndicator style={styles.more} color={C.primary} /> : null}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  list: { padding: 16, paddingBottom: 32, gap: 8, flexGrow: 1 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', paddingHorizontal: 16, paddingTop: 12 },
  markAll: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 4 },
  markAllText: { fontSize: 13, fontWeight: '600', color: C.primary },
  item: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: C.card,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 12,
    padding: 14,
  },
  itemUnread: { borderColor: '#BFDBFE', backgroundColor: '#FBFDFF' },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.primary, marginTop: 6 },
  dotRead: { backgroundColor: 'transparent' },
  itemBody: { flex: 1, gap: 4 },
  itemTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  title: { flex: 1, fontSize: 14, fontWeight: '500', color: C.text },
  titleUnread: { fontWeight: '700' },
  time: { fontSize: 11, color: C.textHint, marginTop: 2 },
  message: { fontSize: 13, color: C.textSub, lineHeight: 19 },
  badgeRow: { flexDirection: 'row', marginTop: 4 },
  spinner: { marginTop: 48 },
  more: { marginVertical: 12 },
  empty: { alignItems: 'center', paddingTop: 64, paddingHorizontal: 32, gap: 8 },
  emptyTitle: { fontSize: 15, fontWeight: '600', color: C.text },
  emptyText: { fontSize: 13, color: C.textSub, textAlign: 'center', lineHeight: 19 },
  retry: { marginTop: 8, backgroundColor: C.primary, borderRadius: 10, paddingVertical: 10, paddingHorizontal: 20 },
  retryText: { fontSize: 14, fontWeight: '600', color: '#fff' },
})
