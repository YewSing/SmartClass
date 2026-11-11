import { useCallback, useState } from 'react'
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl } from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import Topbar from '../components/Topbar'
import * as api from '../services/api'
import { auditAction, auditDetail } from '../services/adminHelpers'
import { C } from '../theme'

const PAGE = 50

const TONES = {
  good:    { bg: C.greenLt,  fg: C.greenDk },
  bad:     { bg: C.redLt,    fg: C.redDk },
  info:    { bg: C.blueLt,   fg: C.blueDk },
  warn:    { bg: C.orangeLt, fg: C.orangeDk },
  neutral: { bg: C.gray100,  fg: C.gray600 },
}

function when(iso) {
  return new Date(iso).toLocaleString('en-MY', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur',
  })
}

// Who changed what, newest first (FR-118, NFR-06)
export default function AdminAudit() {
  const [entries, setEntries] = useState(null)
  const [page, setPage] = useState(1)
  const [more, setMore] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      const list = await api.adminAuditLogs({ page: 1, limit: PAGE })
      setEntries(list)
      setPage(1)
      setMore(list.length === PAGE)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useFocusEffect(useCallback(() => { load() }, [load]))

  const loadMore = async () => {
    setBusy(true)
    try {
      const list = await api.adminAuditLogs({ page: page + 1, limit: PAGE })
      setEntries(e => [...e, ...list])
      setPage(p => p + 1)
      setMore(list.length === PAGE)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false) }

  return (
    <View style={styles.flex}>
      <Topbar title="Audit log" sub="Every change to accounts, face data and attendance" />
      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {error && (
          <TouchableOpacity style={styles.errorBox} onPress={load}>
            <Text style={styles.errText}>{error} · Tap to retry</Text>
          </TouchableOpacity>
        )}
        {entries === null && !error && <ActivityIndicator color={C.primary} style={{ marginTop: 24 }} />}
        {entries?.length === 0 && <Text style={styles.empty}>Nothing has been logged yet.</Text>}
        {entries?.map(e => {
          const a = auditAction(e.action)
          const tone = TONES[a.tone]
          const detail = auditDetail(e)
          return (
            <View key={e.id} style={styles.row} testID="audit-row">
              <View style={styles.rowHead}>
                <View style={[styles.chip, { backgroundColor: tone.bg }]}>
                  <Text style={[styles.chipText, { color: tone.fg }]}>{a.label}</Text>
                </View>
                <Text style={styles.meta}>{when(e.ts)}</Text>
              </View>
              <Text style={styles.actor}>
                {e.actor.name} <Text style={styles.meta}>({e.actor.role}) · {e.target_type} #{e.target_id}</Text>
              </Text>
              {detail ? <Text style={styles.detail} numberOfLines={3}>{detail}</Text> : null}
            </View>
          )
        })}
        {more && (
          <TouchableOpacity style={styles.moreBtn} onPress={loadMore} disabled={busy}>
            {busy ? <ActivityIndicator color={C.primary} size="small" /> : <Text style={styles.moreText}>Show older entries</Text>}
          </TouchableOpacity>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32, gap: 8 },
  row: { backgroundColor: C.card, borderRadius: 10, borderWidth: 1, borderColor: C.border, padding: 12, gap: 6 },
  rowHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' },
  chip: { borderRadius: 10, paddingVertical: 3, paddingHorizontal: 8 },
  chipText: { fontSize: 11, fontWeight: '700' },
  actor: { fontSize: 13, fontWeight: '600', color: C.text },
  meta: { fontSize: 12, fontWeight: '400', color: C.textSub },
  detail: { fontSize: 12, color: C.gray600, lineHeight: 17 },
  empty: { fontSize: 13, color: C.textSub, textAlign: 'center', marginTop: 24 },
  moreBtn: {
    alignItems: 'center', paddingVertical: 10, borderRadius: 10, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card,
  },
  moreText: { fontSize: 13, fontWeight: '600', color: C.text },
  errorBox: { backgroundColor: C.redLt, borderRadius: 8, padding: 10 },
  errText: { fontSize: 13, color: C.redDk },
})
