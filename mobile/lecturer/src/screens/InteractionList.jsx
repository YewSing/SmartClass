import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { apiCall } from '../services/client'
import { C } from '../theme'

export default function InteractionList({ navigation }) {
  const { showToast } = useLecturer()
  const [interactions, setInteractions] = useState([])
  const [refreshing, setRefreshing] = useState(false)

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const list = await apiCall('GET', '/lecturer/interactions')
      setInteractions(Array.isArray(list) ? list : [])
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setRefreshing(false)
    }
  }, [showToast])

  useEffect(() => {
    onRefresh()
  }, [onRefresh])

  // Sort: open sessions first, then by opened_at descending (latest first)
  const sorted = [...interactions].sort((a, b) => {
    if (a.status === b.status) {
      return new Date(b.opened_at) - new Date(a.opened_at)
    }
    return a.status === 'open' ? -1 : 1
  })

  const handleInteractionClick = (session) => {
    navigation.navigate('InteractionDetail', {
      interactionId: session.id,
      occurrence_id: session.occurrence_id,
    })
  }

  return (
    <View style={styles.flex}>
      <Topbar title="Interaction" sub="All sessions" />
      <FlatList
        data={sorted}
        keyExtractor={s => String(s.id)}
        renderItem={renderItem}
        ListHeaderComponent={
          sorted.length > 0
            ? <Text style={styles.countLabel}>{sorted.length} session{sorted.length !== 1 ? 's' : ''}</Text>
            : null
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="chatbubble-outline" size={48} color={C.textHint} />
            <Text style={styles.emptyText}>No interaction sessions yet.</Text>
            <Text style={styles.emptySub}>Start one from the Home screen.</Text>
          </View>
        }
        ListFooterComponent={<View style={{ height: 20 }} />}
        style={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      />
    </View>
  )

  function renderItem({ item: s }) {
    const open = s.status === 'open'
    return (
      <TouchableOpacity style={styles.sessionItem} testID="interaction-row" onPress={() => handleInteractionClick(s)}>
        <View style={[styles.dateBlock, { backgroundColor: open ? C.greenLt : C.gray100 }]}>
          <View style={styles.sessionDot} />
        </View>
        <View style={styles.sessionInfo}>
          <View style={styles.rowBetween}>
            <Text style={styles.sessionTitle}>{s.class_code} — {s.class_name}</Text>
            <Badge variant={open ? 'green' : 'gray'} dot>{open ? 'Open' : 'Closed'}</Badge>
          </View>
          <Text style={styles.sessionSub}>
            {s.class_code} &middot; {open ? 'Live session' : 'Ended'}
          </Text>
          {s.current_poll && (
            <View style={styles.chipsRow}>
              <View style={[styles.chip, { backgroundColor: C.blueLt }]}>
                <Text style={[styles.chipText, { color: C.blueDk }]}>{s.current_poll.question}</Text>
              </View>
            </View>
          )}
          <View style={styles.chipsRow}>
            <View style={[styles.chip, { backgroundColor: C.orangeLt }]}>
              <Text style={[styles.chipText, { color: C.orangeDk }]}>{s.idu_distinct_students ?? 0} IDU</Text>
            </View>
            <View style={[styles.chip, { backgroundColor: C.greenLt }]}>
              <Text style={[styles.chipText, { color: C.greenDk }]}>{s.reaction_counts?.understood ?? 0} Understood</Text>
            </View>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={14} color={C.gray300} />
      </TouchableOpacity>
    )
  }
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  list: { flex: 1 },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  emptyText: {
    fontSize: 14,
    color: C.textSub,
    textAlign: 'center',
  },
  emptySub: {
    fontSize: 12,
    color: C.textHint,
    textAlign: 'center',
    marginTop: 6,
  },
  countLabel: {
    padding: 12,
    paddingBottom: 4,
    fontSize: 12,
    color: C.textSub,
  },
  sessionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: C.border,
    gap: 12,
  },
  dateBlock: {
    width: 44,
    height: 50,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sessionDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.green },
  sessionInfo: { flex: 1, gap: 4 },
  rowBetween: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  sessionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  sessionSub: {
    fontSize: 12,
    color: C.textSub,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 2,
  },
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  chipText: {
    fontSize: 11,
    fontWeight: '500',
  },
})
