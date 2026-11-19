import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import Svg, { Polyline, Circle, Rect } from 'react-native-svg'
import { useLecturer } from '../context/LecturerContext'
import { getAnalyticsEngagement, getAssessmentByTopic, exportAnalyticsCsv } from '../services/api'
import Topbar from '../components/Topbar'
import { C } from '../theme'

const TABS = [['att', 'Attendance'], ['par', 'Participation'], ['quiz', 'Quiz'], ['stu', 'Students']]

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getDateParams(range) {
  const now = new Date()
  const d = new Date(now)
  if (range === 'month') d.setDate(now.getDate() - 30)
  else if (range === 'week') d.setDate(now.getDate() - 7)
  else d.setMonth(now.getMonth() - 6)
  const pad = n => String(n).padStart(2, '0')
  const fmt = x => `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}`
  return { from_date: fmt(d), to_date: fmt(now) }
}

function rateColor(rate) {
  if (rate == null) return C.textHint
  if (rate >= 80) return C.green
  if (rate >= 60) return C.orange
  return C.red
}

function rateLabel(rate) {
  if (rate == null) return 'No data'
  if (rate >= 80) return 'Good'
  if (rate >= 60) return 'Watch'
  return 'At risk'
}

function Dropdown({ value, items, onChange }) {
  const [open, setOpen] = useState(false)
  const current = items.find(i => i.value === value)
  return (
    <View style={styles.ddWrap}>
      <TouchableOpacity style={styles.ddBtn} onPress={() => setOpen(o => !o)} activeOpacity={0.7}>
        <Text style={styles.ddText} numberOfLines={1}>{current?.label ?? 'Select…'}</Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={14} color={C.textSub} />
      </TouchableOpacity>
      {open && (
        <View style={styles.ddMenu}>
          {items.map(i => (
            <TouchableOpacity
              key={i.value}
              style={[styles.ddItem, i.value === value && styles.ddItemActive]}
              onPress={() => { setOpen(false); onChange(i.value) }}
            >
              <Text style={[styles.ddItemText, i.value === value && styles.ddItemTextActive]} numberOfLines={1}>
                {i.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  )
}

// ─── Visual components ────────────────────────────────────────────────────────

// Donut progress ring (0–100), value shown in the middle.
function Ring({ value, color, size = 96, stroke = 10, caption }) {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, value ?? 0))
  return (
    <View style={{ alignItems: 'center' }}>
      <Svg width={size} height={size}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={C.gray100} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2} cy={size / 2} r={r}
          stroke={color} strokeWidth={stroke} fill="none"
          strokeDasharray={`${(pct / 100) * circ} ${circ}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <Circle cx={size / 2} cy={size / 2} r={r - stroke - 3} fill={C.card} />
      </Svg>
      <View style={styles.ringCenter} pointerEvents="none">
        <Text style={[styles.ringValue, { color: color ?? C.text }]}>{value != null ? `${Math.round(value)}%` : '—'}</Text>
        {caption ? <Text style={styles.ringCaption}>{caption}</Text> : null}
      </View>
    </View>
  )
}

// Small tinted insight card: icon + big number + caption.
function InsightCard({ icon, bg, color, value, label }) {
  return (
    <View style={[styles.insightCard, { backgroundColor: bg }]}>
      <Ionicons name={icon} size={16} color={color} />
      <Text style={[styles.insightValue, { color }]}>{value}</Text>
      <Text style={[styles.insightLabel, { color }]}>{label}</Text>
    </View>
  )
}

// Stat tile for the hero's 2×2 grid.
function StatTile({ value, label, alert }) {
  return (
    <View style={[styles.statTile, alert && styles.statTileAlert]}>
      <Text style={[styles.statTileNum, alert && { color: C.red }]}>{value}</Text>
      <Text style={[styles.statTileLbl, alert && { color: C.red }]}>{label}</Text>
    </View>
  )
}

// Hero card: ring on the left, message + 2×2 stat grid filling the rest.
function Hero({ value, title, message, tiles, ringColor }) {
  return (
    <View style={styles.heroCard}>
      <View style={styles.heroLeft}>
        <Ring value={value} color={ringColor} caption={title} />
      </View>
      <View style={styles.heroRight}>
        <Text style={styles.heroMsg}>{message}</Text>
        <View style={styles.heroGrid}>
          {tiles.map(t => <StatTile key={t.label} {...t} />)}
        </View>
      </View>
    </View>
  )
}

// Colored rate pill, e.g. "84% · Good".
function RatePill({ rate }) {
  const color = rateColor(rate)
  return (
    <View style={[styles.ratePill, { backgroundColor: color + '1A' }]}>
      <Text style={[styles.ratePillText, { color }]}>
        {rate != null ? `${Math.round(rate)}%` : '—'} · {rateLabel(rate)}
      </Text>
    </View>
  )
}

// Session bars: attended (present+late per FR-308) with the late part in orange.
function SessionBars({ sessions, enrolled, color }) {
  if (!sessions.length) return null
  const bars = sessions.map(s => ({
    attended: s.present_count + (s.late_count ?? 0),
    late: s.late_count ?? 0,
    total: s.total,
    label: s.label.replace('Week ', 'W'),
    date: s.date,
  }))
  const H = 120
  return (
    <View style={styles.barsWrap}>
      {bars.map((b, i) => {
        const hAtt = Math.max(6, Math.round((b.attended / (b.total || enrolled || 1)) * H))
        const hLate = Math.max(0, Math.round((b.late / (b.total || enrolled || 1)) * H))
        const hLatePart = Math.min(hLate, hAtt)
        return (
          <View key={i} style={styles.barCol}>
            <Text style={styles.barVal}>{b.attended}/{b.total}</Text>
            <View style={styles.barTrack}>
              <View style={[styles.barFill, { height: hAtt, backgroundColor: color }]} />
              {b.late > 0 && (
                <View style={[styles.barLate, { height: hLatePart }]} />
              )}
            </View>
            <Text style={styles.barLabel}>{b.label}</Text>
          </View>
        )
      })}
    </View>
  )
}

// Horizontal score bar for topics / per-student rates.
function ScoreBar({ label, right, score, color }) {
  const pct = Math.max(0, Math.min(100, score ?? 0))
  return (
    <View style={styles.scoreRow}>
      <Text style={styles.scoreLabel} numberOfLines={1}>{label}</Text>
      <View style={styles.scoreTrack}>
        <View style={[styles.scoreFill, { width: `${pct}%`, backgroundColor: color }]} />
      </View>
      <Text style={[styles.scoreValue, { color }]}>{right}</Text>
    </View>
  )
}

// Group dated sessions into Monday-start weeks: [{key, attended, total, rate}].
function weekBuckets(sessions, denominator) {
  const map = new Map()
  for (const s of sessions) {
    const d = s.date ? new Date(`${s.date}T00:00:00`) : null
    if (!d || isNaN(d)) continue
    const monday = new Date(d)
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7))
    const key = `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, '0')}-${String(monday.getDate()).padStart(2, '0')}`
    const e = map.get(key) || { attended: 0, total: 0, sessions: 0 }
    e.attended += s.present_count + (s.late_count ?? 0)
    e.sessions += 1
    if (s.total != null) e.total = Math.max(e.total, s.total)
    map.set(key, e)
  }
  return [...map.entries()].sort().map(([key, e], i) => ({
    key,
    idx: i + 1,
    date: key,
    rate: e.total ? (e.attended / e.total) * 100 : null,
    attended: e.attended,
    sessions: e.sessions,
    denominator,
  }))
}

// Per-week rate bars with a date line under each column.
function WeekBars({ buckets, color }) {
  if (buckets.length < 2) return null
  return (
    <View style={styles.barsWrap}>
      {buckets.map(b => (
        <View key={b.key} style={styles.barCol}>
          <Text style={styles.barVal}>{Math.round(b.rate ?? 0)}%</Text>
          <View style={styles.barTrack}>
            <View style={[styles.barFill, {
              height: Math.max(6, Math.round((b.rate ?? 0) / 100 * 120)),
              backgroundColor: color,
            }]} />
          </View>
          <Text style={styles.barLabel}>W{b.idx}</Text>
          <Text style={styles.barDate}>{b.date.slice(5)}</Text>
        </View>
      ))}
    </View>
  )
}

// Class quiz trend as a line with dots and end labels.
function TrendGraph({ entries, color }) {
  const scored = entries.filter(e => e.average_score != null)
  const W = 300
  const H = 120
  if (!scored.length) return <Text style={styles.hintText}>No graded quizzes yet.</Text>
  const x = i => (scored.length === 1 ? W / 2 : 24 + i * ((W - 48) / (scored.length - 1)))
  const y = score => H - 16 - (score / 100) * (H - 28)
  const pts = scored.map((e, i) => `${x(i)},${y(e.average_score)}`).join(' ')
  return (
    <View>
      <Svg width={W} height={H}>
        {/* 80% and 50% reference lines */}
        <Rect x={0} y={y(80)} width={W} height={1} fill={C.gray300} />
        <Rect x={0} y={y(50)} width={W} height={1} fill={C.redLt} />
        <Polyline points={pts} fill="none" stroke={color} strokeWidth={2.5} />
        {scored.map((e, i) => (
          <Circle key={i} cx={x(i)} cy={y(e.average_score)} r={4.5} fill={color} stroke="#fff" strokeWidth={1.5} />
        ))}
      </Svg>
      <View style={styles.trendLabels}>
        {scored.map(e => (
          <Text key={e.quiz_id} style={styles.trendLabel} numberOfLines={1}>
            {e.title.length > 12 ? `${e.title.slice(0, 11)}…` : e.title}
          </Text>
        ))}
      </View>
      <View style={styles.trendScores}>
        {scored.map(e => (
          <Text key={e.quiz_id} style={[styles.trendScore, { color: rateColor(e.average_score) }]}>
            {Math.round(e.average_score)}%
          </Text>
        ))}
      </View>
    </View>
  )
}

// One at-risk student row: name, fraction, mini bar, rate pill.
function RiskRow({ name, fraction, rate, unit }) {
  const color = rateColor(rate)
  return (
    <View style={styles.riskRow}>
      <View style={[styles.riskDot, { backgroundColor: color }]} />
      <View style={styles.riskMain}>
        <View style={styles.riskTop}>
          <Text style={styles.riskName} numberOfLines={1}>{name}</Text>
          <Text style={styles.riskFraction}>{fraction}{unit ?? ''}</Text>
          <RatePill rate={rate} />
        </View>
        <View style={styles.riskTrack}>
          <View style={[styles.riskFill, { width: `${Math.max(0, Math.min(100, rate ?? 0))}%`, backgroundColor: color }]} />
        </View>
      </View>
    </View>
  )
}

export default function Analytics({ navigation }) {
  const { state, openModal, loadAnalytics, loadAllClasses, showToast } = useLecturer()
  const { allClasses, analytics, analyticsLoading } = state
  const [tab, setTab] = useState('att')
  const [selectedOccId, setSelectedOccId] = useState(null)
  const [timeRange, setTimeRange] = useState('semester')
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    if (!allClasses.length) loadAllClasses()
  }, [])

  useEffect(() => {
    if (allClasses.length && !selectedOccId) setSelectedOccId(allClasses[0].id)
  }, [allClasses])

  useEffect(() => {
    if (selectedOccId) loadAnalytics(selectedOccId, getDateParams(timeRange))
  }, [selectedOccId, timeRange])

  useFocusEffect(useCallback(() => {
    if (selectedOccId) loadAnalytics(selectedOccId, getDateParams(timeRange))
  }, [selectedOccId, timeRange, loadAnalytics]))

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([
      loadAllClasses(),
      selectedOccId ? loadAnalytics(selectedOccId, getDateParams(timeRange)) : Promise.resolve(),
    ])
    setRefreshing(false)
  }, [loadAllClasses, loadAnalytics, selectedOccId, timeRange])

  // Students tab (S41/FR-701–703): per-student engagement indicators.
  const [engagement, setEngagement] = useState([])
  const [engagementLoading, setEngagementLoading] = useState(false)
  // Quiz tab extra (S42/FR-705): assessment performance by quiz topic.
  const [topics, setTopics] = useState([])

  useEffect(() => {
    let dead = false
    if (!selectedOccId) return
    setEngagementLoading(true)
    Promise.all([
      getAnalyticsEngagement(selectedOccId).catch(() => []),
      getAssessmentByTopic(selectedOccId).catch(() => []),
    ]).then(([stu, byTopic]) => {
      if (dead) return
      setEngagement(stu)
      setTopics(byTopic)
      setEngagementLoading(false)
    })
    return () => { dead = true }
  }, [selectedOccId, timeRange])

  const selectedClass = allClasses.find(c => c.id === selectedOccId)
  const sessions = analytics?.sessions ?? []
  const enrolled = analytics?.enrolled_count ?? 0

  // ── Attendance insights (from real session data) ──
  const atRisk = analytics?.at_risk_students ?? []
  const avgRate = analytics?.avg_attendance_rate
  const totalLate = sessions.reduce((s, x) => s + (x.late_count ?? 0), 0)
  const bestSession = sessions.reduce((b, s) => {
    const attended = s.present_count + (s.late_count ?? 0)
    return !b || attended > (b.present_count + (b.late_count ?? 0)) ? s : b
  }, null)

  // ── Participation insights ──
  const parBars = analytics?.participation_bars ?? []
  const parAtRisk = analytics?.participation_at_risk ?? []
  const parAvg = analytics?.avg_participation_rate ?? 0
  const parHeld = analytics?.interaction_sessions_held ?? 0
  const bestPar = parBars.reduce((b, x) => (!b || x.participants > b.participants ? x : b), null)

  // ── Quiz insights ──
  const quizTrend = analytics?.quiz_trend ?? []
  const quizAtRisk = analytics?.quiz_at_risk ?? []
  const avgQuiz = analytics?.avg_quiz_score
  const gradedQuizzes = quizTrend.filter(e => e.average_score != null)
  const scoreDelta = gradedQuizzes.length >= 2
    ? gradedQuizzes[gradedQuizzes.length - 1].average_score - gradedQuizzes[0].average_score
    : null
  const hardestTopic = topics.reduce((b, t) => (!b || t.average_score < b.average_score ? t : b), null)
  const topicsShown = [...topics].sort((a, b) => b.average_score - a.average_score)

  // Weekly trend buckets (semester/month views): attendance from session rows,
  // participation from the per-session participant counts.
  const weeklyAttendance = weekBuckets(sessions)
  const weeklyParticipation = weekBuckets(
    parBars.map(b => ({
      date: b.date, present_count: b.participants, late_count: 0, total: enrolled,
    })),
  )

  const loading = analyticsLoading

  return (
    <View style={styles.flex}>
      <Topbar
        title="Analytics & Reports"
        sub={selectedClass ? `${selectedClass.code} — ${selectedClass.name}` : undefined}
        right={
          <TouchableOpacity
            style={styles.exportBtn}
            onPress={async () => {
              if (!selectedOccId || !analytics) return
              const rangeLabel = timeRange === 'semester' ? 'This semester'
                               : timeRange === 'month' ? 'This month'
                               : 'This week'
              if (tab === 'att') {
                openModal('export', {
                  scope: 'occurrence',
                  id: selectedOccId,
                  filename: `attendance_report_${selectedClass?.code ?? 'report'}_${new Date().getFullYear()}.csv`,
                  dateParams: getDateParams(timeRange),
                  subtitle: `${selectedClass?.code ?? ''} · ${rangeLabel}`,
                  sessionCount: analytics.sessions_held,
                  studentCount: analytics.enrolled_count,
                })
                return
              }
              try {
                setExporting(true)
                const msg = await exportAnalyticsCsv(
                  tab === 'stu' ? 'students' : tab,
                  selectedOccId,
                  `${tab}_report_${selectedClass?.code ?? 'report'}_${new Date().getFullYear()}.csv`,
                  getDateParams(timeRange),
                )
                showToast(msg || 'Report exported', 'success')
              } catch (e) {
                showToast(e.message || 'Export failed', 'error')
              } finally {
                setExporting(false)
              }
            }}
          >
            <Ionicons name="download-outline" size={14} color="#fff" />
            <Text style={styles.exportBtnText}>{exporting ? 'Saving…' : 'Export'}</Text>
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

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* ── Attendance tab ── */}
        {tab === 'att' && (
          loading ? (
            <View style={styles.centered}><Text style={styles.hintText}>Loading…</Text></View>
          ) : !analytics ? (
            <View style={styles.centered}><Text style={styles.hintText}>No data available</Text></View>
          ) : (
            <>
              <Hero
                value={avgRate}
                ringColor={rateColor(avgRate)}
                title="Attendance"
                message={
                  avgRate == null ? 'No closed sessions yet.'
                    : avgRate >= 80 ? 'Attendance is healthy — keep it up.'
                    : avgRate >= 60 ? 'Attendance is slipping — nudge the class.'
                    : 'Low attendance — consider a check-in.'
                }
                tiles={[
                  { value: analytics.sessions_held, label: 'Sessions held' },
                  { value: enrolled, label: 'Enrolled' },
                  { value: totalLate, label: 'Late arrivals' },
                  { value: atRisk.length, label: 'At risk (<80%)', alert: atRisk.length > 0 },
                ]}
              />

              {sessions.length > 0 && (
                <>
                  <View style={styles.insightRow}>
                    <InsightCard
                      icon="trophy-outline" bg={C.greenLt} color={C.greenDk}
                      value={bestSession ? `${bestSession.present_count + (bestSession.late_count ?? 0)}/${bestSession.total}` : '—'}
                      label={bestSession ? `Best session · ${bestSession.label.replace('Week ', 'W')}` : 'No sessions'}
                    />
                    <InsightCard
                      icon="time-outline" bg={C.orangeLt} color={C.orangeDk}
                      value={totalLate} label="Late arrivals"
                    />
                  </View>
                  <View style={styles.chartCard}>
                    <Text style={styles.chartTitle}>Attendance per session</Text>
                    <Text style={styles.chartHint}>Blue = present · Orange = late (counts as attended)</Text>
                    <SessionBars sessions={sessions} enrolled={enrolled} color={C.primary} />
                  </View>
                  {timeRange !== 'week' && weeklyAttendance.length >= 2 && (
                    <View style={styles.chartCard}>
                      <Text style={styles.chartTitle}>Weekly attendance trend</Text>
                      <Text style={styles.chartHint}>Average rate across each calendar week</Text>
                      <WeekBars buckets={weeklyAttendance} color={C.primary} />
                    </View>
                  )}
                </>
              )}

              <View style={styles.chartCard}>
                <Text style={styles.chartTitle}>Students at risk (&lt;80% attendance)</Text>
                {atRisk.length === 0 ? (
                  <View style={styles.allGood}>
                    <Ionicons name="checkmark-circle" size={18} color={C.green} />
                    <Text style={[styles.hintText, { color: C.green }]}>Everyone is above 80%.</Text>
                  </View>
                ) : (
                  <View style={styles.riskList}>
                    {atRisk.map(r => (
                      <RiskRow key={r.student_id} name={`${r.name} (${r.matric_no})`} fraction={`${r.present}/${r.total}`} rate={r.rate} />
                    ))}
                  </View>
                )}
              </View>
            </>
          )
        )}

        {/* ── Participation tab ── */}
        {tab === 'par' && (
          loading ? (
            <View style={styles.centered}><Text style={styles.hintText}>Loading…</Text></View>
          ) : !analytics ? (
            <View style={styles.centered}><Text style={styles.hintText}>No data available</Text></View>
          ) : (
            <>
              <Hero
                value={parAvg}
                ringColor={C.green}
                title="Participation"
                message={
                  parHeld === 0
                    ? 'No interaction sessions held yet.'
                    : parAvg >= 80 ? 'The class is engaging actively.' : 'Engagement is below target.'
                }
                tiles={[
                  { value: parHeld, label: 'Live sessions' },
                  { value: parBars.length ? Math.round(parBars.reduce((s, x) => s + x.participants, 0) / parBars.length) : 0, label: 'Avg participants' },
                  { value: enrolled, label: 'Enrolled' },
                  { value: parAtRisk.length, label: 'Quiet (<80%)', alert: parAtRisk.length > 0 },
                ]}
              />

              {parBars.length > 0 && (
                <>
                  <View style={styles.insightRow}>
                    <InsightCard
                      icon="people-outline" bg={C.blueLt} color={C.blueDk}
                      value={bestPar ? `${bestPar.participants}/${enrolled}` : '—'}
                      label={bestPar ? `Best turnout · ${bestPar.label.replace('Week ', 'W')}` : 'No sessions'}
                    />
                  </View>
                  <View style={styles.chartCard}>
                    <Text style={styles.chartTitle}>Participants per interaction session</Text>
                    <SessionBars sessions={parBars.map(b => ({
                      present_count: b.participants, late_count: 0, total: enrolled, label: b.label, date: b.date,
                    }))} enrolled={enrolled} color={C.green} />
                  </View>
                  {timeRange !== 'week' && weeklyParticipation.length >= 2 && (
                    <View style={styles.chartCard}>
                      <Text style={styles.chartTitle}>Weekly participation trend</Text>
                      <Text style={styles.chartHint}>Average participants per session in each calendar week</Text>
                      <WeekBars buckets={weeklyParticipation} color={C.green} />
                    </View>
                  )}
                </>
              )}

              <View style={styles.chartCard}>
                <Text style={styles.chartTitle}>Quiet students (&lt;80% participation)</Text>
                {parAtRisk.length === 0 ? (
                  <View style={styles.allGood}>
                    <Ionicons name="checkmark-circle" size={18} color={C.green} />
                    <Text style={[styles.hintText, { color: C.green }]}>Everyone participates above 80%.</Text>
                  </View>
                ) : (
                  <View style={styles.riskList}>
                    {parAtRisk.map(r => (
                      <RiskRow key={r.student_id} name={`${r.name} (${r.matric_no})`} fraction={`${r.present}/${r.total}`} rate={r.rate} />
                    ))}
                  </View>
                )}
              </View>
            </>
          )
        )}

        {/* ── Quiz tab ── */}
        {tab === 'quiz' && (
          loading ? (
            <View style={styles.centered}><Text style={styles.hintText}>Loading…</Text></View>
          ) : !analytics ? (
            <View style={styles.centered}><Text style={styles.hintText}>No data available</Text></View>
          ) : (
            <>
              <Hero
                value={avgQuiz}
                ringColor={rateColor(avgQuiz)}
                title="Quiz average"
                message={
                  avgQuiz == null ? 'No graded quizzes yet.'
                    : scoreDelta == null ? 'One graded quiz so far — publish more to see a trend.'
                    : scoreDelta >= 0
                      ? `Scores improved ${Math.round(scoreDelta)} points since the first quiz.`
                      : `Scores dropped ${Math.abs(Math.round(scoreDelta))} points since the first quiz.`
                }
                tiles={[
                  { value: analytics.quiz_count ?? 0, label: 'Quizzes' },
                  { value: gradedQuizzes.length, label: 'Graded' },
                  { value: topics.length, label: 'Topics' },
                  { value: quizAtRisk.length, label: 'Low score (<50%)', alert: quizAtRisk.length > 0 },
                ]}
              />

              {gradedQuizzes.length > 0 && (
                <View style={styles.chartCard}>
                  <Text style={styles.chartTitle}>Class average per quiz</Text>
                  <TrendGraph entries={quizTrend} color={C.primary} />
                </View>
              )}

              {topics.length > 0 && (
                <View style={styles.chartCard}>
                  <Text style={styles.chartTitle}>Assessment by topic</Text>
                  <Text style={styles.chartHint}>Weakest topic: {hardestTopic ? hardestTopic.topic : '—'}</Text>
                  {topicsShown.map(t => (
                    <ScoreBar
                      key={t.topic}
                      label={t.topic}
                      right={`${Math.round(t.average_score)}%`}
                      score={t.average_score}
                      color={rateColor(t.average_score)}
                    />
                  ))}
                </View>
              )}

              <View style={styles.chartCard}>
                <Text style={styles.chartTitle}>Students at risk (&lt;50% avg score)</Text>
                {quizAtRisk.length === 0 ? (
                  <View style={styles.allGood}>
                    <Ionicons name="checkmark-circle" size={18} color={C.green} />
                    <Text style={[styles.hintText, { color: C.green }]}>No low scores.</Text>
                  </View>
                ) : (
                  <View style={styles.riskList}>
                    {quizAtRisk.map(r => (
                      <RiskRow
                        key={r.student_id}
                        name={`${r.name} (${r.matric_no})`}
                        fraction={`${r.quiz_count} quizzes`}
                        rate={r.average_score}
                      />
                    ))}
                  </View>
                )}
              </View>
            </>
          )
        )}

        {/* ── Students tab (S41 engagement indicators) ── */}
        {tab === 'stu' && (
          engagementLoading ? (
            <View style={styles.centered}><Text style={styles.hintText}>Loading…</Text></View>
          ) : engagement.length === 0 ? (
            <View style={styles.centered}><Text style={styles.hintText}>No enrolled students.</Text></View>
          ) : (
            engagement.map(s => {
              const att = s.attendance ?? {}
              const par = s.participation ?? {}
              const qz = s.quizzes ?? {}
              return (
                <View key={s.student_id} style={styles.stuCard}>
                  <View style={styles.stuHead}>
                    <View style={styles.stuAvatar}>
                      <Text style={styles.stuAvatarText}>
                        {(s.student_name ?? '?').split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()}
                      </Text>
                    </View>
                    <View style={styles.stuNameWrap}>
                      <Text style={styles.stuName}>{s.student_name ?? `Student ${s.student_id}`}</Text>
                      <Text style={styles.stuMatric}>{s.matric_no ?? ''}</Text>
                    </View>
                    <RatePill rate={att.rate} />
                  </View>
                  <View style={styles.stuMetrics}>
                    <ScoreBar label="Attendance" right={att.rate != null ? `${Math.round(att.rate)}%` : '—'} score={att.rate} color={rateColor(att.rate)} />
                    <ScoreBar label="Quiz average" right={qz.average_score != null ? `${Math.round(qz.average_score)}%` : '—'} score={qz.average_score} color={rateColor(qz.average_score)} />
                  </View>
                  <View style={styles.stuActions}>
                    <Text style={styles.stuActionChip}>Questions {par.questions ?? 0}</Text>
                    <Text style={styles.stuActionChip}>Votes {par.votes ?? 0}</Text>
                    <Text style={styles.stuActionChip}>Reactions {par.reactions ?? 0}</Text>
                    <Text style={styles.stuActionChip}>IDU {par.idu_signals ?? 0}</Text>
                  </View>
                </View>
              )
            })
          )
        )}

        <View style={{ height: 20 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  exportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    gap: 4,
  },
  exportBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
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
  tabActive: { borderBottomColor: C.primary },
  tabText: { fontSize: 14, fontWeight: '600', color: C.textSub },
  tabTextActive: { color: C.primary },
  pickerRow: {
    flexDirection: 'row',
    padding: 10,
    gap: 8,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  ddWrap: {
    flex: 1,
    position: 'relative',
    // Web: later siblings (the ScrollView) otherwise paint over the open menu.
    zIndex: 30,
    elevation: 30,
  },
  ddBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
    backgroundColor: C.gray50,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  ddText: { fontSize: 12, fontWeight: '600', color: C.text, flex: 1 },
  ddMenu: {
    marginTop: 4,
    backgroundColor: C.card,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: C.border,
    zIndex: 30,
    elevation: 30,
    maxHeight: 220,
  },
  ddItem: { paddingHorizontal: 10, paddingVertical: 8 },
  ddItemActive: { backgroundColor: C.blueLt },
  ddItemText: { fontSize: 12, color: C.text },
  ddItemTextActive: { color: C.primary, fontWeight: '700' },
  // Hero insight card (ring + summary)
  heroCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    backgroundColor: C.card,
    margin: 16,
    marginBottom: 8,
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  heroLeft: { alignItems: 'center' },
  heroRight: { flex: 1, gap: 10 },
  heroMsg: { fontSize: 13, color: C.textSub, lineHeight: 18 },
  heroGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  statTile: {
    flexBasis: '46%',
    flexGrow: 1,
    backgroundColor: C.gray50,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
  },
  statTileAlert: { backgroundColor: C.redLt, borderColor: C.redLt },
  statTileNum: { fontSize: 16, fontWeight: '800', color: C.text },
  statTileLbl: { fontSize: 10, color: C.textSub, marginTop: 1 },
  // Insight cards row
  insightRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 8,
    gap: 10,
  },
  insightCard: {
    flex: 1,
    borderRadius: 12,
    padding: 12,
    gap: 2,
  },
  insightValue: { fontSize: 18, fontWeight: '800' },
  insightLabel: { fontSize: 10, fontWeight: '600', opacity: 0.9 },
  // Chart cards
  chartCard: {
    backgroundColor: C.card,
    borderRadius: 14,
    margin: 16,
    marginTop: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  chartTitle: { fontSize: 13, fontWeight: '700', color: C.text, marginBottom: 2 },
  chartHint: { fontSize: 11, color: C.textHint, marginBottom: 10 },
  // Session bars
  barsWrap: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingTop: 6,
  },
  barCol: { flex: 1, alignItems: 'center' },
  barVal: { fontSize: 9, fontWeight: '700', color: C.textSub, marginBottom: 3 },
  barTrack: {
    width: '100%',
    maxWidth: 34,
    height: 120,
    backgroundColor: C.gray100,
    borderRadius: 6,
    justifyContent: 'flex-end',
    overflow: 'hidden',
  },
  barFill: { width: '100%' },
  barLate: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: C.orange,
    opacity: 0.85,
  },
  barLabel: { fontSize: 10, color: C.textHint, marginTop: 4 },
  barDate: { fontSize: 8, color: C.textHint },
  // Horizontal score bars
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 5,
  },
  scoreLabel: { flex: 1, fontSize: 12, color: C.textSub },
  scoreTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: C.gray100,
    overflow: 'hidden',
  },
  scoreFill: { height: '100%', borderRadius: 4 },
  scoreValue: { fontSize: 12, fontWeight: '800', width: 38, textAlign: 'right' },
  // Trend graph labels
  trendLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
  },
  trendLabel: { fontSize: 9, color: C.textHint, flex: 1, textAlign: 'center' },
  trendScores: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
  },
  trendScore: { fontSize: 10, fontWeight: '800', flex: 1, textAlign: 'center' },
  // At-risk list
  riskList: { gap: 12 },
  riskRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  riskDot: { width: 8, height: 8, borderRadius: 4 },
  riskMain: { flex: 1 },
  riskTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  riskName: { flex: 1, fontSize: 13, fontWeight: '600', color: C.text },
  riskFraction: { fontSize: 11, color: C.textHint },
  riskTrack: {
    height: 5,
    borderRadius: 3,
    backgroundColor: C.gray100,
    overflow: 'hidden',
  },
  riskFill: { height: '100%', borderRadius: 3 },
  ratePill: {
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  ratePillText: { fontSize: 10, fontWeight: '800' },
  allGood: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 6,
  },
  centered: { alignItems: 'center', padding: 40 },
  hintText: { fontSize: 13, color: C.textHint, textAlign: 'center' },
  // Ring
  ringCenter: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ringValue: { fontSize: 18, fontWeight: '800' },
  ringCaption: { fontSize: 9, color: C.textHint, marginTop: 1 },
  // Students tab
  stuCard: {
    backgroundColor: C.card,
    borderRadius: 14,
    margin: 16,
    marginTop: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
  },
  stuHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  stuAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stuAvatarText: { fontSize: 13, fontWeight: '800', color: C.primary },
  stuNameWrap: { flex: 1 },
  stuName: { fontSize: 14, fontWeight: '700', color: C.text },
  stuMatric: { fontSize: 11, color: C.textHint },
  stuMetrics: { gap: 2, marginBottom: 8 },
  stuActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  stuActionChip: {
    fontSize: 11,
    fontWeight: '600',
    color: C.textSub,
    backgroundColor: C.gray50,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: C.border,
    overflow: 'hidden',
  },
})
