import { View, Text, StyleSheet } from 'react-native'
import { C } from '../theme'

// One count row for a class session (T38b): the Home pane and the live session screen use this
// so both show the same five numbers. `counts` = { present, late, excused, absent, not_recorded };
// "Not yet" only while the class is open.
function Count({ n, label, color, testID }) {
  return (
    <View style={styles.count}>
      <Text style={[styles.countNum, { color }]} testID={testID}>{n}</Text>
      <Text style={styles.countLbl}>{label}</Text>
    </View>
  )
}

export default function AttendanceCounts({ counts, open, testIDPrefix = 'count' }) {
  const id = (name) => `${testIDPrefix}-${name}`
  return (
    <View style={styles.counts}>
      <Count n={counts.present} label="Present" color={C.green} testID={id('present')} />
      <Count n={counts.late} label="Late" color={C.orange} testID={id('late')} />
      <Count n={counts.excused} label="Excused" color={C.primary} testID={id('excused')} />
      <Count n={counts.absent} label="Absent" color={C.red} testID={id('absent')} />
      {open ? <Count n={counts.not_recorded} label="Not yet" color={C.gray500} testID={id('not-yet')} /> : null}
    </View>
  )
}

const styles = StyleSheet.create({
  counts: { flexDirection: 'row', justifyContent: 'space-around' },
  count: { alignItems: 'center', minWidth: 52 },
  countNum: { fontSize: 22, fontWeight: '800' },
  countLbl: { fontSize: 11, color: C.textSub, marginTop: 1 },
})
