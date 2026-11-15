import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, FlatList,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { getQuizAttempts } from '../services/api'
import { C } from '../theme'

/** Section card in the interaction style: colored title chip + right node (S29 pattern). */
function Section({ tint = 'blue', badge, right, children, style }) {
  const bg = { blue: C.blueLt, green: C.greenLt, red: C.redLt, orange: C.orangeLt, gray: C.gray100, purple: C.purpleLt, yellow: C.yellowLt }[tint]
  const fg = { blue: C.blueDk, green: C.greenDk, red: C.redDk, orange: C.orangeDk, gray: C.textSub, purple: C.purple, yellow: C.yellowDk }[tint]
  return (
    <View style={[styles.section, style]}>
      {badge != null && (
        <View style={styles.sectionHead}>
          <View style={[styles.sectionBadge, { backgroundColor: bg }]}>
            <Text style={[styles.sectionBadgeText, { color: fg }]}>{badge}</Text>
          </View>
          <View style={{ flex: 1 }} />
          {right}
        </View>
      )}
      {children}
    </View>
  )
}

export default function Breakdown({ navigation, route }) {
  const { showToast } = useLecturer()
  const { quizId } = (route?.params ?? {})

  const [attempts, setAttempts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadAttempts = useCallback(async () => {
    if (!quizId) return
    try {
      const list = await getQuizAttempts(quizId)
      setAttempts(list)
      setError(null)
    } catch (e) { setError(e.message || 'Could not load breakdown') }
    finally { setLoading(false) }
  }, [quizId])

  useEffect(() => { loadAttempts() }, [loadAttempts])

  const submitted = attempts.filter(a => a.status === 'submitted' || a.auto_submitted)
  const scored = submitted.filter(a => a.score != null)
  const avg = scored.length ? (scored.reduce((s, a) => s + a.score, 0) / scored.length).toFixed(0) : '--'
  const correctCount = scored.reduce((s, a) => s + (a.score >= 50 ? 1 : 0), 0)

  const renderItem = ({ item: a }) => (
    <TouchableOpacity
      style={styles.row}
      onPress={() => navigation.navigate('ResultsClosed', { attemptId: a.attempt_id, quizId })}
    >
      <View style={styles.rowBody}>
        <Text style={styles.rowStudent}>Student #{String(a.student_id).slice(-4)}</Text>
        <Text style={styles.rowMeta}>{a.started_at ? new Date(a.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</Text>
      </View>
      <View style={styles.rowRight}>
        <Badge variant={a.status === 'submitted' || a.auto_submitted ? 'green' : 'blue'} dot>
          {a.status === 'started' ? 'In progress' : a.status === 'submitted' ? 'Submitted' : 'Auto-submitted'}
        </Badge>
        <Text style={styles.rowScore}>{a.score != null ? `${a.score}%` : '--'}</Text>
      </View>
    </TouchableOpacity>
  )

  return (
    <View style={styles.flex}>
      <Topbar
        title="Response Breakdown"
        sub="Per-student attempts · tap a row to review answers"
        onBack={() => navigation.goBack()}
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {/* Summary */}
        <Section tint="purple" badge="Breakdown" right={
          <Badge variant="green" dot>{submitted.length} finished</Badge>
        }>
          <View style={styles.summaryRow}>
            <View style={styles.summaryCell}>
              <Text style={styles.summaryNum}>{attempts.length}</Text>
              <Text style={styles.summaryLbl}>Attempts</Text>
            </View>
            <View style={styles.summaryCell}>
              <Text style={[styles.summaryNum, { color: C.textSub }]}>{avg}</Text>
              <Text style={styles.summaryLbl}>Avg score</Text>
            </View>
            <View style={styles.summaryCell}>
              <Text style={[styles.summaryNum, { color: C.greenDk }]}>{correctCount}</Text>
              <Text style={styles.summaryLbl}>Passing (≥50%)</Text>
            </View>
          </View>
        </Section>

        {loading && <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>}

        {!loading && error && (
          <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>
        )}

        {!loading && !error && attempts.length === 0 && (
          <View style={styles.empty}>
            <Ionicons name="people-outline" size={32} color={C.textHint} />
            <Text style={styles.emptyText}>No attempts yet</Text>
          </View>
        )}

        {!loading && !error && attempts.length > 0 && (
          <>
            <Text style={styles.listTitle}>Students <Text style={styles.listSub}>tap to view answers & score short responses</Text></Text>
            <FlatList
              data={attempts}
              keyExtractor={(_, i) => String(i)}
              renderItem={renderItem}
              ItemSeparatorComponent={() => <View style={styles.separator} />}
              contentContainerStyle={{ paddingBottom: 90 }}
              style={styles.flex}
            />
          </>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  section: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  summaryCard: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  summaryRow: { flexDirection: 'row', gap: 10 },
  summaryCell: { flex: 1, alignItems: 'center' },
  summaryNum: { fontSize: 22, fontWeight: '800', color: C.text },
  summaryLbl: { fontSize: 11, color: C.textSub, marginTop: 2 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 40 },
  err: { padding: 16 },
  errText: { fontSize: 13, color: C.red },
  empty: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyText: { fontSize: 15, fontWeight: '700', color: C.text },
  listTitle: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 10, marginBottom: 4 },
  listSub: { fontSize: 12, color: C.textSub, marginBottom: 8 },
  separator: { height: 1, backgroundColor: C.border, marginHorizontal: 16 },
  row: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: C.card,
    borderBottomWidth: 1, borderBottomColor: C.border,
  },
  rowBody: { flex: 1, marginRight: 10 },
  rowStudent: { fontSize: 14, fontWeight: '700', color: C.text },
  rowMeta: { fontSize: 11, color: C.textHint, marginTop: 2 },
  rowRight: { alignItems: 'flex-end', minWidth: 120 },
  rowScore: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 2 },
})
