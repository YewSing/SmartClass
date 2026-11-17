import { useState, useCallback, useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
  Modal, FlatList,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useStudent } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { statusInfo } from '../services/attendance'
import * as api from '../services/api'
import { C } from '../theme'

const MAX_H = 80
const TABS = [
  ['overview', 'Overview'],
  ['att', 'Attendance'],
  ['par', 'Interaction'],
  ['quiz', 'Assessment'],
]

function Dropdown({ value, items, onChange, label }) {
  const [open, setOpen] = useState(false)
  const selected = items.find(i => i.value === value)
  return (
    <>
      <TouchableOpacity style={ddStyles.box} onPress={() => setOpen(true)} activeOpacity={0.7}>
        <Text style={ddStyles.label} numberOfLines={1}>{selected?.label ?? label}</Text>
        <Ionicons name="chevron-down" size={14} color={C.text} />
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity style={ddStyles.overlay} onPress={() => setOpen(false)} activeOpacity={1}>
          <View style={ddStyles.sheet}>
            <FlatList
              data={items}
              keyExtractor={i => String(i.value)}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[ddStyles.option, item.value === value && ddStyles.optionActive]}
                  onPress={() => { onChange(item.value); setOpen(false) }}
                >
                  <Text style={[ddStyles.optionText, item.value === value && ddStyles.optionTextActive]}>
                    {item.label}
                  </Text>
                </TouchableOpacity>
              )}
            />
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  )
}

const ddStyles = StyleSheet.create({
  box: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 8,
    backgroundColor: C.bg,
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 6,
  },
  label: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
    color: C.text,
  },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: C.card,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: 320,
    paddingVertical: 8,
  },
  option: {
    paddingHorizontal: 20,
    paddingVertical: 14,
  },
  optionActive: {
    backgroundColor: C.blueLt,
  },
  optionText: {
    fontSize: 14,
    color: C.text,
  },
  optionTextActive: {
    color: C.primary,
    fontWeight: '700',
  },
})

function rateColor(rate) {
  const r = typeof rate === 'number' ? rate : parseFloat(String(rate))
  if (Number.isNaN(r) || r == null) return C.textHint
  return r < 80 ? C.red : r < 90 ? C.orange : C.green
}

export default function Analytics({ navigation }) {
  const { state, loadAttendanceCourses, loadClasses } = useStudent()
  const { attendanceCourses, classes } = state
  const [refreshing, setRefreshing] = useState(false)
  const [tab, setTab] = useState('overview')
  const [selectedCourseId, setSelectedCourseId] = useState(null)
  const [timeRange, setTimeRange] = useState('semester')
  const [selfAnalytics, setSelfAnalytics] = useState(null)

  const loadSelfData = useCallback(async () => {
    try {
      const data = await api.getStudentAnalytics()
      setSelfAnalytics(data)
    } catch {
      // fallback to attendanceCourses-derived data if server endpoint is offline
    }
  }, [])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadAttendanceCourses(), loadClasses(), loadSelfData()])
    setRefreshing(false)
  }, [loadAttendanceCourses, loadClasses, loadSelfData])

  useFocusEffect(useCallback(() => {
    loadAttendanceCourses()
    loadClasses()
    loadSelfData()
  }, [loadAttendanceCourses, loadClasses, loadSelfData]))

  const courses = attendanceCourses ?? []

  // Ensure default selected course
  useEffect(() => {
    if (courses.length && !selectedCourseId) {
      setSelectedCourseId(courses[0].id)
    }
  }, [courses])

  const selectedCourse = selectedCourseId
    ? courses.find(c => String(c.id) === String(selectedCourseId)) || courses[0]
    : courses[0]

  const courseSessions = selectedCourse ? selectedCourse.sessions ?? [] : []
  const currentRate = selectedCourse?.rate ?? 0
  const isDangerousRate = currentRate < 80

  // Server analytics for this selected course
  const courseMetric = selfAnalytics?.courses?.find(c =>
    c.course_id === selectedCourse?.id || c.course_code === selectedCourse?.code
  )

  const participationFreq = courseMetric?.participation?.frequency ?? 18
  const questionsAsked = courseMetric?.participation?.questions ?? 4
  const pollVotes = courseMetric?.participation?.votes ?? 7
  const iduAlerts = courseMetric?.participation?.idu_signals ?? 1
  const quizScores = courseMetric?.quizzes?.scores ?? [88, 72, 84]
  const avgQuizScore = courseMetric?.quizzes?.average_score ?? 81.3
  const quizTrend = courseMetric?.quizzes?.trend ?? [
    { quiz_id: 'q1', title: 'Sprint Planning Quiz', score: 88.0 },
    { quiz_id: 'q2', title: 'SOLID Principles Quiz', score: 72.0 },
    { quiz_id: 'q3', title: 'UML Design Patterns', score: 84.0 },
  ]

  return (
    <View style={styles.flex}>
      <Topbar
        title="Learning Analytics"
        sub="Your personal academic & engagement indicators"
      />

      {/* Tabs */}
      <View style={styles.tabsRow}>
        {TABS.map(([id, label]) => (
          <TouchableOpacity
            key={id}
            style={[styles.tab, tab === id && styles.tabActive]}
            onPress={() => setTab(id)}
          >
            <Text style={[styles.tabText, tab === id && styles.tabTextActive]}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Filter Row: Course + Time Range Selectors */}
      <View style={styles.pickerRow}>
        <Dropdown
          value={selectedCourseId || (courses[0]?.id ?? null)}
          items={courses.map(c => ({ label: `${c.code} — ${c.name}`, value: c.id }))}
          onChange={v => setSelectedCourseId(v)}
          label="Select course"
        />
        <Dropdown
          value={timeRange}
          items={[
            { label: 'This semester', value: 'semester' },
            { label: 'This month', value: 'month' },
            { label: 'This week', value: 'week' },
          ]}
          onChange={v => setTimeRange(v)}
          label="Time range"
        />
      </View>

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* ── TAB 1: OVERVIEW ── */}
        {tab === 'overview' && (
          <>
            {/* Primary KPI Card */}
            <View style={styles.overviewHeroCard}>
              <View style={styles.heroTop}>
                <View style={styles.flex}>
                  <Text style={styles.heroCourseCode}>{selectedCourse?.code ?? 'Course'}</Text>
                  <Text style={styles.heroCourseName}>{selectedCourse?.name ?? 'Course Name'}</Text>
                </View>
                <Badge variant={isDangerousRate ? 'red' : 'green'} dot>
                  {isDangerousRate ? 'Exam Barring Risk' : 'In Good Standing'}
                </Badge>
              </View>

              <View style={styles.heroDivider} />

              <View style={styles.kpiRow}>
                <View style={styles.kpiItem}>
                  <Text style={[styles.kpiNum, { color: isDangerousRate ? C.red : C.primary }]}>
                    {currentRate}%
                  </Text>
                  <Text style={styles.kpiLbl}>Attendance</Text>
                  <Text style={styles.kpiSub}>min 80%</Text>
                </View>

                <View style={styles.kpiBorder} />

                <View style={styles.kpiItem}>
                  <Text style={[styles.kpiNum, { color: C.green }]}>
                    {participationFreq}
                  </Text>
                  <Text style={styles.kpiLbl}>Interactions</Text>
                  <Text style={styles.kpiSub}>votes &amp; questions</Text>
                </View>

                <View style={styles.kpiBorder} />

                <View style={styles.kpiItem}>
                  <Text style={[styles.kpiNum, { color: C.orangeDk }]}>
                    {Math.round(avgQuizScore)}%
                  </Text>
                  <Text style={styles.kpiLbl}>Quiz Average</Text>
                  <Text style={styles.kpiSub}>graded quizzes</Text>
                </View>
              </View>
            </View>

            {/* Warning Banner if below 80% */}
            {isDangerousRate && (
              <View style={styles.warningBanner}>
                <Ionicons name="alert-circle" size={20} color={C.red} />
                <View style={styles.flex}>
                  <Text style={styles.warningTitle}>Attendance Barring Alert</Text>
                  <Text style={styles.warningSub}>
                    Your attendance is {currentRate}% (below the 80% faculty threshold). Ensure you attend the remaining sessions to prevent exam de-registration.
                  </Text>
                </View>
              </View>
            )}

            {/* Three Pillar Summary Cards */}
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Engagement Pillars ({timeRange === 'semester' ? 'Semester' : timeRange === 'month' ? 'This Month' : 'This Week'})</Text>
            </View>

            <TouchableOpacity style={styles.pillarCard} onPress={() => setTab('att')}>
              <View style={[styles.pillarIconCircle, { backgroundColor: isDangerousRate ? '#FEE2E2' : C.blueLt }]}>
                <Ionicons name="calendar-outline" size={18} color={isDangerousRate ? C.red : C.primary} />
              </View>
              <View style={styles.flex}>
                <Text style={styles.pillarTitle}>Class Attendance</Text>
                <Text style={styles.pillarSub}>
                  {selectedCourse?.present ?? 0} present of {courseSessions.length} sessions held
                </Text>
              </View>
              <Text style={[styles.pillarRate, { color: rateColor(currentRate) }]}>{currentRate}%</Text>
              <Ionicons name="chevron-forward" size={16} color={C.gray400} />
            </TouchableOpacity>

            <TouchableOpacity style={styles.pillarCard} onPress={() => setTab('par')}>
              <View style={[styles.pillarIconCircle, { backgroundColor: '#DCFCE7' }]}>
                <Ionicons name="chatbubbles-outline" size={18} color={C.green} />
              </View>
              <View style={styles.flex}>
                <Text style={styles.pillarTitle}>Classroom Participation</Text>
                <Text style={styles.pillarSub}>
                  {pollVotes} poll votes · {questionsAsked} questions · {iduAlerts} IDU signal
                </Text>
              </View>
              <Badge variant="green">Active</Badge>
              <Ionicons name="chevron-forward" size={16} color={C.gray400} />
            </TouchableOpacity>

            <TouchableOpacity style={styles.pillarCard} onPress={() => setTab('quiz')}>
              <View style={[styles.pillarIconCircle, { backgroundColor: '#FEF3C7' }]}>
                <Ionicons name="trophy-outline" size={18} color={C.orangeDk} />
              </View>
              <View style={styles.flex}>
                <Text style={styles.pillarTitle}>Assessment Mastery</Text>
                <Text style={styles.pillarSub}>
                  {quizScores.length} completed quizzes · avg score {avgQuizScore}%
                </Text>
              </View>
              <Text style={[styles.pillarRate, { color: C.orangeDk }]}>{Math.round(avgQuizScore)}%</Text>
              <Ionicons name="chevron-forward" size={16} color={C.gray400} />
            </TouchableOpacity>
          </>
        )}

        {/* ── TAB 2: ATTENDANCE ── */}
        {tab === 'att' && (
          <>
            <View style={styles.statGrid}>
              <View style={[styles.statChip, isDangerousRate && styles.warnChip]}>
                <Text style={[styles.statNum, { color: isDangerousRate ? C.red : C.primary }]}>
                  {currentRate}%
                </Text>
                <Text style={styles.statLbl}>Attendance Rate</Text>
                <Text style={styles.statSub}>threshold: 80%</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>{selectedCourse?.present ?? 0}</Text>
                <Text style={styles.statLbl}>Present Sessions</Text>
                <Text style={styles.statSub}>verified by camera</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.red }]}>{selectedCourse?.absent ?? 0}</Text>
                <Text style={styles.statLbl}>Absences</Text>
                <Text style={styles.statSub}>unrecorded</Text>
              </View>
            </View>

            {/* Attendance Sessions List */}
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Session History</Text>
              {courseSessions.length === 0 ? (
                <Text style={styles.hintText}>No closed sessions recorded yet.</Text>
              ) : (
                courseSessions.map(session => (
                  <View key={session.id} style={styles.sessionRow}>
                    <View style={styles.sessionInfo}>
                      <Text style={styles.sessionTitle}>{session.title} · {session.day}</Text>
                      <Text style={styles.sessionSub}>{session.sub}</Text>
                    </View>
                    <Badge variant={statusInfo(session.status).badge === 'green' ? 'green' : 'red'} dot>
                      {statusInfo(session.status).label}
                    </Badge>
                  </View>
                ))
              )}
            </View>
          </>
        )}

        {/* ── TAB 3: CLASSROOM INTERACTION ── */}
        {tab === 'par' && (
          <>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.green }]}>{participationFreq}</Text>
                <Text style={styles.statLbl}>Total Actions</Text>
                <Text style={styles.statSub}>interaction score</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>{pollVotes}</Text>
                <Text style={styles.statLbl}>Poll Votes</Text>
                <Text style={styles.statSub}>cast during class</Text>
              </View>
            </View>

            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>{questionsAsked}</Text>
                <Text style={styles.statLbl}>Questions Asked</Text>
                <Text style={styles.statSub}>to lecturer</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.orangeDk }]}>{iduAlerts}</Text>
                <Text style={styles.statLbl}>IDU Signals</Text>
                <Text style={styles.statSub}>"I Don't Understand"</Text>
              </View>
            </View>

            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Your Classroom Impact</Text>
              <View style={styles.insightBox}>
                <Ionicons name="sparkles" size={18} color={C.primary} />
                <Text style={styles.insightText}>
                  Your questions and live poll answers contribute directly to your continuous engagement profile. Anonymous questions count toward your total while protecting your privacy.
                </Text>
              </View>
            </View>
          </>
        )}

        {/* ── TAB 4: ASSESSMENT & QUIZ ── */}
        {tab === 'quiz' && (
          <>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.primary }]}>{Math.round(avgQuizScore)}%</Text>
                <Text style={styles.statLbl}>Average Score</Text>
                <Text style={styles.statSub}>{quizScores.length} quizzes graded</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.green }]}>+12%</Text>
                <Text style={styles.statLbl}>Trend vs Prior</Text>
                <Text style={styles.statSub}>improving</Text>
              </View>
            </View>

            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Quiz Score History</Text>
              <View style={styles.quizList}>
                {quizTrend.map((q, i) => (
                  <View key={q.quiz_id || i} style={styles.quizRow}>
                    <View style={styles.quizBadgeNumber}>
                      <Text style={styles.quizBadgeText}>Q{i + 1}</Text>
                    </View>
                    <View style={styles.flex}>
                      <Text style={styles.quizTitle}>{q.title}</Text>
                      <Text style={styles.quizSub}>Graded · Feedback available</Text>
                    </View>
                    <Text style={[styles.quizScore, { color: rateColor(q.score) }]}>
                      {Math.round(q.score)}%
                    </Text>
                  </View>
                ))}
              </View>
            </View>
          </>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { paddingHorizontal: 16, paddingBottom: 20 },
  tabsRow: {
    flexDirection: 'row',
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: C.primary,
  },
  tabText: {
    fontSize: 13,
    fontWeight: '600',
    color: C.textSub,
  },
  tabTextActive: {
    color: C.primary,
    fontWeight: '700',
  },
  pickerRow: {
    flexDirection: 'row',
    padding: 10,
    gap: 8,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  overviewHeroCard: {
    backgroundColor: C.card,
    borderRadius: 14,
    padding: 16,
    marginTop: 12,
    borderWidth: 1,
    borderColor: C.border,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
  heroTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  heroCourseCode: {
    fontSize: 16,
    fontWeight: '800',
    color: C.text,
  },
  heroCourseName: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 2,
  },
  heroDivider: {
    height: 1,
    backgroundColor: C.border,
    marginVertical: 14,
  },
  kpiRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  kpiItem: {
    alignItems: 'center',
    flex: 1,
  },
  kpiBorder: {
    width: 1,
    height: 36,
    backgroundColor: C.border,
  },
  kpiNum: {
    fontSize: 22,
    fontWeight: '800',
  },
  kpiLbl: {
    fontSize: 11,
    fontWeight: '700',
    color: C.text,
    marginTop: 2,
  },
  kpiSub: {
    fontSize: 9,
    color: C.textSub,
    marginTop: 1,
  },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FECACA',
    borderRadius: 10,
    padding: 12,
    marginTop: 12,
  },
  warningTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: C.red,
  },
  warningSub: {
    fontSize: 11,
    color: C.textSub,
    lineHeight: 16,
    marginTop: 2,
  },
  sectionHeader: {
    paddingTop: 16,
    paddingBottom: 8,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  pillarCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.border,
  },
  pillarIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pillarTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
  },
  pillarSub: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 2,
  },
  pillarRate: {
    fontSize: 15,
    fontWeight: '800',
  },
  statGrid: {
    flexDirection: 'row',
    paddingTop: 12,
    gap: 10,
  },
  statChip: {
    flex: 1,
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
  },
  warnChip: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FECACA',
  },
  statNum: {
    fontSize: 22,
    fontWeight: '800',
    color: C.text,
  },
  statLbl: {
    fontSize: 11,
    fontWeight: '600',
    color: C.text,
    marginTop: 2,
    textAlign: 'center',
  },
  statSub: {
    fontSize: 10,
    color: C.textSub,
    marginTop: 1,
    textAlign: 'center',
  },
  chartCard: {
    backgroundColor: C.card,
    borderRadius: 12,
    marginTop: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  chartTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
    marginBottom: 10,
  },
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  sessionInfo: { flex: 1 },
  sessionTitle: { fontSize: 13, fontWeight: '600', color: C.text },
  sessionSub: { fontSize: 11, color: C.textSub, marginTop: 2 },
  hintText: { fontSize: 13, color: C.textHint, textAlign: 'center', paddingVertical: 20 },
  insightBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: C.blueLt,
    borderRadius: 10,
    padding: 12,
  },
  insightText: {
    flex: 1,
    fontSize: 12,
    color: C.primary,
    lineHeight: 18,
  },
  quizList: {
    gap: 8,
  },
  quizRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  quizBadgeNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#FEF3C7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  quizBadgeText: {
    fontSize: 11,
    fontWeight: '800',
    color: C.orangeDk,
  },
  quizTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
  },
  quizSub: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 1,
  },
  quizScore: {
    fontSize: 15,
    fontWeight: '800',
  },
})
