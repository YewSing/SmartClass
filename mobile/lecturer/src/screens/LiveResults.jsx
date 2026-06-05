import { useState, useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { QUIZZES } from '../data/mockData'
import { C } from '../theme'

const BARS = [
  { opt: 'A', pct: 20, count: 1, correct: false },
  { opt: 'B', pct: 60, count: 3, correct: true  },
  { opt: 'C', pct: 20, count: 1, correct: false },
  { opt: 'D', pct: 0,  count: 0, correct: false },
]

const MAX_BAR_H = 90

export default function LiveResults({ navigation }) {
  const quiz = QUIZZES[0]
  const [secs, setSecs] = useState(14)

  useEffect(() => {
    const t = setInterval(() => setSecs(s => s > 0 ? s - 1 : 30), 1000)
    return () => clearInterval(t)
  }, [])

  const mm = String(Math.floor(secs / 60)).padStart(2, '0')
  const ss = String(secs % 60).padStart(2, '0')

  return (
    <View style={styles.flex}>
      <Topbar
        title="Live Results"
        onBack={() => navigation.goBack()}
        right={<Badge variant="blue" dot>Active</Badge>}
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Question card */}
        <View style={styles.card}>
          <Text style={styles.quizQuestion}>{quiz.question}</Text>
        </View>

        {/* Timer */}
        <View style={styles.timerBlock}>
          <Text style={styles.timerNum}>{mm}:{ss}</Text>
          <Text style={styles.timerLabel}>Time remaining</Text>
        </View>

        {/* Response summary */}
        <View style={styles.respSummary}>
          {[
            { n: '4/5', l: 'Answered', color: C.text },
            { n: '3', l: 'Correct', color: C.green },
            { n: '1', l: 'Incorrect', color: C.red },
            { n: '1', l: 'Unanswered', color: C.gray400 },
          ].map(r => (
            <View key={r.l} style={styles.respStat}>
              <Text style={[styles.respN, { color: r.color }]}>{r.n}</Text>
              <Text style={styles.respL}>{r.l}</Text>
            </View>
          ))}
        </View>

        {/* Bar chart */}
        <View style={styles.chartCard}>
          <Text style={styles.chartLabel}>Answer Distribution</Text>
          <View style={styles.barsContainer}>
            {BARS.map(b => (
              <View key={b.opt} style={styles.barCol}>
                <View style={styles.barWrapper}>
                  <View
                    style={[
                      styles.barFill,
                      { height: Math.round((b.pct / 100) * MAX_BAR_H) || 4 },
                      { backgroundColor: b.correct ? C.green : C.gray300 },
                    ]}
                  />
                </View>
                <Text style={[styles.barPct, { color: b.correct ? C.green : C.textSub }]}>
                  {b.pct > 0 ? `${b.pct}%` : '0%'}
                </Text>
                <View style={[styles.barOptLabel, { backgroundColor: b.correct ? C.greenLt : C.gray100 }]}>
                  <Text style={[styles.barOptText, { color: b.correct ? C.greenDk : C.gray600 }]}>{b.opt}</Text>
                </View>
                <Text style={styles.barCount}>{b.count}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Close early */}
        <View style={styles.actionRow}>
          <TouchableOpacity style={styles.dangerBtn} onPress={() => navigation.goBack()}>
            <Ionicons name="stop-outline" size={16} color="#fff" />
            <Text style={styles.dangerBtnText}>Close Early</Text>
          </TouchableOpacity>
        </View>
        <View style={{ height: 20 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  card: {
    margin: 16,
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  quizQuestion: {
    fontSize: 15,
    fontWeight: '700',
    color: C.text,
    lineHeight: 22,
  },
  timerBlock: {
    alignItems: 'center',
    paddingVertical: 20,
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
  },
  timerNum: {
    fontSize: 42,
    fontWeight: '800',
    color: C.primary,
    letterSpacing: 2,
  },
  timerLabel: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 4,
  },
  respSummary: {
    flexDirection: 'row',
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
    justifyContent: 'space-around',
  },
  respStat: {
    alignItems: 'center',
  },
  respN: {
    fontSize: 20,
    fontWeight: '800',
  },
  respL: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 2,
  },
  chartCard: {
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  chartLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
    marginBottom: 14,
  },
  barsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'flex-end',
    height: 130,
  },
  barCol: {
    alignItems: 'center',
    gap: 4,
    flex: 1,
  },
  barWrapper: {
    height: MAX_BAR_H,
    justifyContent: 'flex-end',
    width: 36,
  },
  barFill: {
    width: 36,
    borderRadius: 4,
    minHeight: 4,
  },
  barPct: {
    fontSize: 11,
    fontWeight: '700',
  },
  barOptLabel: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  barOptText: {
    fontSize: 13,
    fontWeight: '700',
  },
  barCount: {
    fontSize: 12,
    color: C.textSub,
  },
  actionRow: {
    paddingHorizontal: 16,
  },
  dangerBtn: {
    backgroundColor: C.red,
    borderRadius: 10,
    paddingVertical: 13,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  dangerBtnText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },
})
