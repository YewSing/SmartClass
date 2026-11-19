import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import { getAllInteractionSessions } from '../services/api'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Every interaction session across the lecturer's classes, straight from the DB:
// open sessions first, then newest to oldest (UC-501). Tapping a session opens
// its control screen.
export default function InteractionSessions({ navigation }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setSessions(await getAllInteractionSessions())
    } catch {
      setSessions([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])
  useFocusEffect(useCallback(() => { load() }, [load]))

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }, [load])

  const renderItem = ({ item: i }) => {
    const d = i.opened_at ? new Date(i.opened_at) : null
    const day = d ? String(d.getDate()).padStart(2, '0') : '--'
    const month = d ? MONTHS[d.getMonth()] : ''
    return (
      <TouchableOpacity
        style={styles.sessionItem}
        testID="interaction-row"
        onPress={() => navigation.navigate('InteractionControl', { interaction_id: i.id })}
      >
        <View style={[styles.dateBlock, { backgroundColor: i.status === 'open' ? C.greenLt : C.gray100 }]}>
          <Text style={[styles.dateDay, { color: i.status === 'open' ? C.green : C.gray600 }]}>{day}</Text>
          <Text style={[styles.dateMonth, { color: i.status === 'open' ? C.greenDk : C.gray500 }]}>{month}</Text>
        </View>
        <View style={styles.sessionInfo}>
          <Text style={styles.sessionTitle}>{i.class_code} — {i.class_name}</Text>
          <View style={styles.rowGap}>
            <Text style={styles.sessionSub}>
              {d ? `${day}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}` : ''}
            </Text>
            {i.status === 'open' ? (
              <Badge variant="green" dot style={{ paddingVertical: 2, paddingHorizontal: 6 }}>Open</Badge>
            ) : (
              <Badge variant="gray" style={{ paddingVertical: 2, paddingHorizontal: 6 }}>Closed</Badge>
            )}
          </View>
          <View style={styles.chipsRow}>
            {i.live_question ? (
              <View style={[styles.chip, { backgroundColor: C.purpleLt }]}>
                <Text style={[styles.chipText, { color: C.purple }]}>Live question</Text>
              </View>
            ) : null}
            {i.current_poll ? (
              <View style={[styles.chip, { backgroundColor: C.blueLt }]}>
                <Text style={[styles.chipText, { color: C.blueDk }]}>Poll open</Text>
              </View>
            ) : null}
            {i.status !== 'open' && !i.live_question && !i.current_poll ? (
              <View style={[styles.chip, { backgroundColor: C.gray100 }]}>
                <Text style={[styles.chipText, { color: C.gray600 }]}>Closed session</Text>
              </View>
            ) : null}
          </View>
        </View>
        <Ionicons name="chevron-forward" size={14} color={C.gray300} />
      </TouchableOpacity>
    )
  }

  return (
    <View style={styles.flex}>
      <Topbar title="Interaction" sub="All sessions" />
      <FlatList
        data={sessions}
        keyExtractor={i => String(i.id)}
        renderItem={renderItem}
        ListHeaderComponent={
          sessions.length > 0
            ? <Text style={styles.countLabel}>{sessions.length} session{sessions.length !== 1 ? 's' : ''}</Text>
            : null
        }
        ListEmptyComponent={
          loading ? null : (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>
                No interaction sessions yet. Open one from Home with "Open Session".
              </Text>
            </View>
          )
        }
        ListFooterComponent={<View style={{ height: 20 }} />}
        style={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      />
    </View>
  )
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
    gap: 16,
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
    gap: 4,
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
  rowGap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
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
