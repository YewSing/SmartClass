import { useCallback, useState } from 'react'
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import * as api from '../services/api'
import { syncRows } from '../services/adminHelpers'
import { C } from '../theme'

function when(iso) {
  return new Date(iso).toLocaleString('en-MY', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur',
  })
}

// Courses, enrolments and accounts come from SPeCTRUM (FR-104). The server syncs on a schedule;
// this shows the last result and lets an admin sync now.
export default function AdminMoodleSync() {
  const { showToast } = useLecturer()
  const [last, setLast] = useState(undefined)   // undefined while loading, null before the first sync
  const [error, setError] = useState(null)
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    try {
      setLast(await api.adminLastSync())
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useFocusEffect(useCallback(() => { load() }, [load]))

  const syncNow = async () => {
    setSyncing(true)
    try {
      await api.adminSyncNow()
      showToast('Sync finished', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setSyncing(false)
      load()   // the server records failures too
    }
  }

  const rows = syncRows(last)

  return (
    <View style={styles.flex}>
      <Topbar title="SPeCTRUM sync" sub="Courses, enrolments and accounts from SPeCTRUM" />
      <ScrollView style={styles.flex} contentContainerStyle={styles.content}>
        <View style={styles.card}>
          <View style={styles.head}>
            <View style={styles.flex0}>
              <Text style={styles.title}>Last sync</Text>
              {last === undefined && !error && <ActivityIndicator color={C.primary} style={{ alignSelf: 'flex-start' }} />}
              {last === null && <Text style={styles.meta} testID="sync-status">No sync since the server started</Text>}
              {last && (
                <View style={styles.statusRow}>
                  <Ionicons name={last.ok ? 'checkmark-circle' : 'alert-circle'} size={16} color={last.ok ? C.green : C.red} />
                  <Text style={styles.meta} testID="sync-status">
                    {last.ok ? 'Succeeded' : 'Failed'} · {when(last.finished_at)}
                  </Text>
                </View>
              )}
            </View>
            <TouchableOpacity style={[styles.btn, syncing && styles.busy]} onPress={syncNow} disabled={syncing} accessibilityRole="button">
              {syncing ? <ActivityIndicator color="#fff" size="small" /> : <Ionicons name="sync" size={16} color="#fff" />}
              <Text style={styles.btnText}>{syncing ? 'Syncing…' : 'Sync now'}</Text>
            </TouchableOpacity>
          </View>
          {error && <Text style={styles.errText}>{error}</Text>}
          {last && !last.ok && (
            <Text style={styles.errText}>SPeCTRUM couldn't be read, so nothing was changed ({last.error}).</Text>
          )}
          {rows.length > 0 && (
            <View style={styles.table}>
              {rows.map(r => (
                <View key={r.key} style={styles.tableRow}>
                  <Text style={styles.cell}>{r.label}</Text>
                  <Text style={styles.cellNum}>{r.value}</Text>
                </View>
              ))}
            </View>
          )}
          {last?.skipped?.length > 0 && (
            <View style={styles.skipped}>
              <Text style={styles.title}>Skipped</Text>
              {last.skipped.map((s, i) => <Text key={i} style={styles.meta}>• {s}</Text>)}
            </View>
          )}
        </View>
        <Text style={styles.hint}>
          SmartClass also syncs by itself on a schedule (every 15 minutes by default), and each person's own courses when they sign in.
          Timetables (days, times, rooms) are kept in SmartClass.
        </Text>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  flex0: { flex: 1, gap: 4 },
  content: { padding: 16, paddingBottom: 32, gap: 12 },
  card: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 16, gap: 12 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  title: { fontSize: 15, fontWeight: '700', color: C.text },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  meta: { fontSize: 13, color: C.textSub },
  btn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.primary,
    paddingVertical: 10, paddingHorizontal: 16, borderRadius: 10,
  },
  btnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  busy: { opacity: 0.7 },
  table: { borderTopWidth: 1, borderTopColor: C.border },
  tableRow: {
    flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  cell: { fontSize: 13, color: C.text },
  cellNum: { fontSize: 13, fontWeight: '700', color: C.text },
  skipped: { gap: 4 },
  hint: { fontSize: 12, color: C.textSub, lineHeight: 18 },
  errText: { fontSize: 13, color: C.redDk, backgroundColor: C.redLt, borderRadius: 8, padding: 8 },
})
