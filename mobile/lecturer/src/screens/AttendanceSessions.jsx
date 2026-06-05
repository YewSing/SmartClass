import { useEffect } from 'react'
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

export default function AttendanceSessions({ navigation }) {
  const { state, loadSessions, selectSession } = useLecturer()
  const { sessions } = state

  useEffect(() => { loadSessions() }, [])

  const handleSessionClick = (session) => {
    selectSession(session)
    navigation.navigate('AttendanceDetail')
  }

  const renderItem = ({ item: s }) => (
    <TouchableOpacity style={styles.sessionItem} onPress={() => handleSessionClick(s)}>
      <View style={[styles.dateBlock, { backgroundColor: s.open ? C.greenLt : C.gray100 }]}>
        <Text style={[styles.dateDay, { color: s.open ? C.green : C.gray600 }]}>{s.day}</Text>
        <Text style={[styles.dateMonth, { color: s.open ? C.greenDk : C.gray500 }]}>{s.month}</Text>
      </View>
      <View style={styles.sessionInfo}>
        <Text style={styles.sessionTitle}>{s.class_code} — {s.class_name}</Text>
        {s.open ? (
          <View style={styles.rowGap}>
            <Text style={styles.sessionSub}>{s.time}</Text>
            <Badge variant="green" dot style={{ paddingVertical: 2, paddingHorizontal: 6 }}>Open now</Badge>
          </View>
        ) : (
          <Text style={styles.sessionSub}>
            {s.time}{s.duration ? ` · (${s.duration})` : ''}
          </Text>
        )}
        <View style={styles.chipsRow}>
          <View style={[styles.chip, { backgroundColor: C.greenLt }]}>
            <Text style={[styles.chipText, { color: C.greenDk }]}>{s.present} Present</Text>
          </View>
          <View style={[styles.chip, { backgroundColor: C.redLt }]}>
            <Text style={[styles.chipText, { color: C.redDk }]}>{s.absent} Absent</Text>
          </View>
          {s.unid > 0 && (
            <View style={[styles.chip, { backgroundColor: C.orangeLt }]}>
              <Text style={[styles.chipText, { color: C.orangeDk }]}>{s.unid} Unidentified</Text>
            </View>
          )}
        </View>
      </View>
      <Ionicons name="chevron-forward" size={14} color={C.gray300} />
    </TouchableOpacity>
  )

  return (
    <View style={styles.flex}>
      <Topbar title="Attendance" sub="All sessions" />
      {sessions.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>No sessions yet. Open a session from the dashboard.</Text>
        </View>
      ) : (
        <FlatList
          data={sessions}
          keyExtractor={s => String(s.id)}
          renderItem={renderItem}
          ListHeaderComponent={
            <Text style={styles.countLabel}>{sessions.length} session{sessions.length !== 1 ? 's' : ''}</Text>
          }
          ListFooterComponent={<View style={{ height: 20 }} />}
          style={styles.list}
        />
      )}
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
    gap: 12,
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
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sessionInfo: {
    flex: 1,
    gap: 4,
  },
  sessionTitle: {
    fontSize: 14,
    fontWeight: '700',
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
    fontWeight: '700',
  },
})
