import {
  View, Text, FlatList, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { BREAKDOWN_ROWS } from '../data/mockData'
import { C } from '../theme'

export default function Breakdown({ navigation }) {
  const renderItem = ({ item: r }) => (
    <View style={styles.row}>
      <Text style={styles.rowName}>{r.name}</Text>
      <Text style={styles.rowAnswer}>{r.answer}</Text>
      <View style={styles.rowResult}>
        {r.correct === true  ? <Text style={styles.resultYes}>✅</Text>
         : r.correct === false ? <Text style={styles.resultNo}>❌</Text>
         : <Text style={styles.resultNA}>—</Text>}
      </View>
    </View>
  )

  return (
    <View style={styles.flex}>
      <Topbar title="Response Breakdown" onBack={() => navigation.goBack()} />

      {/* Question banner */}
      <View style={styles.questionBanner}>
        <Text style={styles.questionText}>
          What does SOLID stand for in object-oriented design principles?
        </Text>
        <View style={styles.correctRow}>
          <Ionicons name="checkmark-circle" size={14} color={C.green} style={{ marginTop: 1, flexShrink: 0 }} />
          <Text style={styles.correctText}>
            Correct: D — Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion
          </Text>
        </View>
      </View>

      {/* Summary stats */}
      <View style={styles.summaryRow}>
        <View style={[styles.bkdnStat, { backgroundColor: C.greenLt }]}>
          <Text style={[styles.bkdnNum, { color: C.green }]}>18</Text>
          <Text style={[styles.bkdnLbl, { color: C.greenDk }]}>Correct</Text>
        </View>
        <View style={[styles.bkdnStat, { backgroundColor: C.redLt }]}>
          <Text style={[styles.bkdnNum, { color: C.red }]}>4</Text>
          <Text style={[styles.bkdnLbl, { color: C.redDk }]}>Incorrect</Text>
        </View>
        <View style={[styles.bkdnStat, { backgroundColor: C.gray100 }]}>
          <Text style={[styles.bkdnNum, { color: C.gray500 }]}>3</Text>
          <Text style={[styles.bkdnLbl, { color: C.gray500 }]}>Unanswered</Text>
        </View>
      </View>

      {/* Table header */}
      <View style={styles.tableHeader}>
        <Text style={[styles.headerText, { flex: 1 }]}>Student</Text>
        <Text style={[styles.headerText, { width: 70, textAlign: 'center' }]}>Answer</Text>
        <Text style={[styles.headerText, { width: 50, textAlign: 'center' }]}>Result</Text>
      </View>

      <FlatList
        data={BREAKDOWN_ROWS}
        keyExtractor={(_, i) => String(i)}
        renderItem={renderItem}
        ListFooterComponent={<View style={{ height: 24 }} />}
        style={styles.flex}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  questionBanner: {
    backgroundColor: C.card,
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    gap: 8,
  },
  questionText: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
    lineHeight: 21,
  },
  correctRow: {
    flexDirection: 'row',
    gap: 6,
    alignItems: 'flex-start',
  },
  correctText: {
    fontSize: 12,
    color: C.textSub,
    flex: 1,
    lineHeight: 18,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 10,
    padding: 14,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  bkdnStat: {
    flex: 1,
    borderRadius: 10,
    padding: 10,
    alignItems: 'center',
  },
  bkdnNum: {
    fontSize: 22,
    fontWeight: '800',
  },
  bkdnLbl: {
    fontSize: 11,
    fontWeight: '700',
    marginTop: 2,
  },
  tableHeader: {
    flexDirection: 'row',
    padding: 10,
    paddingHorizontal: 14,
    backgroundColor: C.gray50,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  headerText: {
    fontSize: 11,
    fontWeight: '700',
    color: C.textSub,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    backgroundColor: C.card,
  },
  rowName: {
    flex: 1,
    fontSize: 13,
    color: C.text,
  },
  rowAnswer: {
    width: 70,
    textAlign: 'center',
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
  },
  rowResult: {
    width: 50,
    alignItems: 'center',
  },
  resultYes: { fontSize: 16 },
  resultNo:  { fontSize: 16 },
  resultNA:  { fontSize: 16, color: C.gray300 },
})
