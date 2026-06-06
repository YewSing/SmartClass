import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Modal, FlatList, RefreshControl,
} from 'react-native'
import Svg, { Polyline, Circle, Line, Text as SvgText } from 'react-native-svg'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import { ANALYTICS_PAR_BARS, ANALYTICS_PAR_LABELS } from '../data/mockData'
import { C } from '../theme'

const MAX_H = 90
const TABS = [['att', 'Attendance'], ['par', 'Participation'], ['env', 'Environment']]

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
  return rate < 70 ? C.red : C.orange
}

// Simple bar chart using View-based bars
function BarChart({ heights, labels, color }) {
  const maxH = 90
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
  chart: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 110,
    gap: 4,
    paddingTop: 10,
  },
  col: {
    flex: 1,
    alignItems: 'center',
    gap: 4,
  },
  barTrack: {
    height: 90,
    justifyContent: 'flex-end',
    width: '100%',
  },
  bar: {
    borderRadius: 3,
    width: '100%',
    minHeight: 4,
  },
  barLabel: {
    fontSize: 8,
    color: C.textHint,
  },
})

export default function Analytics({ navigation }) {
  const { state, openModal, loadAnalytics, loadAllClasses } = useLecturer()
  const { allClasses, analytics, analyticsLoading } = state
  const [tab, setTab] = useState('att')
  const [selectedOccId, setSelectedOccId] = useState(null)
  const [timeRange, setTimeRange] = useState('semester')

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
  const enrolled = analytics?.enrolled_count || 1
  const barHeights = sessions.map(s => Math.round((s.present_count / enrolled) * MAX_H))
  const barLabels = sessions.map(s => s.label.replace('Week ', 'W'))

  return (
    <View style={styles.flex}>
      <Topbar
        title="Analytics & Reports"

        right={
          <TouchableOpacity
            style={[styles.exportBtn, tab !== 'att' && { opacity: 0.5 }]}
            onPress={() => {
              if (tab !== 'att' || !selectedOccId || !analytics) return
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
        {/* Attendance tab */}
        {tab === 'att' && (
          analyticsLoading ? (
            <View style={styles.centered}>
              <Text style={styles.hintText}>Loading…</Text>
            </View>
          ) : !analytics ? (
            <View style={styles.centered}>
              <Text style={styles.hintText}>No data available</Text>
            </View>
          ) : (
            <>
              <View style={styles.statGrid}>
                <View style={styles.statChip}>
                  <Text style={styles.statNum}>{analytics.avg_attendance_rate}%</Text>
                  <Text style={styles.statLbl}>Avg attendance rate</Text>
                </View>
                <View style={styles.statChip}>
                  <Text style={styles.statNum}>{analytics.sessions_held}</Text>
                  <Text style={styles.statLbl}>Sessions held</Text>
                </View>
              </View>
              <View style={styles.statGrid}>
                <View style={styles.statChip}>
                  <Text style={[styles.statNum, { color: C.red }]}>{atRisk.length}</Text>
                  <Text style={styles.statLbl}>Students at-risk (&lt;80%)</Text>
                </View>
                <View style={styles.statChip}>
                  <Text style={styles.statNum}>{analytics.enrolled_count}</Text>
                  <Text style={styles.statLbl}>Enrolled</Text>
                </View>
              </View>

              {sessions.length > 0 ? (
                <View style={styles.chartCard}>
                  <Text style={styles.chartTitle}>Attendance per Session (students present)</Text>
                  <BarChart heights={barHeights} labels={barLabels} color={C.primary} />
                </View>
              ) : (
                <View style={styles.chartCard}>
                  <Text style={styles.hintText}>No closed sessions yet.</Text>
                </View>
              )}

              <View style={styles.chartCard}>
                <Text style={styles.chartTitle}>Students at risk (&lt;80% attendance)</Text>
                {atRisk.length === 0 ? (
                  <Text style={styles.hintText}>No at-risk students.</Text>
                ) : (
                  <View style={styles.riskList}>
                    {atRisk.map(r => (
                      <View key={r.student_id} style={styles.riskRow}>
                        <Text style={styles.riskName}>{r.name}</Text>
                        <Text style={styles.riskFraction}>{r.present}/{r.total}</Text>
                        <Text style={[styles.riskRate, { color: rateColor(r.rate) }]}>{r.rate}%</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            </>
          )
        )}

        {/* Participation tab */}
        {tab === 'par' && (
          <>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>79%</Text>
                <Text style={styles.statLbl}>Avg response rate</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>68%</Text>
                <Text style={styles.statLbl}>Avg quiz score</Text>
              </View>
            </View>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>32</Text>
                <Text style={styles.statLbl}>Quizzes &amp; polls run</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={[styles.statNum, { color: C.green }]}>+8%</Text>
                <Text style={styles.statLbl}>Score trend vs last sem</Text>
              </View>
            </View>
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Response rate per session</Text>
              <BarChart heights={ANALYTICS_PAR_BARS} labels={ANALYTICS_PAR_LABELS} color={C.green} />
            </View>
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Average score trend</Text>
              <Svg width="100%" height={90} viewBox="0 0 300 90">
                <Polyline
                  points="10,75 60,60 110,50 160,55 210,38 270,30 290,34"
                  fill="none"
                  stroke={C.green}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {[[10,75],[60,60],[110,50],[160,55],[210,38],[270,30],[290,34]].map(([x,y],i) => (
                  <Circle key={i} cx={x} cy={y} r="3.5" fill={C.green} />
                ))}
              </Svg>
              <Text style={styles.svgNote}>Average % correct over weeks (↑ trend)</Text>
            </View>
          </>
        )}

        {/* Environment tab */}
        {tab === 'env' && (
          <>
            <View style={styles.statGrid}>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>25.8°C</Text>
                <Text style={styles.statLbl}>Avg temperature</Text>
              </View>
              <View style={styles.statChip}>
                <Text style={styles.statNum}>1180</Text>
                <Text style={styles.statLbl}>Avg CO₂ (ppm)</Text>
              </View>
            </View>
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>Temperature history (°C)</Text>
              <Svg width="100%" height={90} viewBox="0 0 300 90">
                <Polyline
                  points="10,55 60,50 110,58 160,44 210,52 270,46 290,42"
                  fill="none"
                  stroke={C.primary}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {[[10,55],[60,50],[110,58],[160,44],[210,52],[270,46],[290,42]].map(([x,y],i) => (
                  <Circle key={i} cx={x} cy={y} r="3.5" fill={C.primary} />
                ))}
              </Svg>
            </View>
            <View style={styles.chartCard}>
              <Text style={styles.chartTitle}>CO₂ history (ppm)</Text>
              <Svg width="100%" height={90} viewBox="0 0 300 90">
                <Line x1="10" y1="35" x2="290" y2="35" stroke="#f5c5c5" strokeWidth="1" strokeDasharray="4,3" />
                <SvgText x="210" y="31" fontSize="9" fill={C.red}>1500 ppm limit</SvgText>
                <Polyline
                  points="10,72 60,65 110,52 160,68 210,44 270,58 290,50"
                  fill="none"
                  stroke={C.red}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {[[10,72],[60,65],[110,52],[160,68],[210,44],[270,58],[290,50]].map(([x,y],i) => (
                  <Circle key={i} cx={x} cy={y} r="3.5" fill={C.red} />
                ))}
              </Svg>
            </View>
          </>
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
    fontSize: 14,
    fontWeight: '600',
    color: C.textSub,
  },
  tabTextActive: {
    color: C.primary,
  },
  pickerRow: {
    flexDirection: 'row',
    padding: 10,
    gap: 8,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
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
  statNum: {
    fontSize: 22,
    fontWeight: '800',
    color: C.text,
  },
  statLbl: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 2,
    textAlign: 'center',
  },
  chartCard: {
    backgroundColor: C.card,
    borderRadius: 12,
    margin: 16,
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
  riskList: {
    gap: 10,
  },
  riskRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  riskName: {
    flex: 1,
    fontSize: 13,
    color: C.text,
  },
  riskFraction: {
    fontSize: 12,
    color: C.textHint,
  },
  riskRate: {
    fontSize: 13,
    fontWeight: '700',
  },
  centered: {
    alignItems: 'center',
    padding: 40,
  },
  hintText: {
    fontSize: 13,
    color: C.textHint,
    textAlign: 'center',
  },
  svgNote: {
    fontSize: 11,
    color: C.textHint,
    textAlign: 'center',
    marginTop: 4,
  },
})
