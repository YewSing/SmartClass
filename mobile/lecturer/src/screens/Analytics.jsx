import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Modal, FlatList, RefreshControl,
} from 'react-native'
import Svg, { Polyline, Circle } from 'react-native-svg'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

const MAX_H = 90
const TABS = [
  ['overview', 'Overview'],
  ['att', 'Attendance'],
  ['par', 'Classroom Interaction'],
  ['quiz', 'Assessment & Quiz'],
]

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
  if (Number.isNaN(r)) return C.textHint
  return r < 80 ? C.red : r < 90 ? C.orange : C.green
}

// Interactive session bar chart highlighting dangerous rate sessions in red (<80%)
function SessionBarChart({ sessions, enrolled, onSelectSession, selectedSessionId }) {
  const safeEnrolled = enrolled || 1
  return (
    <View style={bStyles.chart}>
      {sessions.map((s, i) => {
        const present = s.present_count ?? 0
        const rate = s.rate != null ? s.rate : Math.round((present / safeEnrolled) * 100)
        const isDangerous = rate < 80 // Barring warning threshold (<80%)
        const barHeight = Math.max(8, Math.min(MAX_H, Math.round((rate / 100) * MAX_H)))
        const barColor = isDangerous ? C.red : C.primary
        const isSelected = selectedSessionId === (s.session_id ?? i)

        return (
          <TouchableOpacity
            key={s.session_id ?? i}
            style={[bStyles.col, isSelected && bStyles.colSelected]}
            onPress={() => onSelectSession?.(s)}
            activeOpacity={0.7}
          >
            <Text style={[bStyles.rateLabel, { color: isDangerous ? C.red : C.textSub }]}>
              {rate}%
            </Text>
            <View style={bStyles.barTrack}>
              <View
                style={[
                  bStyles.bar,
                  {
                    height: barHeight,
                    backgroundColor: barColor,
                    borderColor: isDangerous ? '#B91C1C' : 'transparent',
                    borderWidth: isDangerous ? 1 : 0,
                  },
                ]}
              />
            </View>
            <View style={bStyles.labelWrap}>
              <Text style={[bStyles.barLabel, isDangerous && bStyles.barLabelDanger]} numberOfLines={1}>
                {s.label.replace('Week ', 'W')}
              </Text>
              {isDangerous && (
                <View style={bStyles.dangerDot} />
              )}
            </View>
          </TouchableOpacity>
        )
      })}
    </View>
  )
}

const bStyles = StyleSheet.create({
  chart: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 125,
    gap: 6,
    paddingTop: 8,
  },
  col: {
    flex: 1,
    alignItems: 'center',
    gap: 3,
    paddingVertical: 2,
    borderRadius: 6,
  },
  colSelected: {
    backgroundColor: C.blueLt,
  },
  rateLabel: {
    fontSize: 9,
    fontWeight: '700',
    marginBottom: 2,
  },
  barTrack: {
    height: 80,
    justifyContent: 'flex-end',
    width: '100%',
    backgroundColor: '#F3F4F6',
    borderRadius: 4,
    overflow: 'hidden',
  },
  bar: {
    borderRadius: 4,
    width: '100%',
    minHeight: 6,
  },
  labelWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    marginTop: 2,
  },
  barLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: C.textHint,
  },
  barLabelDanger: {
    color: C.red,
    fontWeight: '800',
  },
  dangerDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: C.red,
  },
})

export default function Analytics({ navigation }) {
  const { state, openModal, loadAnalytics, loadAllClasses } = useLecturer()
  const { allClasses, analytics, analyticsLoading } = state
  const [tab, setTab] = useState('overview')
  const [selectedOccId, setSelectedOccId] = useState(null)
  const [timeRange, setTimeRange] = useState('semester')
  const [selectedSession, setSelectedSession] = useState(null)

  useEffect(() => {
    if (!allClasses.length) loadAllClasses()
  }, [])

  useEffect(() => {
    if (allClasses.length && !selectedOccId) {
      setSelectedOccId(allClasses[0].id)
    }
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

  const selectedClass = allClasses.find(c => c.id === selectedOccId)
  const sessions = analytics?.sessions ?? []
  const atRisk = analytics?.at_risk_students ?? []
  const enrolled = analytics?.enrolled_count || 26
  const dangerousSessions = sessions.filter(s => {
    const present = s.present_count ?? 0
    const rate = s.rate != null ? s.rate : Math.round((present / enrolled) * 100)
    return rate < 80
  })

  return (
    <View style={styles.flex}>
      <Topbar
        title="Learning Analytics"
        sub="Class engagement, attendance and early warnings"
        right={
          <TouchableOpacity
            style={[styles.exportBtn, tab !== 'att' && tab !== 'overview' && { opacity: 0.5 }]}
            onPress={() => {
              if (!selectedOccId || !analytics) return
              const cls = allClasses.find(c => c.id === selectedOccId)
              const rangeLabel = timeRange === 'semester' ? 'This semester'
                : timeRange === 'month' ? 'This month'
                  : 'This week'
              openModal('export', {
                scope: 'occurrence',
                id: selectedOccId,
                filename: `attendance_report_${cls?.code ?? 'report'}_${new Date().getFullYear()}.csv`,
                dateParams: getDateParams(timeRange),
                subtitle: `${cls?.code ?? ''} · ${rangeLabel}`,
                sessionCount: analytics.sessions_held,
                studentCount: analytics.enrolled_count,
              })
            }}
          >
            <Ionicons name="download-outline" size={14} color="#fff" />
            <Text style={styles.exportBtnText}>Export</Text>
          </TouchableOpacity>
        }
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

      {/* Filter row */}
      <View style={styles.pickerRow}>
        <Dropdown
          value={selectedOccId}
          items={allClasses.map(c => ({ label: `${c.code} — ${c.name}`, value: c.id }))}
          onChange={v => { setSelectedOccId(v); setSelectedSession(null) }}
        />
        <Dropdown
          value={timeRange}
          items={[
            { label: 'This semester', value: 'semester' },
            { label: 'This month', value: 'month' },
            { label: 'This week', value: 'week' },
          ]}
          onChange={v => { setTimeRange(v); setSelectedSession(null) }}
        />
      </View>

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* ── TAB 1: OVERVIEW ── */}
        {tab === 'overview' && (
          analyticsLoading ? (
            <View style={styles.centered}>
              <Text style={styles.hintText}>Loading overview…</Text>
            </View>
          ) : !analytics ? (
            <View style={styles.centered}>
              <Text style={styles.hintText}>No data available for this class</Text>
            </View>
          ) : (
            <>
              {/* Executive Hero Card */}
              <View style={styles.overviewHeroCard}>
                <View style={styles.heroTop}>
                  <View style={styles.flex}>
                    <Text style={styles.heroCourseCode}>{selectedClass?.code ?? 'Course'}</Text>
                    <Text style={styles.heroCourseName}>{selectedClass?.name ?? 'Course Name'}</Text>
                  </View>
                  <Badge variant={analytics.avg_attendance_rate < 80 ? 'red' : 'green'} dot>
                    {analytics.avg_attendance_rate < 80 ? 'Attention Needed' : 'Healthy Turnout'}
                  </Badge>
                </View>

                <View style={styles.heroDivider} />

                <View style={styles.kpiRow}>
                  <View style={styles.kpiItem}>
                    <Text style={[styles.kpiNum, { color: analytics.avg_attendance_rate < 80 ? C.red : C.primary }]}>
                      {analytics.avg_attendance_rate}%
                    </Text>
                    <Text style={styles.kpiLbl}>Avg Attendance</Text>
                    <Text style={styles.kpiSub}>threshold: 80%</Text>
                  </View>

                  <View style={styles.kpiBorder} />

                  <View style={styles.kpiItem}>
                    <Text style={[styles.kpiNum, { color: atRisk.length > 0 ? C.red : C.green }]}>
                      {atRisk.length}
                    </Text>
                    <Text style={styles.kpiLbl}>At-Risk Students</Text>
                    <Text style={styles.kpiSub}>barring alert</Text>
                  </View>

                  <View style={styles.kpiBorder} />

                  <View style={styles.kpiItem}>
                    <Text style={[styles.kpiNum, { color: C.green }]}>82%</Text>
                    <Text style={styles.kpiLbl}>In-Class Response</Text>
                    <Text style={styles.kpiSub}>polls &amp; Qs</Text>
                  </View>

                  <View style={styles.kpiBorder} />

                  <View style={styles.kpiItem}>
                    <Text style={[styles.kpiNum, { color: C.orangeDk }]}>74%</Text>
                    <Text style={styles.kpiLbl}>Quiz Average</Text>
                    <Text style={styles.kpiSub}>3 assessments</Text>
                  </View>
                </View>
              </View>

              {/* Actionable Warning Callout */}
              {dangerousSessions.length > 0 && (
                <View style={styles.warningBanner}>
                  <Ionicons name="alert-circle" size={20} color={C.red} />
                  <View style={styles.flex}>
                    <Text style={styles.warningTitle}>
                      {dangerousSessions.length} Dangerous Turnout Session{dangerousSessions.length > 1 ? 's' : ''} Detected
                    </Text>
                    <Text style={styles.warningSub}>
                      Recent sessions recorded attendance below 80%. {atRisk.length} student{atRisk.length !== 1 ? 's are' : ' is'} currently below the threshold for final exam barring.
                    </Text>
                  </View>
                </View>
              )}

              {/* Module Pillars Section */}
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>Learning Health Pillars</Text>
              </View>

              {/* Attendance Pillar */}
              <TouchableOpacity style={styles.pillarCard} activeOpacity={0.8} onPress={() => setTab('att')}>
                <View style={[styles.pillarIconCircle, { backgroundColor: analytics.avg_attendance_rate < 80 ? '#FEE2E2' : C.blueLt }]}>
                  <Ionicons name="calendar-outline" size={18} color={analytics.avg_attendance_rate < 80 ? C.red : C.primary} />
                </View>
                <View style={styles.flex}>
                  <Text style={styles.pillarTitle}>Attendance &amp; Verification</Text>
                  <Text style={styles.pillarSub}>
                    {analytics.sessions_held} sessions held · {atRisk.length} at-risk students flagged
                  </Text>
                </View>
                <Text style={[styles.pillarRate, { color: rateColor(analytics.avg_attendance_rate) }]}>
                  {analytics.avg_attendance_rate}%
                </Text>
                <Ionicons name="chevron-forward" size={16} color={C.gray400} />
              </TouchableOpacity>

              {/* Classroom Interaction Pillar */}
              <TouchableOpacity style={styles.pillarCard} activeOpacity={0.8} onPress={() => setTab('par')}>
                <View style={[styles.pillarIconCircle, { backgroundColor: '#DCFCE7' }]}>
                  <Ionicons name="chatbubbles-outline" size={18} color={C.green} />
                </View>
                <View style={styles.flex}>
                  <Text style={styles.pillarTitle}>Classroom Interaction</Text>
                  <Text style={styles.pillarSub}>
                    14 student questions · 8 live polls · 3 "Don't Understand" alerts
                  </Text>
                </View>
                <Badge variant="green">82% Active</Badge>
                <Ionicons name="chevron-forward" size={16} color={C.gray400} />
              </TouchableOpacity>

              {/* Assessment Pillar */}
              <TouchableOpacity style={styles.pillarCard} activeOpacity={0.8} onPress={() => setTab('quiz')}>
                <View style={[styles.pillarIconCircle, { backgroundColor: '#FEF3C7' }]}>
                  <Ionicons name="trophy-outline" size={18} color={C.orangeDk} />
                </View>
                <View style={styles.flex}>
                  <Text style={styles.pillarTitle}>Assessment &amp; Mastery</Text>
                  <Text style={styles.pillarSub}>
                    Class average 74% (+8% vs first quiz) · 3 quizzes graded
                  </Text>
                </View>
                <Text style={[styles.pillarRate, { color: C.orangeDk }]}>74%</Text>
                <Ionicons name="chevron-forward" size={16} color={C.gray400} />
              </TouchableOpacity>
            </>
          )
        )}

        {/* ── TAB 2: ATTENDANCE ── */}
        {tab === 'att' && (
          analyticsLoading ? (
            <View style={styles.centered}>
              <Text style={styles.hintText}>Loading analytics…</Text>
            </View>
          ) : !analytics ? (
            <View style={styles.centered}>
              <Text style={styles.hintText}>No data available for this class</Text>
            </View>
          ) : (
            <>
              {/* Executive Stat Grid */}
              <View style={styles.statGrid}>
                <View style={[styles.statChip, analytics.avg_attendance_rate < 80 && styles.statChipDanger]}>
                  <Text style={[styles.statNum, analytics.avg_attendance_rate < 80 && { color: C.red }]}>
                    {analytics.avg_attendance_rate}%
                  </Text>
                  <Text style={styles.statLbl}>Course Avg Attendance</Text>
                  <Text style={styles.statSub}>threshold: 80%</Text>
                </View>
                <View style={styles.statChip}>
                  <Text style={styles.statNum}>{analytics.sessions_held}</Text>
                  <Text style={styles.statLbl}>Sessions Held</Text>
                  <Text style={styles.statSub}>{enrolled} enrolled</Text>
                </View>
              </View>

              <View style={styles.statGrid}>
                <View style={[styles.statChip, atRisk.length > 0 && styles.statChipDanger]}>
                  <Text style={[styles.statNum, { color: atRisk.length > 0 ? C.red : C.green }]}>
                    {atRisk.length}
                  </Text>
                  <Text style={styles.statLbl}>At-Risk Students</Text>
                  <Text style={styles.statSub}>&lt;80% (exam barring)</Text>
                </View>
                <View style={[styles.statChip, dangerousSessions.length > 0 && styles.statChipWarn]}>
                  <Text style={[styles.statNum, { color: dangerousSessions.length > 0 ? C.red : C.primary }]}>
                    {dangerousSessions.length}
                  </Text>
                  <Text style={styles.statLbl}>Dangerous Sessions</Text>
                  <Text style={styles.statSub}>turnout &lt;80%</Text>
                </View>
              </View>

              {/* Sessions Attendance Chart */}
              <View style={styles.chartCard}>
                <View style={styles.cardHeaderWithBadge}>
                  <View style={styles.flex}>
                    <Text style={styles.chartTitle}>Class Attendance Trend</Text>
                    <Text style={styles.chartSubtitle}>
                      Sessions in red fall below the 80% attendance threshold
                    </Text>
                  </View>
                  <View style={styles.legendRow}>
                    <View style={styles.legendItem}>
                      <View style={[styles.legendBox, { backgroundColor: C.primary }]} />
                      <Text style={styles.legendText}>Normal (≥80%)</Text>
                    </View>
                    <View style={styles.legendItem}>
                      <View style={[styles.legendBox, { backgroundColor: C.red }]} />
                      <Text style={[styles.legendText, { color: C.red, fontWeight: '700' }]}>Dangerous (&lt;80%)</Text>
                    </View>
                  </View>
                </View>

                {sessions.length > 0 ? (
                  <>
                    <SessionBarChart
                      sessions={sessions}
                      enrolled={enrolled}
                      selectedSessionId={selectedSession?.session_id}
                      onSelectSession={s => setSelectedSession(s)}
                    />
                    <Text style={styles.chartFooterNote}>Tap any session bar to view attendance details below</Text>
                  </>
                ) : (
                  <Text style={styles.hintText}>No closed sessions recorded yet.</Text>
                )}

                {selectedSession && (
                  <View style={styles.selectedSessionCallout}>
                    <View style={styles.selectedSessionHeader}>
                      <Text style={styles.selectedSessionTitle}>{selectedSession.label} Overview</Text>
                      <Badge variant={(selectedSession.rate ?? 0) < 80 ? 'red' : 'green'} dot>
                        {(selectedSession.rate ?? 0) < 80 ? 'Dangerous Rate' : 'Normal'}
                      </Badge>
                    </View>
                    <View style={styles.selectedSessionStats}>
                      <Text style={styles.selectedSessionText}>
                        Present: <Text style={styles.bold}>{selectedSession.present_count} / {enrolled}</Text>
                      </Text>
                      <Text style={styles.selectedSessionText}>
                        Turnout: <Text style={[styles.bold, { color: (selectedSession.rate ?? 0) < 80 ? C.red : C.green }]}>
                          {selectedSession.rate ?? Math.round((selectedSession.present_count / enrolled) * 100)}%
                        </Text>
                      </Text>
                      <Text style={styles.selectedSessionText}>
                        Date: <Text style={styles.bold}>{selectedSession.date || '—'}</Text>
                      </Text>
                    </View>
                  </View>
                )}
              </View>

              {/* Early Warning / At Risk Students List (FR-707, FR-710) */}
              <View style={styles.chartCard}>
                <View style={styles.cardHeaderWithBadge}>
                  <View style={styles.flex}>
                    <Text style={styles.chartTitle}>Early Warning &amp; At-Risk Students</Text>
                    <Text style={styles.chartSubtitle}>
                      Students with attendance below 80% face automatic exam barring
                    </Text>
                  </View>
                  <Badge variant={atRisk.length > 0 ? 'red' : 'green'}>
                    {atRisk.length} flagged
                  </Badge>
                </View>

                {atRisk.length === 0 ? (
                  <View style={styles.emptyRisk}>
                    <Ionicons name="checkmark-circle-outline" size={24} color={C.green} />
                    <Text style={styles.emptyRiskText}>All students have healthy attendance above 80%</Text>
                  </View>
                ) : (
                  <View style={styles.riskList}>
                    {atRisk.map(r => (
                      <View key={r.student_id} style={styles.riskCardItem}>
                        <View style={styles.riskAvatar}>
                          <Text style={styles.riskAvatarText}>
                            {r.name.split(' ').map(w => w[0]).slice(0, 2).join('')}
                          </Text>
                        </View>
                        <View style={styles.riskDetails}>
                          <Text style={styles.riskName}>{r.name}</Text>
                          <Text style={styles.riskMatric}>
                            {r.matric_no || r.student_id} · {r.condition || 'Attendance < 80%'}
                          </Text>
                        </View>
                        <View style={styles.riskNumbers}>
                          <Text style={styles.riskFraction}>{r.present}/{r.total} sessions</Text>
                          <Text style={[styles.riskRate, { color: rateColor(r.rate) }]}>{r.rate}%</Text>
                        </View>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            </>
          )
        )}

        {/* ── TAB 3: CLASSROOM INTERACTION ── */}
        {tab === 'par' && (
          <>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.green }]}>82%</Text>
                <Text style={styles.statLbl}>Avg Participation Rate</Text>
                <Text style={styles.statSub}>active in-class</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>14</Text>
                <Text style={styles.statLbl}>Live Questions Asked</Text>
                <Text style={styles.statSub}>student questions</Text>
              </View>
            </View>

            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>8</Text>
                <Text style={styles.statLbl}>Polls Executed</Text>
                <Text style={styles.statSub}>100% closed</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.orangeDk }]}>3</Text>
                <Text style={styles.statLbl}>"Don't Understand" Alerts</Text>
                <Text style={styles.statSub}>addressed live</Text>
              </View>
            </View>

            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>In-Class Response Rate per Session</Text>
              <Text style={styles.chartSubtitle}>Proportion of enrolled students voting in polls and answering prompts</Text>
              <View style={{ height: 12 }} />
              <SessionBarChart
                sessions={sessions}
                enrolled={enrolled}
              />
            </View>

            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Student Interaction Highlights</Text>
              <View style={styles.insightBox}>
                <Ionicons name="bulb-outline" size={18} color={C.primary} />
                <Text style={styles.insightText}>
                  Poll participation peaked at 90% during Week 5 (Agile vs Waterfall debate).
                  Questions tagged with SOLID principles received the highest peer engagement.
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
                <Text style={[styles.statNum, { color: C.primary }]}>74%</Text>
                <Text style={styles.statLbl}>Class Average Score</Text>
                <Text style={styles.statSub}>across 3 quizzes</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.green }]}>+8%</Text>
                <Text style={styles.statLbl}>Performance Trend</Text>
                <Text style={styles.statSub}>improving over weeks</Text>
              </View>
            </View>

            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Class Average Score Progression</Text>
              <Text style={styles.chartSubtitle}>Mean percentage score across completed weekly quizzes</Text>
              <View style={{ marginTop: 12 }}>
                <Svg width="100%" height={90} viewBox="0 0 300 90">
                  <Polyline
                    points="10,75 60,60 110,50 160,55 210,38 270,30 290,34"
                    fill="none"
                    stroke={C.green}
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {[[10, 75], [60, 60], [110, 50], [160, 55], [210, 38], [270, 30], [290, 34]].map(([x, y], i) => (
                    <Circle key={i} cx={x} cy={y} r="3.5" fill={C.green} />
                  ))}
                </Svg>
                <Text style={styles.svgNote}>Average % score over semester (steady upward trajectory)</Text>
              </View>
            </View>

            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Topic Mastery Breakdown (FR-705)</Text>
              <View style={styles.topicBreakdownList}>
                <View style={styles.topicRow}>
                  <View style={styles.topicInfo}>
                    <Text style={styles.topicTitle}>Agile &amp; Scrum Framework</Text>
                    <Text style={styles.topicSub}>12 questions · Week 2–3</Text>
                  </View>
                  <Badge variant="green">88% Mastered</Badge>
                </View>
                <View style={styles.topicRow}>
                  <View style={styles.topicInfo}>
                    <Text style={styles.topicTitle}>SOLID Design Principles</Text>
                    <Text style={styles.topicSub}>10 questions · Week 4</Text>
                  </View>
                  <Badge variant="orange">72% Review Needed</Badge>
                </View>
                <View style={styles.topicRow}>
                  <View style={styles.topicInfo}>
                    <Text style={styles.topicTitle}>Java OOP &amp; Interfaces</Text>
                    <Text style={styles.topicSub}>8 questions · Week 5</Text>
                  </View>
                  <Badge variant="green">81% Mastered</Badge>
                </View>
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
  flex: { flex: 1},
  exportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    gap: 4,
  },
  exportBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
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
    fontSize: 12,
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
    marginHorizontal: 16,
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
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  kpiItem: {
    alignItems: 'center',
    flex: 1,
  },
  kpiBorder: {
    width: 1,
    height: 34,
    backgroundColor: C.border,
  },
  kpiNum: {
    fontSize: 18,
    fontWeight: '800',
  },
  kpiLbl: {
    fontSize: 10,
    fontWeight: '700',
    color: C.text,
    marginTop: 2,
    textAlign: 'center',
  },
  kpiSub: {
    fontSize: 9,
    color: C.textSub,
    marginTop: 1,
    textAlign: 'center',
  },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    borderWidth: 1,
    borderColor: '#FECACA',
    borderRadius: 10,
    padding: 12,
    marginHorizontal: 16,
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
    paddingHorizontal: 16,
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
    marginHorizontal: 16,
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
    paddingHorizontal: 16,
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
  statChipDanger: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FECACA',
  },
  statChipWarn: {
    backgroundColor: '#FFFBEB',
    borderColor: '#FDE68A',
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
    marginHorizontal: 16,
    marginTop: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  cardHeaderWithBadge: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  chartTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
  },
  chartSubtitle: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 2,
  },
  legendRow: {
    flexDirection: 'row',
    gap: 10,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  legendBox: {
    width: 8,
    height: 8,
    borderRadius: 2,
  },
  legendText: {
    fontSize: 10,
    color: C.textSub,
  },
  chartFooterNote: {
    fontSize: 10,
    color: C.textHint,
    textAlign: 'center',
    marginTop: 6,
  },
  selectedSessionCallout: {
    marginTop: 12,
    padding: 10,
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
  },
  selectedSessionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  selectedSessionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: C.text,
  },
  selectedSessionStats: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  selectedSessionText: {
    fontSize: 11,
    color: C.textSub,
  },
  bold: {
    fontWeight: '700',
    color: C.text,
  },
  emptyRisk: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 14,
    justifyContent: 'center',
  },
  emptyRiskText: {
    fontSize: 13,
    color: C.green,
    fontWeight: '600',
  },
  riskList: {
    gap: 8,
    marginTop: 6,
  },
  riskCardItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
    paddingHorizontal: 8,
    backgroundColor: '#FEF2F2',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  riskAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#FEE2E2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  riskAvatarText: {
    fontSize: 12,
    fontWeight: '700',
    color: C.red,
  },
  riskDetails: {
    flex: 1,
  },
  riskName: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
  },
  riskMatric: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 1,
  },
  riskNumbers: {
    alignItems: 'flex-end',
  },
  riskFraction: {
    fontSize: 11,
    color: C.textSub,
  },
  riskRate: {
    fontSize: 14,
    fontWeight: '800',
  },
  insightBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    padding: 10,
    backgroundColor: C.blueLt,
    borderRadius: 8,
    marginTop: 8,
  },
  insightText: {
    flex: 1,
    fontSize: 12,
    color: C.primary,
    lineHeight: 18,
  },
  topicBreakdownList: {
    gap: 10,
    marginTop: 8,
  },
  topicRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  topicInfo: {
    flex: 1,
  },
  topicTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
  },
  topicSub: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 1,
  },
  centered: {
    alignItems: 'center',
    padding: 40,
  },
  hintText: {
    fontSize: 13,
    color: C.textHint,
    textAlign: 'center',
    marginVertical: 12,
  },
  svgNote: {
    fontSize: 11,
    color: C.textHint,
    textAlign: 'center',
    marginTop: 4,
  },
})
