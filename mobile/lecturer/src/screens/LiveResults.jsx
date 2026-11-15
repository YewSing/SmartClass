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

const REFRESH_MS = 5000

export default function LiveResults({ navigation, route }) {
  const { showToast } = useLecturer()
  const { quizId, courseId, courseCode, courseName } = (route?.params ?? {})

  const [attempts, setAttempts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [intervalId, setIntervalId] = useState(null)

  const loadAttempts = useCallback(async () => {
    if (!quizId) return
    try {
      const list = await getQuizAttempts(quizId)
      setAttempts(list)
      setError(null)
    } catch (e) {
      setError(e.message || 'Could not load quiz attempts')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [quizId])

  useEffect(() => {
    loadAttempts()
    const id = setInterval(loadAttempts, REFRESH_MS)
    setIntervalId(id)
    return () => clearInterval(id)
  }, [loadAttempts])

  const started = attempts.filter(a => a.status === 'started').length
  const submitted = attempts.filter(a => a.status === 'submitted').length
  const autoSubmitted = attempts.filter(a => a.auto_submitted).length
  const scored = attempts.filter(a => a.score != null)
  const avg = scored.length ? (scored.reduce((s, a) => s + a.score, 0) / scored.length).toFixed(0) : '--'

  const statusLabel = (s) => {
    switch (s) {
      case 'started': return 'In progress'
      case 'submitted': return 'Submitted'
      case 'auto_submitted': return 'Auto-submitted'
      default: return s
    }
  }

  const renderItem = ({ item: a }) => (
    <TouchableOpacity
      style={styles.row}
      onPress={() => navigation.navigate('ResultsClosed', { attemptId: a.attempt_id })}
    >
      <View style={styles.rowBody}>
        <Text style={styles.rowStudent}>Student #{String(a.student_id).slice(-4)}</Text>
        <Text style={styles.rowMeta}>
          {statusLabel(a.status)}{a.submitted_at ? ` · submitted` : ''}
        </Text>
      </View>
      <View style={styles.rowRight}>
        <Badge variant={a.status === 'submitted' || a.auto_submitted ? 'green' : 'blue'} dot>
          {statusLabel(a.status)}
        </Badge>
        {a.score != null ? (
          <Text style={styles.rowScore}>{a.score}%</Text>
        ) : (
          <Text style={styles.rowScore}>--</Text>
        )}
      </View>
    </TouchableOpacity>
  )

  return (
    <View style={styles.flex}>
      <Topbar
        title="Live Results"
        sub={courseCode ? `${courseCode} · ${courseName}` : undefined}
        onBack={() => navigation.goBack()}
        right={
          <TouchableOpacity style={styles.refresh} onPress={() => { setRefreshing(true); loadAttempts() }}>
            <Ionicons name={refreshing ? 'loop-circle' : 'refresh-outline'} size={18} color={C.primary} />
          </TouchableOpacity>
        }
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {/* Summary */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryCell}>
              <Text style={styles.summaryNum}>{attempts.length}</Text>
              <Text style={styles.summaryLbl}>Attempts</Text>
            </View>
            <View style={styles.summaryCell}>
              <Text style={styles.summaryNum}>{started}</Text>
              <Text style={styles.summaryLbl}>In progress</Text>
            </View>
            <View style={styles.summaryCell}>
              <Text style={[styles.summaryNum, { color: C.green }]}>{submitted}</Text>
              <Text style={styles.summaryLbl}>Submitted</Text>
            </View>
            <View style={styles.summaryCell}>
              <Text style={[styles.summaryNum, { color: C.textSub }]}>{avg}</Text>
              <Text style={styles.summaryLbl}>Avg score</Text>
            </View>
          </View>
          {autoSubmitted > 0 && (
            <Text style={styles.hint}>{autoSubmitted} attempt{autoSubmitted !== 1 ? 's' : ''} auto-submitted after the deadline.</Text>
          )}
        </View>

        {loading && <View style={styles.loading}><ActivityIndicator size="large" color={C.primary} /></View>}

        {!loading && error && (
          <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>
        )}

        {!loading && !error && attempts.length === 0 && (
          <View style={styles.empty}>
            <Ionicons name="people-outline" size={32} color={C.textHint} />
            <Text style={styles.emptyText}>No attempts yet</Text>
            <Text style={styles.emptySub}>Students take the quiz from the student app.</Text>
          </View>
        )}

        {!loading && !error && attempts.length > 0 && (
          <>
            <Text style={styles.listTitle}>Attempts <Text style={styles.listSub}>tap a row to view / score answers</Text></Text>
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
  refresh: { padding: 8 },
  summaryCard: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 12,
    borderWidth: 1, borderColor: C.border,
  },
  summaryRow: { flexDirection: 'row', gap: 10 },
  summaryCell: { flex: 1, alignItems: 'center' },
  summaryNum: { fontSize: 22, fontWeight: '800', color: C.text },
  summaryLbl: { fontSize: 11, color: C.textSub, marginTop: 2 },
  hint: { fontSize: 12, color: C.textHint, marginTop: 8 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 40 },
  err: { padding: 16 },
  errText: { fontSize: 13, color: C.red },
  empty: { alignItems: 'center', paddingVertical: 40, gap: 8 },
  emptyText: { fontSize: 15, fontWeight: '700', color: C.text },
  emptySub: { fontSize: 13, color: C.textSub },
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
  rowRight: { alignItems: 'flex-end', minWidth: 110 },
  rowScore: { fontSize: 15, fontWeight: '800', color: C.text, marginTop: 2 },
})
