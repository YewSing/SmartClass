// The lecturer's Interaction tab (Module 5, plan-shino.md S38d): their past and current class
// sessions that have interaction data, newest first, like the Attendance tab. A live
// session opens its live screen (LiveInteraction), an ended one its summary (InteractionSummary). Data: GET /lecturer/interaction/sessions.
import { useCallback, useEffect, useRef, useState } from 'react'
import { View, Text, FlatList, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator } from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { LoadError, Loading } from '../components/InteractionParts'
import * as api from '../services/api'
import { historyRow, mergeHistory } from '../services/interaction'
import { C } from '../theme'

const PAGE = 20

export default function InteractionSessions({ navigation }) {
  const [items, setItems] = useState(null)        // null until the first page arrives
  const [total, setTotal] = useState(0)
  const [nextOffset, setNextOffset] = useState(null)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const seq = useRef(0)                            // a newer first-page load wins over an older one

  const loadFirst = useCallback(async () => {
    const mine = ++seq.current
    try {
      const page = await api.getInteractionSessions(0, PAGE)
      if (mine !== seq.current) return
      setItems(page.sessions)
      setTotal(page.total)
      setNextOffset(page.next_offset)
      setError(null)
    } catch (e) {
      if (mine === seq.current) setError(e.message ?? 'Could not load the sessions')
    }
  }, [])

  // Re-read whenever the tab comes back into view (a class may have run in between)
  useFocusEffect(useCallback(() => { loadFirst() }, [loadFirst]))
  useEffect(() => () => { seq.current += 1 }, [])

  const loadMore = async () => {
    if (nextOffset == null || loadingMore) return
    const mine = seq.current
    setLoadingMore(true)
    try {
      const page = await api.getInteractionSessions(nextOffset, PAGE)
      if (mine !== seq.current) return
      setItems(cur => mergeHistory(cur, page.sessions))
      setTotal(page.total)
      setNextOffset(page.next_offset)
    } catch (e) {
      if (mine === seq.current) setError(e.message ?? 'Could not load more sessions')
    } finally { setLoadingMore(false) }
  }

  const onRefresh = async () => {
    setRefreshing(true)
    await loadFirst()
    setRefreshing(false)
  }

  const renderItem = ({ item }) => {
    const r = historyRow(item)
    return (
      <TouchableOpacity style={styles.row} testID="ix-history-row"
        onPress={() => navigation.navigate(r.live ? 'LiveInteraction' : 'InteractionSummary', { sessionId: r.id })}>
        <View style={[styles.dateBlock, { backgroundColor: r.live ? C.greenLt : C.gray100 }]}>
          <Text style={[styles.dateDay, { color: r.live ? C.green : C.gray600 }]}>{r.day}</Text>
          <Text style={[styles.dateMonth, { color: r.live ? C.greenDk : C.gray500 }]}>{r.month}</Text>
        </View>
        <View style={styles.info}>
          <Text style={styles.title} numberOfLines={1}>{r.title}</Text>
          <View style={styles.rowGap}>
            {r.sub ? <Text style={styles.sub}>{r.sub}</Text> : null}
            {r.live ? <Badge variant="green" dot style={styles.badge}>Live</Badge> : null}
          </View>
          <View style={styles.chips}>
            {r.chips.map(c => (
              <View key={c.key} style={styles.chip} testID={`ix-history-chip-${c.key}`}>
                <Text style={styles.chipText}>{c.label}</Text>
              </View>
            ))}
          </View>
        </View>
        <Ionicons name="chevron-forward" size={14} color={C.gray300} />
      </TouchableOpacity>
    )
  }

  let body
  if (items == null) {
    body = (
      <View style={styles.pad}>
        {error ? <LoadError message={error} onRetry={loadFirst} testID="ix-history-error" /> : <Loading text="Loading sessions…" />}
      </View>
    )
  } else {
    body = (
      <FlatList
        data={items}
        keyExtractor={s => String(s.attendance_session_id)}
        renderItem={renderItem}
        style={styles.flex}
        ListHeaderComponent={
          <View>
            {error ? <View style={styles.padX}><LoadError message={error} onRetry={loadFirst} testID="ix-history-error" /></View> : null}
            {items.length ? (
              <Text style={styles.countLabel} testID="ix-history-count">
                {total} session{total !== 1 ? 's' : ''} with interaction
              </Text>
            ) : null}
          </View>
        }
        ListEmptyComponent={
          <View style={styles.empty} testID="ix-history-empty">
            <Text style={styles.emptyText}>
              No class interaction yet. Questions, polls, quick questions and reactions from your classes appear here.
            </Text>
          </View>
        }
        ListFooterComponent={
          nextOffset != null ? (
            <TouchableOpacity style={styles.more} onPress={loadMore} disabled={loadingMore} testID="ix-history-more">
              {loadingMore ? <ActivityIndicator size="small" color={C.primary} /> : <Text style={styles.moreText}>Load more</Text>}
            </TouchableOpacity>
          ) : <View style={{ height: 20 }} />
        }
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      />
    )
  }

  return (
    <View style={styles.flex}>
      <Topbar title="Interaction" sub="Questions, polls and reactions by class" />
      {body}
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  pad: { padding: 16 },
  padX: { paddingHorizontal: 16, paddingTop: 12 },
  empty: { alignItems: 'center', justifyContent: 'center', padding: 24 },
  emptyText: { fontSize: 14, color: C.textSub, textAlign: 'center' },
  countLabel: { padding: 12, paddingBottom: 4, fontSize: 12, color: C.textSub },
  row: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: C.card, marginHorizontal: 16, marginBottom: 8,
    borderRadius: 12, padding: 12, borderWidth: 1, borderColor: C.border, gap: 16,
  },
  dateBlock: { width: 44, height: 50, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  dateDay: { fontSize: 20, fontWeight: '800' },
  dateMonth: { fontSize: 10, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  info: { flex: 1, gap: 4 },
  title: { fontSize: 14, fontWeight: '600', color: C.text },
  sub: { fontSize: 12, color: C.textSub },
  rowGap: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  badge: { paddingVertical: 2, paddingHorizontal: 6 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
  chip: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10, backgroundColor: C.blueLt },
  chipText: { fontSize: 11, fontWeight: '500', color: C.blueDk },
  more: {
    marginHorizontal: 16, marginTop: 4, marginBottom: 20, paddingVertical: 10, borderRadius: 10,
    borderWidth: 1, borderColor: C.border, backgroundColor: C.card, alignItems: 'center',
  },
  moreText: { fontSize: 13, fontWeight: '600', color: C.primary },
})
