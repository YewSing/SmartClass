// The student's own questions from every class, newest first, with answered status (FR-520;
// plan-shino.md S38). Anonymous ones are listed too: they are the student's own.
import { useCallback, useEffect, useState } from 'react'
import { View, Text, FlatList, StyleSheet, RefreshControl, ActivityIndicator } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { LoadError } from '../components/InteractionParts'
import * as api from '../services/api'
import { myQuestionMeta, myQuestionBadge, mergeQuestionPages } from '../services/interaction'
import { C } from '../theme'

export default function MyQuestions({ navigation }) {
  const [items, setItems] = useState([])
  const [next, setNext] = useState(null)
  const [status, setStatus] = useState('loading')     // loading | ready | error
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)

  const load = useCallback(async () => {
    try {
      const page = await api.getMyQuestions()
      setItems(page.questions)
      setNext(page.next_before)
      setStatus('ready')
      setError(null)
    } catch (e) {
      setError(e.message)
      setStatus(s => (s === 'ready' ? 'ready' : 'error'))
    }
  }, [])

  useEffect(() => { load() }, [load])

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false) }

  const onMore = async () => {
    if (loadingMore || next == null) return
    setLoadingMore(true)
    try {
      const page = await api.getMyQuestions(next)
      setItems(cur => mergeQuestionPages(cur, page.questions))
      setNext(page.next_before)
    } catch (e) { setError(e.message) } finally { setLoadingMore(false) }
  }

  const renderItem = ({ item: q }) => {
    const b = myQuestionBadge(q)
    return (
      <View style={styles.item} testID="myq-item">
        <Text style={styles.text}>{q.text}</Text>
        <View style={styles.metaRow}>
          <Text style={styles.meta} numberOfLines={1}>{myQuestionMeta(q)}</Text>
          <View style={styles.flex1} />
          <View style={styles.upvotes}>
            <Ionicons name="arrow-up" size={12} color={C.textSub} />
            <Text style={styles.meta}>{q.upvotes}</Text>
          </View>
          <Badge variant={b.variant}>{b.label}</Badge>
        </View>
      </View>
    )
  }

  let empty = null
  if (status === 'loading') empty = <ActivityIndicator style={styles.spinner} color={C.primary} accessibilityLabel="Loading your questions" />
  else if (status === 'error') empty = <LoadError title="Couldn't load your questions" message={error} onRetry={load} testID="myq-error" />
  else {
    empty = (
      <View style={styles.empty} testID="myq-empty">
        <Ionicons name="chatbubbles-outline" size={36} color={C.gray400} />
        <Text style={styles.emptyTitle}>No questions yet</Text>
        <Text style={styles.emptyText}>Questions you ask in a live class show up here, with whether they were answered.</Text>
      </View>
    )
  }

  return (
    <View style={styles.flex}>
      <Topbar title="My questions" sub={status === 'ready' && items.length ? `${items.length}${next != null ? '+' : ''} asked` : ''}
        onBack={() => navigation.goBack()} />
      <FlatList
        data={items}
        keyExtractor={q => String(q.id)}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        ListEmptyComponent={empty}
        ListHeaderComponent={status === 'ready' && error && items.length
          ? <LoadError title="Couldn't refresh" message={error} onRetry={load} testID="myq-error" /> : null}
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
  flex1: { flex: 1 },
  list: { padding: 16, paddingBottom: 32, gap: 8, flexGrow: 1 },
  item: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 12, padding: 14 },
  text: { fontSize: 14, color: C.text, lineHeight: 20 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  meta: { fontSize: 12, color: C.textSub, flexShrink: 1 },
  upvotes: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  spinner: { marginTop: 48 },
  more: { marginVertical: 12 },
  empty: { alignItems: 'center', paddingTop: 64, paddingHorizontal: 32, gap: 8 },
  emptyTitle: { fontSize: 15, fontWeight: '600', color: C.text },
  emptyText: { fontSize: 13, color: C.textSub, textAlign: 'center', lineHeight: 19 },
})
