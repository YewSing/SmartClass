import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Modal, FlatList, RefreshControl, ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import * as api from '../services/api'
import { materialsSummary } from '../services/assistantHelpers'
import { C } from '../theme'

// Material status → label + colour (FR-804)
const STATUS_META = {
  indexed: { label: 'Indexed', color: C.greenDk, bg: C.greenLt },
  no_text: { label: 'No text', color: C.orangeDk, bg: C.orangeLt },
  unsupported: { label: 'Unsupported', color: C.gray600, bg: C.gray100 },
  error: { label: 'Error', color: C.redDk, bg: C.redLt },
  pending: { label: 'Pending', color: C.gray600, bg: C.gray100 },
}

function statusMeta(status) {
  return STATUS_META[status] ?? { label: status, color: C.gray600, bg: C.gray100 }
}

function CoursePicker({ value, items, onChange }) {
  const [open, setOpen] = useState(false)
  const selected = items.find(i => i.value === value)
  return (
    <>
      <TouchableOpacity style={ddStyles.box} testID="assistant-course-picker" onPress={() => setOpen(true)} activeOpacity={0.7}>
        <Text style={ddStyles.label} numberOfLines={1}>{selected?.label ?? 'Pick a course'}</Text>
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
  label: { flex: 1, fontSize: 13, fontWeight: '500', color: C.text },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: C.card,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: 320,
    paddingVertical: 8,
  },
  option: { paddingHorizontal: 20, paddingVertical: 14 },
  optionActive: { backgroundColor: C.blueLt },
  optionText: { fontSize: 14, color: C.text },
  optionTextActive: { color: C.primary, fontWeight: '700' },
})

function TrendList({ title, icon, empty, rows }) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Ionicons name={icon} size={16} color={C.primary} />
        <Text style={styles.cardTitle}>{title}</Text>
      </View>
      {rows.length === 0 ? (
        <Text style={styles.hintText}>{empty}</Text>
      ) : (
        <View style={styles.trendList}>
          {rows.map((r, i) => (
            <View key={i} style={styles.trendRow}>
              <Text style={styles.trendText} numberOfLines={2}>{r.label}</Text>
              <Text style={styles.trendCount}>{r.students}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  )
}

export default function LecturerAssistant({ navigation }) {
  const { showToast } = useLecturer()
  const [courses, setCourses] = useState([])
  const [courseId, setCourseId] = useState(null)
  const [materials, setMaterials] = useState(null)
  const [trends, setTrends] = useState(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [materialsOpen, setMaterialsOpen] = useState(false)   // collapsed: the trends matter more day to day

  const loadCourses = useCallback(async () => {
    try {
      const list = await api.getAssistantCourses()
      setCourses(list)
      setCourseId(prev => prev ?? list[0]?.id ?? null)
    } catch (e) { showToast(e.message, 'error') }
  }, [showToast])

  const loadData = useCallback(async (id) => {
    if (!id) return
    setLoading(true)
    try {
      const [mats, tr] = await Promise.all([api.getMaterials(id), api.getQuestionTrends(id)])
      setMaterials(mats)
      setTrends(tr)
    } catch (e) { showToast(e.message, 'error') } finally { setLoading(false) }
  }, [showToast])

  useEffect(() => { loadCourses() }, [loadCourses])
  useEffect(() => { if (courseId) loadData(courseId) }, [courseId, loadData])

  const onSync = useCallback(async () => {
    if (!courseId || syncing) return
    setSyncing(true)
    try {
      const report = await api.syncMaterials(courseId)
      showToast(`Materials synced (${report.added ?? 0} new, ${report.updated ?? 0} updated)`, 'success')
      await loadData(courseId)
    } catch (e) {
      showToast(e.message, 'error')
    } finally { setSyncing(false) }
  }, [courseId, syncing, loadData, showToast])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadCourses(), courseId ? loadData(courseId) : Promise.resolve()])
    setRefreshing(false)
  }, [loadCourses, loadData, courseId])

  const courseItems = courses.map(c => ({ label: `${c.code} — ${c.name}`, value: c.id }))

  return (
    <View style={styles.flex}>
      <Topbar
        title="AI Assistant"
        right={
          <TouchableOpacity
            style={[styles.syncBtn, (!courseId || syncing) && styles.btnDisabled]}
            testID="assistant-sync"
            onPress={onSync}
            disabled={!courseId || syncing}
          >
            <Ionicons name="sync" size={14} color="#fff" />
            <Text style={styles.syncBtnText}>{syncing ? 'Syncing…' : 'Sync materials'}</Text>
          </TouchableOpacity>
        }
      />

      <View style={styles.pickerRow}>
        <CoursePicker value={courseId} items={courseItems} onChange={setCourseId} />
      </View>

      {courseId ? (
        <View style={styles.actionsRow}>
          <TouchableOpacity
            style={styles.actionBtn}
            testID="assistant-ask"
            onPress={() => navigation.navigate('LecturerAsk', {
              courseId, courseCode: courses.find(c => c.id === courseId)?.code ?? '',
            })}
          >
            <Ionicons name="chatbubble-ellipses-outline" size={16} color={C.primary} />
            <Text style={styles.actionText}>Ask my materials</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionBtn}
            testID="assistant-before-class"
            onPress={() => navigation.navigate('BeforeClass', {
              courseId, courseCode: courses.find(c => c.id === courseId)?.code ?? '',
            })}
          >
            <Ionicons name="bulb-outline" size={16} color={C.primary} />
            <Text style={styles.actionText}>Before next class</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* Materials status (FR-804) */}
        <TouchableOpacity
          style={styles.collapseHeader}
          onPress={() => setMaterialsOpen(o => !o)}
          testID="assistant-materials-toggle"
          accessibilityRole="button"
          accessibilityState={{ expanded: materialsOpen }}
        >
          <Text style={[styles.sectionLabel, styles.collapseLabel]}>Materials</Text>
          <Text style={styles.collapseSummary} numberOfLines={1}>{materialsSummary(materials)}</Text>
          <Ionicons name={materialsOpen ? 'chevron-up' : 'chevron-down'} size={16} color={C.textHint} />
        </TouchableOpacity>
        {materialsOpen ? (
        <View style={styles.card} testID="assistant-materials">
          {loading && !materials ? (
            <View style={styles.centered}><ActivityIndicator color={C.primary} /></View>
          ) : !materials ? (
            <Text style={styles.hintText}>No materials yet — sync the course first.</Text>
          ) : materials.length === 0 ? (
            <Text style={styles.hintText}>No materials in this course.</Text>
          ) : (
            materials.map((m, i) => {
              const meta = statusMeta(m.status)
              return (
                <View key={m.id} style={[styles.materialRow, i > 0 && styles.rowBorder]}>
                  <View style={styles.flex}>
                    <Text style={styles.materialTitle} numberOfLines={1}>{m.title}</Text>
                    <Text style={styles.materialMeta} numberOfLines={1}>
                      {m.section ? `${m.section} · ` : ''}{m.chunks} chunks
                    </Text>
                  </View>
                  <View style={[styles.badge, { backgroundColor: meta.bg }]}>
                    <Text style={[styles.badgeText, { color: meta.color }]}>{meta.label}</Text>
                  </View>
                </View>
              )
            })
          )}
        </View>
        ) : null}

        {/* Question trends (FR-813) */}
        <Text style={styles.sectionLabel}>What students ask</Text>
        {!trends ? (
          <Text style={styles.hintText}>Loading…</Text>
        ) : (
          <>
            <TrendList
              title="Most asked topics" icon="chatbubbles-outline"
              empty="No topics have enough student questions yet."
              rows={(trends.mostAsked ?? []).map(t => ({ label: t.topic, students: t.students }))}
            />
            <TrendList
              title="Most cited materials" icon="document-text-outline"
              empty="No materials have been cited enough yet."
              rows={(trends.mostCited ?? []).map(t => ({ label: t.title, students: t.students }))}
            />
            <TrendList
              title="Topics the materials don't cover" icon="help-circle-outline"
              empty="Nothing asked is outside the materials yet."
              rows={(trends.uncovered ?? []).map(t => ({ label: t.topic, students: t.students }))}
            />
          </>
        )}

        <View style={{ height: 20 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  syncBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    gap: 4,
  },
  syncBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  btnDisabled: { opacity: 0.45 },
  pickerRow: {
    flexDirection: 'row',
    padding: 10,
    gap: 8,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 8,
    padding: 10,
    backgroundColor: C.bg,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: C.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.primary,
    paddingVertical: 11,
  },
  actionText: { fontSize: 13, fontWeight: '600', color: C.primary },
  collapseHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingRight: 16 },
  collapseLabel: { paddingBottom: 0, marginBottom: 0, paddingTop: 14 },
  collapseSummary: { flex: 1, fontSize: 12, color: C.textHint, paddingTop: 14 },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    paddingHorizontal: 16,
    paddingTop: 14,
    marginBottom: 6,
  },
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    marginHorizontal: 16,
    paddingHorizontal: 14,
    paddingVertical: 6,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: C.border,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10 },
  cardTitle: { fontSize: 13, fontWeight: '700', color: C.text },
  materialRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 },
  rowBorder: { borderTopWidth: 1, borderTopColor: C.border },
  materialTitle: { fontSize: 13, fontWeight: '600', color: C.text },
  materialMeta: { fontSize: 11, color: C.textSub, marginTop: 1 },
  badge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  trendList: { paddingBottom: 10 },
  trendRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 },
  trendText: { flex: 1, fontSize: 13, color: C.text },
  trendCount: { fontSize: 12, fontWeight: '700', color: C.textSub },
  hintText: { fontSize: 13, color: C.textHint, textAlign: 'center', padding: 16 },
  centered: { alignItems: 'center', padding: 24 },
})
