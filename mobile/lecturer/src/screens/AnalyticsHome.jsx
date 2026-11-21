import { useState, useEffect, useCallback } from 'react'
import { View, Text, TouchableOpacity, StyleSheet, Modal, FlatList } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import ComingSoon from '../components/ComingSoon'
import * as api from '../services/api'
import { C } from '../theme'

// Analytics tab. Learning analytics (Module 7) are being rebuilt (plan-shino.md S02), so the tab
// shows the placeholder plus the attendance CSV export (Module 3), which works today.

const RANGES = [
  { label: 'This semester', value: 'semester' },
  { label: 'This month', value: 'month' },
  { label: 'This week', value: 'week' },
]

function dateParams(range) {
  const today = new Date()
  const pad = n => String(n).padStart(2, '0')
  const fmt = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  if (range === 'month') {
    return { from: fmt(new Date(today.getFullYear(), today.getMonth(), 1)), to: fmt(today) }
  }
  if (range === 'week') {
    const mon = new Date(today)
    mon.setDate(today.getDate() - ((today.getDay() + 6) % 7))
    return { from: fmt(mon), to: fmt(today) }
  }
  return {}
}

function Dropdown({ value, items, onChange }) {
  const [open, setOpen] = useState(false)
  const selected = items.find(i => i.value === value)
  return (
    <>
      <TouchableOpacity style={dd.box} onPress={() => setOpen(true)} activeOpacity={0.7}>
        <Text style={dd.label} numberOfLines={1}>{selected?.label ?? '—'}</Text>
        <Ionicons name="chevron-down" size={14} color={C.text} />
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <TouchableOpacity style={dd.overlay} onPress={() => setOpen(false)} activeOpacity={1}>
          <View style={dd.sheet}>
            <FlatList
              data={items}
              keyExtractor={i => String(i.value)}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[dd.option, item.value === value && dd.optionActive]}
                  onPress={() => { onChange(item.value); setOpen(false) }}
                >
                  <Text style={[dd.optionText, item.value === value && dd.optionTextActive]}>{item.label}</Text>
                </TouchableOpacity>
              )}
            />
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  )
}

export default function AnalyticsHome() {
  const { state, openModal, loadAllClasses, showToast } = useLecturer()
  const { allClasses } = state
  const [occId, setOccId] = useState(null)
  const [range, setRange] = useState('semester')
  const [report, setReport] = useState(null)   // { sessions, students } for the chosen class and range

  useEffect(() => { if (!allClasses.length) loadAllClasses() }, [])
  useEffect(() => { if (allClasses.length && !occId) setOccId(allClasses[0].id) }, [allClasses])

  const loadReport = useCallback(async () => {
    if (!occId) return
    setReport(null)
    try {
      const r = await api.getClassAttendanceReport(occId, dateParams(range))
      setReport({ sessions: r.sessions.length, students: r.students.length })
    } catch (e) { showToast?.(e.message, 'error') }
  }, [occId, range, showToast])
  useEffect(() => { loadReport() }, [loadReport])

  const cls = allClasses.find(c => c.id === occId)
  const onExport = () => {
    if (!occId || !report) return
    openModal('export', {
      scope: 'occurrence',
      id: occId,
      filename: `attendance_report_${cls?.code ?? 'report'}_${new Date().getFullYear()}.csv`,
      dateParams: dateParams(range),
      subtitle: `${cls?.code ?? ''} · ${RANGES.find(r => r.value === range).label}`,
      sessionCount: report.sessions,
      studentCount: report.students,
    })
  }

  return (
    <ComingSoon
      title="Analytics"
      icon="bar-chart-outline"
      message="Learning analytics are being rebuilt. The attendance report below still works."
      right={
        <TouchableOpacity style={[styles.exportBtn, !report && styles.disabled]} onPress={onExport}>
          <Ionicons name="download-outline" size={14} color="#fff" />
          <Text style={styles.exportBtnText}>Export</Text>
        </TouchableOpacity>
      }
    >
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Attendance report</Text>
        <View style={styles.pickerRow}>
          <Dropdown
            value={occId}
            items={allClasses.map(c => ({ label: `${c.code} — ${c.name}`, value: c.id }))}
            onChange={setOccId}
          />
          <Dropdown value={range} items={RANGES} onChange={setRange} />
        </View>
        {report ? (
          <View style={styles.statRow}>
            <View style={styles.statChip}>
              <Text style={styles.statNum}>{report.sessions}</Text>
              <Text style={styles.statLbl}>Sessions held</Text>
            </View>
            <View style={styles.statChip}>
              <Text style={styles.statNum}>{report.students}</Text>
              <Text style={styles.statLbl}>Enrolled</Text>
            </View>
          </View>
        ) : (
          <Text style={styles.hint}>{allClasses.length ? 'Loading…' : 'No classes yet.'}</Text>
        )}
      </View>
    </ComingSoon>
  )
}

const styles = StyleSheet.create({
  exportBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: C.primary, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6,
  },
  disabled: { opacity: 0.5 },
  exportBtnText: { fontSize: 13, fontWeight: '600', color: '#fff' },
  card: {
    backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, gap: 10,
  },
  cardTitle: { fontSize: 14, fontWeight: '600', color: C.text },
  pickerRow: { flexDirection: 'row', gap: 8 },
  statRow: { flexDirection: 'row', gap: 10 },
  statChip: {
    flex: 1, alignItems: 'center', padding: 12,
    borderRadius: 10, borderWidth: 1, borderColor: C.border, backgroundColor: C.bg,
  },
  statNum: { fontSize: 20, fontWeight: '600', color: C.text },
  statLbl: { fontSize: 11, color: C.textSub, marginTop: 2 },
  hint: { fontSize: 13, color: C.textHint },
})

const dd = StyleSheet.create({
  box: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1, borderColor: C.border, borderRadius: 8, backgroundColor: C.bg,
    paddingHorizontal: 10, paddingVertical: 8,
  },
  label: { flex: 1, fontSize: 13, fontWeight: '500', color: C.text },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: C.card, borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: 320, paddingVertical: 8,
  },
  option: { paddingHorizontal: 20, paddingVertical: 14 },
  optionActive: { backgroundColor: C.blueLt },
  optionText: { fontSize: 14, color: C.text },
  optionTextActive: { color: C.primary, fontWeight: '600' },
})
