// FR-706 — the student's own engagement summary & academic performance.
// A student sees only their own indicators (FR-701/702 computed by Module 7).
import { View, Text, ScrollView, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { MY_PROGRESS } from '../data/module2'
import { C } from '../theme'

const TINT = {
  good: { color: C.green, bg: C.greenLt },
  warn: { color: C.yellowDk, bg: C.yellowLt },
  bad: { color: C.redDk, bg: C.redLt },
}

function TrendIcon({ trend }) {
  if (trend === 'up') return <Ionicons name="trending-up" size={14} color={C.green} />
  if (trend === 'down') return <Ionicons name="trending-down" size={14} color={C.red} />
  return <Ionicons name="remove" size={14} color={C.textHint} />
}

export default function MyProgress() {
  return (
    <View style={styles.flex}>
      <Topbar title="My Progress" sub="Your engagement & performance" />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Overall summary — FR-702 indicators, own data only */}
        <View style={styles.overallCard}>
          <Text style={styles.overallTitle}>Overall this semester</Text>
          <View style={styles.overallGrid}>
            {MY_PROGRESS.overall.map(s => {
              const t = TINT[s.tint] ?? TINT.good
              return (
                <View key={s.label} style={[styles.overallCell, { backgroundColor: t.bg }]}>
                  <Text style={[styles.overallValue, { color: t.color }]}>{s.value}</Text>
                  <Text style={styles.overallLbl}>{s.label}</Text>
                </View>
              )
            })}
          </View>
        </View>

        {MY_PROGRESS.courses.map(course => (
          <View key={course.code} style={styles.courseCard}>
            <View style={styles.courseHeader}>
              <View>
                <Text style={styles.courseCode}>{course.code}</Text>
                <Text style={styles.courseName}>{course.name}</Text>
              </View>
              <TrendIcon trend={course.participation.trend} />
            </View>

            {/* Attendance — FR-309 rates reused here */}
            <View style={styles.metricRow}>
              <Ionicons name="calendar-outline" size={13} color={C.primary} />
              <Text style={styles.metricLbl}>Attendance</Text>
              <Text style={[styles.metricVal, { color: course.attendance.rate < 80 ? C.red : C.green }]}>
                {course.attendance.rate}% ({course.attendance.present}/{course.attendance.total})
              </Text>
            </View>
            <View style={styles.track}>
              <View style={[styles.fill, { width: `${course.attendance.rate}%`, backgroundColor: course.attendance.rate < 80 ? C.red : C.green }]} />
            </View>

            {/* Participation — FR-702 counts */}
            <View style={styles.metricRow}>
              <Ionicons name="stats-chart-outline" size={13} color={C.purple} />
              <Text style={styles.metricLbl}>Participation</Text>
            </View>
            <View style={styles.partRow}>
              <View style={styles.partChip}>
                <Text style={styles.partNum}>{course.participation.questions}</Text>
                <Text style={styles.partLbl}>Questions</Text>
              </View>
              <View style={[styles.partChip, { backgroundColor: C.redLt }]}>
                <Text style={[styles.partNum, { color: C.red }]}>{course.participation.idu}</Text>
                <Text style={styles.partLbl}>I Don't Understand</Text>
              </View>
              <View style={[styles.partChip, { backgroundColor: C.purpleLt }]}>
                <Text style={[styles.partNum, { color: C.purple }]}>{course.participation.polls}</Text>
                <Text style={styles.partLbl}>Polls voted</Text>
              </View>
            </View>

            {/* Quiz scores & trend — FR-702 */}
            <View style={styles.metricRow}>
              <Ionicons name="document-text-outline" size={13} color={C.green} />
              <Text style={styles.metricLbl}>Quiz scores</Text>
            </View>
            {course.quizzes.map(qz => (
              <View key={qz.title} style={styles.quizRow}>
                <Text style={styles.quizName}>{qz.title}</Text>
                <TrendIcon trend={qz.trend} />
                <Text style={[styles.quizScore, { color: qz.score < 60 ? C.red : C.text }]}>{qz.score}%</Text>
              </View>
            ))}

            {/* Early-warning flag — FR-707/709 shown to the student */}
            {course.flag && (
              <View style={styles.flagBanner}>
                <Ionicons name="warning" size={14} color={C.yellowDk} />
                <Text style={styles.flagText}>
                  Early warning: {course.flag.condition}. Talk to your lecturer — support is available.
                </Text>
              </View>
            )}
          </View>
        ))}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  overallCard: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 12,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  overallTitle: { fontSize: 12, fontWeight: '700', color: C.textSub, marginBottom: 10 },
  overallGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  overallCell: {
    flexBasis: '47%', flexGrow: 1, borderRadius: 10, padding: 12, alignItems: 'flex-start',
  },
  overallValue: { fontSize: 20, fontWeight: '800' },
  overallLbl: { fontSize: 11, color: C.textSub, marginTop: 2 },
  courseCard: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 12,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  courseHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start',
    marginBottom: 10,
  },
  courseCode: { fontSize: 12, fontWeight: '800', color: C.primary },
  courseName: { fontSize: 14, fontWeight: '700', color: C.text },
  metricRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 10, marginBottom: 6 },
  metricLbl: { fontSize: 12, fontWeight: '700', color: C.textSub, flex: 1 },
  metricVal: { fontSize: 12, fontWeight: '800' },
  track: { height: 7, borderRadius: 4, backgroundColor: C.gray100, overflow: 'hidden' },
  fill: { height: 7, borderRadius: 4 },
  partRow: { flexDirection: 'row', gap: 8 },
  partChip: {
    flex: 1, backgroundColor: C.blueLt, borderRadius: 10, padding: 10, alignItems: 'center',
  },
  partNum: { fontSize: 18, fontWeight: '800', color: C.primary },
  partLbl: { fontSize: 9, color: C.textSub, textAlign: 'center', marginTop: 2 },
  quizRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 8, borderTopWidth: 1, borderTopColor: C.border, marginTop: 2,
  },
  quizName: { flex: 1, fontSize: 13, color: C.text },
  quizScore: { fontSize: 14, fontWeight: '800' },
  flagBanner: {
    flexDirection: 'row', gap: 8, marginTop: 10,
    backgroundColor: C.yellowLt, borderWidth: 1, borderColor: C.yellow,
    borderRadius: 10, padding: 10,
  },
  flagText: { flex: 1, fontSize: 11, color: C.yellowDk, lineHeight: 16 },
})
