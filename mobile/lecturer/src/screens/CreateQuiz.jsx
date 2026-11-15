import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, TextInput,
  Modal, TouchableWithoutFeedback, Dimensions,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  getClasses, getQuizDrafts, getMaterials, generateQuiz,
  approveQuizQuestion, deleteQuizQuestion, publishQuiz,
} from '../services/api'
import { C } from '../theme'

// ─── Bottom sheet overlay (inline, mirrors components/Modals Sheet) ─────────

function Sheet({ visible, onClose, children }) {
  const { bottom } = useSafeAreaInsets()
  return (
    <Modal transparent animationType="slide" visible={visible} onRequestClose={onClose}>
      <View style={styles.overlay}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={StyleSheet.absoluteFillObject} />
        </TouchableWithoutFeedback>
        <View style={[styles.sheet, { paddingBottom: bottom }]}>
          <View style={styles.handle} />
          <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled" bounces={false}>
            {children}
          </ScrollView>
        </View>
      </View>
    </Modal>
  )
}

const BUTTON = { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 13, borderRadius: 10, gap: 6 }

export default function CreateQuiz({ navigation, route }) {
  const { showToast } = useLecturer()
  const { courseId: paramCourseId, courseCode, courseName } = (route?.params ?? {})

  const [coursePickerMode, setCoursePickerMode] = useState(!paramCourseId)
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [courseId, setCourseId] = useState(paramCourseId)
  const [courseCodeState, setCourseCodeState] = useState(courseCode)
  const [courseNameState, setCourseNameState] = useState(courseName)

  const [drafts, setDrafts] = useState([])
  const [draftsLoading, setDraftsLoading] = useState(false)

  const [generateVisible, setGenerateVisible] = useState(false)
  const [materials, setMaterials] = useState([])
  const [materialsLoading, setMaterialsLoading] = useState(false)
  const [selectedMaterials, setSelectedMaterials] = useState([])
  const [genType, setGenType] = useState('mcq')
  const [genLevel, setGenLevel] = useState('beginner')
  const [genCount, setGenCount] = useState('5')
  const [genBusy, setGenBusy] = useState(false)

  const [publishVisible, setPublishVisible] = useState(false)
  const [timeLimit, setTimeLimit] = useState('')
  const [publishBusy, setPublishBusy] = useState(false)

  const loadCourses = useCallback(async () => {
    try {
      const list = await getClasses()
      setCourses(list)
    } catch (e) { setError(e.message) }
  }, [])

  const loadDrafts = useCallback(async () => {
    if (!courseId) return
    setDraftsLoading(true)
    try {
      const list = await getQuizDrafts(courseId)
      setDrafts(list)
    } catch (e) { setError(e.message) }
    finally { setDraftsLoading(false) }
  }, [courseId])

  const loadMaterials = useCallback(async () => {
    if (!courseId) return
    setMaterialsLoading(true)
    try {
      const list = await getMaterials(courseId)
      setMaterials(list)
      setSelectedMaterials(list.map(m => m.id))
    } catch (e) { /* materials may not be indexed yet */ }
    finally { setMaterialsLoading(false) }
  }, [courseId])

  useEffect(() => {
    let cancelled = false
    if (coursePickerMode) {
      loadCourses().then(() => setLoading(false))
    } else {
      loadDrafts()
    }
    return () => { cancelled = true }
  }, [coursePickerMode, courseId, loadCourses, loadDrafts])

  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title={coursePickerMode ? 'Choose a course' : 'Create Quiz'} />
        <View style={styles.loading}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Loading…</Text>
        </View>
      </View>
    )
  }

  // ─── Course picker ───────────────────────────────────────────────────────

  if (coursePickerMode) {
    return (
      <View style={styles.flex}>
        <Topbar title="Choose a course" onBack={() => navigation.goBack()} />
        <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.list}>
          {error && <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>}
          {courses.map(c => (
            <TouchableOpacity key={c.id} style={styles.courseRow} onPress={() => {
              setCoursePickerMode(false)
              setCourseId(c.course_id)
              setCourseCodeState(c.code)
              setCourseNameState(c.name)
              loadDrafts()
              loadMaterials()
            }}>
              <View style={styles.courseRowBody}>
                <Text style={styles.courseRowCode}>{c.code}</Text>
                <Text style={styles.courseRowName}>{c.name}</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={C.textHint} />
            </TouchableOpacity>
          ))}
          {courses.length === 0 && <View style={styles.empty}><Text style={styles.emptyText}>No courses</Text></View>}
          <View style={{ height: 24 }} />
        </ScrollView>
      </View>
    )
  }

  const approved = drafts.filter(d => d.status === 'approved')
  const canPublish = approved.length > 0

  // ─── Hub ─────────────────────────────────────────────────────────────────

  return (
    <View style={styles.flex}>
      <Topbar
        title="Create Quiz / Poll"
        sub={courseCodeState}
        onBack={() => navigation.goBack()}
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {/* Draft questions */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Draft questions</Text>
            <Text style={styles.sectionSub}>{drafts.length} drafted · {approved.length} approved</Text>
          </View>
          {draftsLoading && <View style={styles.loadingSmall}><ActivityIndicator size={16} color={C.primary} /></View>}
          {!draftsLoading && drafts.length === 0 && (
            <View style={styles.empty}>
              <Ionicons name="create-outline" size={28} color={C.textHint} />
              <Text style={styles.emptyText}>No draft questions yet. Generate some from your course materials.</Text>
            </View>
          )}
          {!draftsLoading && drafts.map(d => (
            <View key={d.id} style={styles.draftCard}>
              <View style={styles.draftBody}>
                <Text style={styles.draftQuestion} numberOfLines={2}>{d.question}</Text>
                <View style={styles.optionsRow}>
                  {(d.options ?? []).map((o, i) => (
                    <View key={i} style={[styles.optionChip, d.correct_answer === o && styles.optionChipCorrect]}>
                      <Text style={[styles.optionChipText, d.correct_answer === o && styles.optionChipTextCorrect]}>
                        {String.fromCharCode(65 + i)}. {o}
                      </Text>
                    </View>
                  ))}
                </View>
                <View style={styles.draftMeta}>
                  <Badge variant={d.status === 'approved' ? 'green' : 'gray'}>{d.status.charAt(0).toUpperCase() + d.status.slice(1)}</Badge>
                  <Text style={styles.metaText}>{d.level} · {d.topic || '—'}</Text>
                </View>
              </View>
              <View style={styles.draftActions}>
                {d.status === 'draft' && (
                  <>
                    <TouchableOpacity style={styles.iconBtn} onPress={() => editDraft(d)}>
                      <Ionicons name="create-outline" size={16} color={C.primary} />
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.iconBtn} onPress={() => approveDraft(d.id)}>
                      <Ionicons name="checkmark-outline" size={16} color={C.green} />
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.iconBtn} onPress={() => deleteDraft(d.id)}>
                      <Ionicons name="trash-outline" size={16} color={C.red} />
                    </TouchableOpacity>
                  </>
                )}
                {d.status === 'approved' && (
                  <TouchableOpacity style={styles.iconBtn} onPress={() => viewDraft(d)}>
                    <Ionicons name="eye-outline" size={16} color={C.textSub} />
                  </TouchableOpacity>
                )}
              </View>
            </View>
          ))}
        </View>

        {/* Generate */}
        <View style={styles.section}>
          <TouchableOpacity style={styles.genRow} onPress={() => { loadMaterials(); setGenerateVisible(true) }}>
            <Ionicons name="sparkles" size={18} color="#fff" style={{ marginRight: 8 }} />
            <Text style={styles.genText}>Generate questions from materials</Text>
          </TouchableOpacity>
        </View>

        {/* Publish */}
        <View style={styles.section}>
          <View style={styles.publishRow}>
            <View>
              <Text style={styles.publishTitle}>Publish quiz</Text>
              <Text style={styles.publishSub}>{canPublish ? `${approved.length} approved question${approved.length !== 1 ? 's' : ''} ready` : 'Approve questions before publishing'}</Text>
            </View>
            <TouchableOpacity
              style={[styles.publishBtn, !canPublish && styles.publishBtnDisabled]}
              onPress={canPublish ? () => setPublishVisible(true) : undefined}
              disabled={!canPublish}
            >
              <Ionicons name="send-outline" size={16} color="#fff" />
              <Text style={styles.publishBtnText}>Publish</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={{ height: 24 }} />
      </ScrollView>

      {/* Generate modal */}
      <Sheet visible={generateVisible} onClose={() => setGenerateVisible(false)}>
        <View style={styles.modalBody}>
          <Text style={styles.modalTitle}>Generate questions</Text>
          <Text style={styles.modalSub}>Draft questions from your indexed course materials (LLM-generated; review before publishing).</Text>
          {materialsLoading && <View style={styles.loadingSmall}><ActivityIndicator size={16} color={C.primary} /></View>}
          {!materialsLoading && materials.length === 0 && (
            <View style={styles.empty}>
              <Ionicons name="folder-open" size={24} color={C.textHint} />
              <Text style={styles.emptyText}>No indexed materials for this course. Sync the KB first.</Text>
            </View>
          )}
          <Text style={styles.label}>Materials</Text>
          <View style={styles.materialsList}>
            {materials.map(m => (
              <TouchableOpacity
                key={m.id}
                style={[styles.materialChip, selectedMaterials.includes(m.id) && styles.materialChipActive]}
                onPress={() => setSelectedMaterials(prev =>
                  prev.includes(m.id) ? prev.filter(id => id !== m.id) : [...prev, m.id]
                )}
              >
                <Text style={[styles.materialChipText, selectedMaterials.includes(m.id) && styles.materialChipTextActive]}>{m.title}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.pillRow}>
            <Text style={styles.label}>Type</Text>
            <View style={styles.pills}>
              {['mcq', 'short_answer'].map(t => (
                <TouchableOpacity
                  key={t}
                  style={[styles.pill, genType === t && styles.pillActive]}
                  onPress={() => setGenType(t)}
                >
                  <Text style={[styles.pillText, genType === t && styles.pillTextActive]}>{t === 'mcq' ? 'MCQ' : 'Short answer'}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View style={styles.pillRow}>
            <Text style={styles.label}>Level</Text>
            <View style={styles.pills}>
              {['beginner', 'intermediate', 'advanced'].map(l => (
                <TouchableOpacity
                  key={l}
                  style={[styles.pill, genLevel === l && styles.pillActive]}
                  onPress={() => setGenLevel(l)}
                >
                  <Text style={[styles.pillText, genLevel === l && styles.pillTextActive]}>{l.charAt(0).toUpperCase() + l.slice(1)}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View style={styles.inputRow}>
            <Text style={styles.label}>Count</Text>
            <TextInput
              style={styles.countInput}
              value={genCount}
              onChangeText={setGenCount}
              keyboardType="numeric"
              placeholder="5"
              maxLength={2}
            />
          </View>
          <View style={styles.btnRow}>
            <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => setGenerateVisible(false)}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.btn, styles.btnPrimary]}
              onPress={handleGenerate}
              disabled={genBusy || selectedMaterials.length === 0}
            >
              <Text style={styles.btnPrimaryText}>{genBusy ? 'Generating…' : 'Generate'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Sheet>

      {/* Publish modal */}
      <Sheet visible={publishVisible} onClose={() => setPublishVisible(false)}>
        <View style={styles.modalBody}>
          <Text style={styles.modalTitle}>Publish quiz</Text>
          <Text style={styles.modalSub}>Publishes the approved questions as a quiz students can take.</Text>
          <Text style={styles.label}>Time limit (minutes)</Text>
          <TextInput
            style={styles.countInput}
            value={timeLimit}
            onChangeText={setTimeLimit}
            keyboardType="numeric"
            placeholder="30"
            maxLength={3}
          />
          <Text style={styles.hintText}>Students get one attempt; the attempt deadline is start + time limit.</Text>
          <View style={styles.btnRow}>
            <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => setPublishVisible(false)}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.btn, styles.btnPrimary]}
              onPress={handlePublish}
              disabled={publishBusy || !timeLimit}
            >
              <Text style={styles.btnPrimaryText}>{publishBusy ? 'Publishing…' : 'Publish quiz'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Sheet>
    </View>
  )

  // ─── Handlers ────────────────────────────────────────────────────────────

  async function handleGenerate() {
    if (genBusy || selectedMaterials.length === 0) return
    setGenBusy(true)
    try {
      const count = Math.max(1, Math.min(50, parseInt(genCount || '5', 10) || 5))
      await generateQuiz(courseId, {
        material_ids: selectedMaterials,
        type: genType,
        level: genLevel,
        count,
      })
      setGenerateVisible(false)
      setSelectedMaterials([])
      setGenCount('5')
      await loadDrafts()
      showToast('Questions drafted', 'success')
    } catch (e) {
      showToast(e.message || 'Could not generate questions', 'error')
    } finally {
      setGenBusy(false)
    }
  }

  async function handlePublish() {
    if (publishBusy || !timeLimit) return
    setPublishBusy(true)
    try {
      const quiz = await publishQuiz({
        question_ids: approved.map(a => a.id),
        time_limit_minutes: parseInt(timeLimit, 10),
      })
      setPublishVisible(false)
      navigation.navigate('LiveResults', {
        quizId: quiz.id, courseId, courseCode: courseCodeState, courseName: courseNameState,
      })
    } catch (e) {
      showToast(e.message || 'Could not publish quiz', 'error')
    } finally {
      setPublishBusy(false)
    }
  }

  async function editDraft(d) {
    showToast('Use the lecturer web app to edit question text', 'info')
  }

  async function approveDraft(id) {
    try {
      await approveQuizQuestion(id)
      await loadDrafts()
      showToast('Question approved', 'success')
    } catch (e) { showToast(e.message || 'Could not approve', 'error') }
  }

  async function deleteDraft(id) {
    try {
      await deleteQuizQuestion(id)
      await loadDrafts()
      showToast('Question deleted', 'success')
    } catch (e) { showToast(e.message || 'Could not delete', 'error') }
  }

  function viewDraft(d) {
    showToast(`${d.options?.length ?? 0} options · correct: ${d.correct_answer ?? '—'}`, 'info')
  }
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  list: { padding: 16 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  loadingSmall: { paddingVertical: 8 },
  loadingText: { fontSize: 14, color: C.textSub },
  err: { padding: 16 },
  errText: { fontSize: 13, color: C.red },
  empty: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  emptyText: { fontSize: 13, color: C.textSub },
  courseRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: C.card, borderRadius: 10, padding: 14, marginHorizontal: 16, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  courseRowBody: { flex: 1 },
  courseRowCode: { fontSize: 15, fontWeight: '800', color: C.primary },
  courseRowName: { fontSize: 13, fontWeight: '700', color: C.text, marginTop: 2 },
  section: { marginBottom: 14 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: C.text },
  sectionSub: { fontSize: 12, color: C.textSub },
  draftCard: {
    backgroundColor: C.card, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.border, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  draftBody: { flex: 1, marginRight: 8 },
  draftQuestion: { fontSize: 13, fontWeight: '700', color: C.text, lineHeight: 19, marginBottom: 6 },
  optionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 },
  optionChip: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 5,
    borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.gray50,
  },
  optionChipCorrect: { borderColor: C.green, backgroundColor: C.greenLt },
  optionChipText: { fontSize: 11, color: C.textSub },
  optionChipTextCorrect: { color: C.greenDk, fontWeight: '700' },
  draftMeta: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  metaText: { fontSize: 11, color: C.textHint },
  draftActions: { flexDirection: 'row', gap: 6 },
  iconBtn: { padding: 6 },
  genRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: C.primary, borderRadius: 10,
    paddingVertical: 14, paddingHorizontal: 14, gap: 8, marginBottom: 10,
  },
  genText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  publishRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: C.blueLt, borderRadius: 10, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: C.blueLt,
  },
  publishRowDisabled: { opacity: 0.6 },
  publishTitle: { fontSize: 14, fontWeight: '800', color: C.text },
  publishSub: { fontSize: 12, color: C.textSub, marginTop: 2 },
  publishBtn: { ...BUTTON, backgroundColor: C.primary, paddingHorizontal: 16 },
  publishBtnDisabled: { ...BUTTON, backgroundColor: C.gray100, borderColor: C.border },
  publishBtnText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  modalBody: { padding: 16 },
  modalTitle: { fontSize: 18, fontWeight: '800', color: C.text, marginBottom: 4 },
  modalSub: { fontSize: 13, color: C.textSub, marginBottom: 16 },
  label: { fontSize: 12, fontWeight: '700', color: C.text, marginBottom: 6 },
  materialsList: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 },
  materialChip: {
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card,
  },
  materialChipActive: { borderColor: C.primary, backgroundColor: C.blueLt },
  materialChipText: { fontSize: 12, color: C.text },
  materialChipTextActive: { color: C.primary, fontWeight: '700' },
  pillRow: { marginBottom: 14 },
  pills: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  pill: {
    flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1.5, borderColor: C.border, alignItems: 'center', backgroundColor: C.card,
  },
  pillActive: { backgroundColor: C.primary, borderColor: C.primary },
  pillText: { fontSize: 13, fontWeight: '600', color: C.textSub },
  pillTextActive: { color: '#fff' },
  inputRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 14 },
  countInput: {
    flex: 1, height: 46, borderWidth: 1.5, borderColor: C.border, borderRadius: 10, paddingHorizontal: 12,
    fontSize: 14, color: C.text, backgroundColor: C.card,
  },
  hintText: { fontSize: 12, color: C.textHint, marginBottom: 14 },
  btnRow: { flexDirection: 'row', gap: 8 },
  btn: { flex: 1, ...BUTTON },
  btnPrimary: { backgroundColor: C.primary },
  btnOutline: { borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card },
  btnPrimaryText: { fontSize: 15, fontWeight: '700', color: '#fff' },
  btnOutlineText: { fontSize: 15, fontWeight: '600', color: C.text },
  handle: { width: 40, height: 4, backgroundColor: C.gray300, borderRadius: 2, alignSelf: 'center', marginBottom: 14 },
  overlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 20, paddingTop: 12, maxHeight: Dimensions.get('window').height * 0.85,
  },
})
