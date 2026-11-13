// Module 7 — Learning Analytics & Early Warning (lecturer view).
// Tabs: Students (FR-703 per-student indicators) · Class trend (FR-704/705) ·
// At-risk (FR-707/709/710 list with triggering conditions).
// Frontend-only: attendance/participation/quiz indicators come from module2
// fixtures until M7 is wired to M3 (FR-313), M5 (FR-509) and M6 (FR-614).
import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Modal, FlatList, RefreshControl,
} from 'react-native'
import Svg, { Polyline, Circle } from 'react-native-svg'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import { STUDENT_INDICATORS, TOPIC_PERFORMANCE, CLASS_OVERVIEW } from '../data/module2'
import { C } from '../theme'

const TABS = [['students', 'Students'], ['trend', 'Class Trend'], ['risk', 'At-Risk']]

function trendIcon(t) {
  if (t === 'up') return <Ionicons name="trending-up" size={13} color={C.green} />
  if (t === 'down') return <Ionicons name="trending-down" size={13} color={C.red} />
  return <Ionicons name="remove" size={13} color={C.textHint} />
}

function getDateParams(range) {
  const today = new Date()
  const pad = n => String(n).padStart(2, '0')
  const fmt = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  if (range === 'month') {
    return { from_date: fmt(new Date(today.getFullYear(), today.getMonth(), 1)), to_date: fmt(today) }
  }
  if (range === 'week') {
    const mon = new Date(today)
    mon.setDate(today.getDate() - ((today.getDay() + 6) % 7))
    return { from_date: fmt(mon), to_date: fmt(today) }
  }
  return {}
}

function Dropdown({ value, items, onChange }) {
  const [open, setOpen] = useState(false)
  const selected = items.find(i => i.value === value)
  return (
    <>
      <TouchableOpacity style={ddStyles.box} onPress={() => setOpen(true)} activeOpacity={0.7}>
        <Text style={ddStyles.label} numberOfLines={1}>{selected?.label ?? '—'}</Text>
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
    flex: 1, flexDirection: 'row', alignItems: 'center', borderWidth: 1.5,
    borderColor: C.border, borderRadius: 8, backgroundColor: C.bg,
    paddingHorizontal: 10, paddingVertical: 8, gap: 6,
  },
  label: { flex: 1, fontSize: 13, fontWeight: '500', color: C.text },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: C.card, borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: 320, paddingVertical: 8 },
  option: { paddingHorizontal: 20, paddingVertical: 14 },
  optionActive: { backgroundColor: C.blueLt },
  optionText: { fontSize: 14, color: C.text },
  optionTextActive: { color: C.primary, fontWeight: '700' },
})

// Simple bar chart using View-based bars
function BarChart({ heights, labels, color }) {
  return (
    <View style={bStyles.chart}>
      {heights.map((h, i) => (
        <View key={i} style={bStyles.col}>
          <View style={bStyles.barTrack}>
            <View style={[bStyles.bar, { height: h, backgroundColor: color }]} />
          </View>
          <Text style={bStyles.barLabel} numberOfLines={1}>{labels[i]}</Text>
        </View>
      ))}
    </View>
  )
}

const bStyles = StyleSheet.create({
  chart: { flexDirection: 'row', alignItems: 'flex-end', height: 110, gap: 4, paddingTop: 10 },
  col: { flex: 1, alignItems: 'center', gap: 4 },
  barTrack: { height: 90, justifyContent: 'flex-end', width: '100%' },
  bar: { borderRadius: 3, width: '100%', minHeight: 4 },
  barLabel: { fontSize: 8, color: C.textHint },
})

const ATT_BARS = [66, 78, 90, 80, 96, 85, 88]
const ATT_LABELS = ['W6S1', 'W6S2', 'W7S1', 'W7S2', 'W8S1', 'W8S2', 'W9S1']
const PAR_BARS = [55, 62, 70, 74, 79, 84]
const PAR_LABELS = ['W5', 'W6', 'W7', 'W8', 'W9', 'W10']

export default function Analytics({ navigation }) {
  const { state, loadAnalytics, loadAllClasses, openModal } = useLecturer()
  const { allClasses, analytics, analyticsLoading } = state
  const [tab, setTab] = useState('students')
  const [selectedOccId, setSelectedOccId] = useState(null)
  const [timeRange, setTimeRange] = useState('semester')

  useEffect(() => { if (!allClasses.length) loadAllClasses() }, [])

  useEffect(() => {
    if (allClasses.length && !selectedOccId) setSelectedOccId(allClasses[0].id)
  }, [allClasses])

  useEffect(() => {
    if (selectedOccId) loadAnalytics(selectedOccId, getDateParams(timeRange))
  }, [selectedOccId, timeRange])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([
      loadAllClasses(),
      selectedOccId ? loadAnalytics(selectedOccId, getDateParams(timeRange)) : Promise.resolve(),
    ])
    setRefreshing(false)
  }, [loadAllClasses, loadAnalytics, selectedOccId, timeRange])

  const atRiskStudents = STUDENT_INDICATORS.filter(s => s.flagged)
  const enrolled = analytics?.enrolled_count || CLASS_OVERVIEW.enrolled
  const barHeights = (analytics?.sessions ?? []).map(s =>
    Math.max(6, Math.round((s.present_count / Math.max(enrolled, 1)) * 90))
  )
  const barLabels = (analytics?.sessions ?? []).map(s => s.label.replace('Week ', 'W'))

  return (
    <View style={styles.flex}>
      <Topbar title="Learning Analytics" sub="Engagement & early warning" />

      {/* Class selector */}
      <View style={styles.pickerRow}>
        <Dropdown
          value={selectedOccId}
          items={allClasses.map(c => ({ label: `${c.code} — ${c.name}`, value: c.id }))}
          onChange={v => setSelectedOccId(v)}
        />
        <Dropdown
          value={timeRange}
          items={[
            { label: 'This semester', value: 'semester' },
            { label: 'This month', value: 'month' },
            { label: 'This week', value: 'week' },
          ]}
          onChange={v => setTimeRange(v)}
        />
      </View>

      {/* Tabs */}
      <View style={styles.tabsRow}>
        {TABS.map(([id, label]) => (
          <TouchableOpacity
            key={id}
            style={[styles.tab, tab === id && styles.tabActive]}
            onPress={() => setTab(id)}
          >
            <Text style={[styles.tabText, tab === id && styles.tabTextActive]}>{label}</Text>
            {id === 'risk' && atRiskStudents.length > 0 && (
              <View style={styles.tabBadge}><Text style={styles.tabBadgeText}>{atRiskStudents.length}</Text></View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* ── Students tab — FR-703 ── */}
        {tab === 'students' && (
          <>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.green }]}>{CLASS_OVERVIEW.attendanceRate}%</Text>
                <Text style={styles.statLbl}>Avg attendance</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.purple }]}>{CLASS_OVERVIEW.participationRate}%</Text>
                <Text style={styles.statLbl}>Avg participation</Text>
              </View>
            </View>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>{CLASS_OVERVIEW.avgQuizScore}%</Text>
                <Text style={styles.statLbl}>Avg quiz score</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.red }]}>{atRiskStudents.length}</Text>
                <Text style={styles.statLbl}>At-risk students</Text>
              </View>
            </View>

            <Text style={styles.sectionTitle}>Individual indicators (FR-702)</Text>
            {STUDENT_INDICATORS.map(s => (
              <View key={s.id} style={[styles.card, s.flagged && styles.cardFlagged]}>
                <View style={styles.studentTop}>
                  <View style={styles.avatar}><Text style={styles.avatarText}>
                    {s.name.split(' ').map(p => p[0]).slice(0, 2).join('')}
                  </Text></View>
                  <View style={styles.studentId}>
                    <Text style={styles.studentName}>{s.name}</Text>
                    <Text style={styles.studentMatric}>{s.id}</Text>
                  </View>
                  {trendIcon(s.trend)}
                </View>
                <View style={styles.indRow}>
                  <View style={styles.indCell}>
                    <Text style={[styles.indNum, { color: s.attendance < 80 ? C.red : C.green }]}>{s.attendance}%</Text>
                    <Text style={styles.indLbl}>Attendance</Text>
                  </View>
                  <View style={styles.indCell}>
                    <Text style={styles.indNum}>{s.questions}</Text>
                    <Text style={styles.indLbl}>Questions</Text>
                  </View>
                  <View style={styles.indCell}>
                    <Text style={[styles.indNum, { color: s.idu >= 3 ? C.orange : C.text }]}>{s.idu}</Text>
                    <Text style={styles.indLbl}>IDU</Text>
                  </View>
                  <View style={styles.indCell}>
                    <Text style={[styles.indNum, { color: s.quizAvg < 60 ? C.red : C.text }]}>{s.quizAvg}%</Text>
                    <Text style={styles.indLbl}>Quiz avg</Text>
                  </View>
                  <View style={styles.indCell}>
                    <Text style={styles.indNumSm}>{s.participation}</Text>
                    <Text style={styles.indLbl}>Particip.</Text>
                  </View>
                </View>
                {s.flagged && (
                  <View style={styles.flagRow}>
                    <Ionicons name="warning" size={12} color={C.redDk} />
                    <Text style={styles.flagText}>{s.condition}</Text>
                  </View>
                )}
              </View>
            ))}
          </>
        )}

        {/* ── Class trend tab — FR-704 / FR-705 ── */}
        {tab === 'trend' && (
          <>
            {analyticsLoading ? (
              <View style={styles.centered}><Text style={styles.hintText}>Loading…</Text></View>
            ) : (
              <>
                <View style={styles.chartCard}>
                  <Text style={styles.chartTitle}>Class attendance across sessions</Text>
                  {(analytics?.sessions ?? []).length > 0 ? (
                    <BarChart heights={barHeights} labels={barLabels} color={C.primary} />
                  ) : (
                    <BarChart heights={ATT_BARS} labels={ATT_LABELS} color={C.primary} />
                  )}
                </View>

                <View style={styles.chartCard}>
                  <Text style={styles.chartTitle}>Class engagement trend</Text>
                  <Svg width="100%" height={90} viewBox="0 0 300 90">
                    <Polyline
                      points="10,70 60,62 110,52 160,48 210,40 290,28"
                      fill="none" stroke={C.green} strokeWidth="2.5"
                      strokeLinecap="round" strokeLinejoin="round"
                    />
                    {[[10, 70], [60, 62], [110, 52], [160, 48], [210, 40], [290, 28]].map(([x, y], i) => (
                      <Circle key={i} cx={x} cy={y} r="3.5" fill={C.green} />
                    ))}
                  </Svg>
                  <Text style={styles.svgNote}>Participation rate across sessions (FR-509 data) — ↑ improving</Text>
                </View>

                {/* FR-705 — assessment performance by topic */}
                <View style={styles.chartCard}>
                  <Text style={styles.chartTitle}>Assessment performance by topic</Text>
                  {TOPIC_PERFORMANCE.map(t => {
                    const weak = t.avg < 60
                    return (
                      <View key={t.topic} style={styles.topicRow}>
                        <View style={styles.topicHead}>
                          <Text style={styles.topicName}>{t.topic}</Text>
                          <Text style={[styles.topicAvg, { color: weak ? C.red : t.avg < 70 ? C.orange : C.green }]}>{t.avg}%</Text>
                        </View>
                        <View style={styles.topicTrack}>
                          <View style={[styles.topicFill, { width: `${t.avg}%`, backgroundColor: weak ? C.red : t.avg < 70 ? C.orange : C.green }]} />
                          {/* 50% frequently-missed threshold marker (FR-613 config) */}
                        </View>
                        <Text style={styles.topicSrc} numberOfLines={1}>{t.missRate >= 50 ? '⚠ ' : ''}{t.material}</Text>
                      </View>
                    )
                  })}
                  <Text style={styles.svgNote}>Source rows link each topic to the material section to revisit (FR-614 → FR-824).</Text>
                </View>
              </>
            )}
          </>
        )}

        {/* ── At-risk tab — FR-710 ── */}
        {tab === 'risk' && (
          <>
            <View style={styles.warnBanner}>
              <Ionicons name="alert-circle" size={15} color={C.yellowDk} />
              <Text style={styles.warnText}>
                Flags are re-evaluated after every closed attendance session and every graded quiz (FR-708). Each flag is delivered to you as an important notification (FR-210).
              </Text>
            </View>
            {atRiskStudents.length === 0 ? (
              <View style={styles.centered}>
                <Ionicons name="shield-checkmark" size={34} color={C.green} />
                <Text style={styles.hintText}>No at-risk students right now.</Text>
              </View>
            ) : atRiskStudents.map(s => (
              <View key={s.id} style={[styles.card, styles.cardFlagged]}>
                <View style={styles.studentTop}>
                  <View style={[styles.avatar, { backgroundColor: C.redLt }]}>
                    <Text style={[styles.avatarText, { color: C.redDk }]}>
                      {s.name.split(' ').map(p => p[0]).slice(0, 2).join('')}
                    </Text>
                  </View>
                  <View style={styles.studentId}>
                    <Text style={styles.studentName}>{s.name}</Text>
                    <Text style={styles.studentMatric}>{s.id}</Text>
                  </View>
                  <View style={styles.riskBadge}>
                    <Text style={styles.riskBadgeText}>AT-RISK</Text>
                  </View>
                </View>
                <View style={styles.conditionBox}>
                  <Text style={styles.conditionLbl}>Condition met (FR-707)</Text>
                  <Text style={styles.conditionText}>{s.condition}</Text>
                </View>
                <View style={styles.followRow}>
                  <TouchableOpacity style={styles.followBtn}>
                    <Ionicons name="chatbubble-ellipses" size={13} color={C.primary} />
                    <Text style={styles.followBtnText}>Message student</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.followBtn}>
                    <Ionicons name="document-text" size={13} color={C.primary} />
                    <Text style={styles.followBtnText}>View full report</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  tabsRow: {
    flexDirection: 'row', backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  tab: {
    flex: 1, paddingVertical: 12, alignItems: 'center', flexDirection: 'row',
    justifyContent: 'center', gap: 5, borderBottomWidth: 2, borderBottomColor: 'transparent',
  },
  tabActive: { borderBottomColor: C.primary },
  tabText: { fontSize: 14, fontWeight: '600', color: C.textSub },
  tabTextActive: { color: C.primary },
  tabBadge: {
    backgroundColor: C.red, minWidth: 16, height: 16, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4,
  },
  tabBadgeText: { fontSize: 9, fontWeight: '800', color: '#fff' },
  pickerRow: {
    flexDirection: 'row', padding: 10, gap: 8,
    backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  statGrid: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 12, gap: 10 },
  statChip: {
    flex: 1, backgroundColor: C.card, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: C.border, alignItems: 'center',
  },
  statNum: { fontSize: 22, fontWeight: '800', color: C.text },
  statLbl: { fontSize: 11, color: C.textSub, marginTop: 2, textAlign: 'center' },
  sectionTitle: {
    fontSize: 11, fontWeight: '700', color: C.textHint, textTransform: 'uppercase',
    letterSpacing: 0.6, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 6,
  },
  card: {
    backgroundColor: C.card, marginHorizontal: 16, marginBottom: 8,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 12,
  },
  cardFlagged: { borderColor: C.red, borderWidth: 1.5 },
  studentTop: { flexDirection: 'row', alignItems: 'center', gap: 9, marginBottom: 10 },
  avatar: {
    width: 34, height: 34, borderRadius: 17, backgroundColor: C.blueLt,
    alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { fontSize: 12, fontWeight: '800', color: C.primary },
  studentId: { flex: 1 },
  studentName: { fontSize: 14, fontWeight: '700', color: C.text },
  studentMatric: { fontSize: 11, color: C.textHint },
  indRow: { flexDirection: 'row' },
  indCell: { flex: 1, alignItems: 'center', gap: 2 },
  indNum: { fontSize: 15, fontWeight: '800', color: C.text },
  indNumSm: { fontSize: 11, fontWeight: '800', color: C.text, marginTop: 3 },
  indLbl: { fontSize: 9, color: C.textHint, textAlign: 'center' },
  flagRow: {
    flexDirection: 'row', gap: 6, marginTop: 10, backgroundColor: C.redLt,
    borderRadius: 8, padding: 8, alignItems: 'flex-start',
  },
  flagText: { flex: 1, fontSize: 11, color: C.redDk, lineHeight: 16 },
  chartCard: {
    backgroundColor: C.card, borderRadius: 12, margin: 16, marginTop: 12,
    padding: 14, borderWidth: 1, borderColor: C.border,
  },
  chartTitle: { fontSize: 13, fontWeight: '700', color: C.text, marginBottom: 10 },
  svgNote: { fontSize: 11, color: C.textHint, textAlign: 'center', marginTop: 6 },
  topicRow: { marginBottom: 12 },
  topicHead: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  topicName: { fontSize: 13, fontWeight: '600', color: C.text },
  topicAvg: { fontSize: 13, fontWeight: '800' },
  topicTrack: { height: 7, borderRadius: 4, backgroundColor: C.gray100, overflow: 'hidden' },
  topicFill: { height: 7, borderRadius: 4 },
  topicSrc: { fontSize: 10, color: C.textHint, marginTop: 3 },
  warnBanner: {
    flexDirection: 'row', gap: 8, marginHorizontal: 16, marginTop: 12,
    backgroundColor: C.yellowLt, borderWidth: 1, borderColor: C.yellow,
    borderRadius: 10, padding: 10, alignItems: 'flex-start',
  },
  warnText: { flex: 1, fontSize: 11, color: C.yellowDk, lineHeight: 16 },
  riskBadge: {
    backgroundColor: C.red, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
  },
  riskBadgeText: { fontSize: 9, fontWeight: '900', color: '#fff', letterSpacing: 0.5 },
  conditionBox: {
    backgroundColor: C.redLt, borderRadius: 9, padding: 10, borderWidth: 1, borderColor: C.red,
  },
  conditionLbl: { fontSize: 9, fontWeight: '800', color: C.redDk, textTransform: 'uppercase', marginBottom: 3 },
  conditionText: { fontSize: 12, color: C.redDk, lineHeight: 17 },
  followRow: { flexDirection: 'row', gap: 8, marginTop: 10 },
  followBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    paddingVertical: 9, borderRadius: 9, borderWidth: 1.5, borderColor: C.primary,
  },
  followBtnText: { fontSize: 12, fontWeight: '700', color: C.primary },
  centered: { alignItems: 'center', padding: 40, gap: 8 },
  hintText: { fontSize: 13, color: C.textHint, textAlign: 'center' },
})
