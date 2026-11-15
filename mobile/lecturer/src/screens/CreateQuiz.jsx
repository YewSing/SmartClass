import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, TextInput,
  Switch, Modal, FlatList, Dimensions,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  getClasses, getMaterials, syncMaterials, getQuizDrafts,
  generateQuiz, editQuizQuestion, approveQuizQuestion, deleteQuizQuestion,
  createQuizQuestion, quickAddQuiz, publishQuiz, saveQuizDraft,
} from '../services/api'
import { C } from '../theme'

const { BUTTON } = { BUTTON: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 10 } }

/** Section card in the interaction style: colored title chip + right node (S29 pattern). */
function Section({ tint = 'blue', badge, right, children, style }) {
  const bg = { blue: C.blueLt, green: C.greenLt, red: C.redLt, orange: C.orangeLt, gray: C.gray100, purple: C.purpleLt, yellow: C.yellowLt }[tint]
  const fg = { blue: C.blueDk, green: C.greenDk, red: C.redDk, orange: C.orangeDk, gray: C.textSub, purple: C.purple, yellow: C.yellowDk }[tint]
  return (
    <View style={[styles.section, style]}>
      {badge != null && (
        <View style={styles.sectionHead}>
          <View style={[styles.sectionBadge, { backgroundColor: bg }]}>
            <Text style={[styles.sectionBadgeText, { color: fg }]}>{badge}</Text>
          </View>
          <View style={{ flex: 1 }} />
          {right}
        </View>
      )}
      {children}
    </View>
  )
}

function Sheet({ visible, onClose, children }) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <ScrollView showsVerticalScrollIndicator={false}>{children}</ScrollView>
        </View>
      </View>
    </Modal>
  )
}

function dtLocal(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

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
  const [syncing, setSyncing] = useState(false)

  // Generate-from-materials sheet
  const [generateVisible, setGenerateVisible] = useState(false)
  const [materials, setMaterials] = useState([])
  const [materialsLoading, setMaterialsLoading] = useState(false)
  const [selectedMaterials, setSelectedMaterials] = useState([])
  const [genType, setGenType] = useState('mcq')
  const [genLevel, setGenLevel] = useState('beginner')
  const [genCount, setGenCount] = useState('5')
  const [genBusy, setGenBusy] = useState(false)

  // LLM quick-add ("create 5 mcq, 2 short answer, duration 15min, valid two days from now")
  const [quickPrompt, setQuickPrompt] = useState('')
  const [quickBusy, setQuickBusy] = useState(false)

  // Manual question sheet
  const [addVisible, setAddVisible] = useState(false)
  const [addType, setAddType] = useState('mcq')
  const [addText, setAddText] = useState('')
  const [addOptions, setAddOptions] = useState(['', '', '', ''])
  const [addCorrect, setAddCorrect] = useState('A')
  const [addSuggested, setAddSuggested] = useState('')
  const [addTopic, setAddTopic] = useState('')
  const [addBusy, setAddBusy] = useState(false)

  // Edit question sheet
  const [editTarget, setEditTarget] = useState(null)
  const [editText, setEditText] = useState('')
  const [editOptions, setEditOptions] = useState([])
  const [editCorrect, setEditCorrect] = useState('')
  const [editSuggested, setEditSuggested] = useState('')
  const [editBusy, setEditBusy] = useState(false)

  // Quiz details (Moodle-style)
  const [quizTitle, setQuizTitle] = useState('')
  const [timeLimit, setTimeLimit] = useState('15')
  const [opensAt, setOpensAt] = useState(dtLocal(new Date()))
  const [closesAt, setClosesAt] = useState('')
  const [attempts, setAttempts] = useState('1')
  const [reviewVisible, setReviewVisible] = useState(true)

  // Finish: target classes
  const [targetIds, setTargetIds] = useState([])
  const [finishBusy, setFinishBusy] = useState(false)

  const loadCourses = useCallback(async () => {
    try {
      const list = await getClasses()
      setCourses(list)
      setTargetIds(prev => (prev.length ? prev : list.slice(0, 1).map(c => c.course_id)))
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
      loadCourses().then(() => { if (!cancelled) setLoading(false) })
    } else {
      loadDrafts().then(() => { if (!cancelled) setLoading(false) })
    }
    return () => { cancelled = true }
  }, [coursePickerMode, courseId, loadCourses, loadDrafts])

  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title={coursePickerMode ? 'Choose a class' : 'Create Quiz'} />
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
        <Topbar title="Choose a class" onBack={() => navigation.goBack()} />
        <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.list}>
          {error && <View style={styles.err}><Text style={styles.errText}>{error}</Text></View>}
          {courses.map(c => (
            <TouchableOpacity key={c.id} style={styles.courseRow} onPress={() => {
              setCoursePickerMode(false)
              setCourseId(c.course_id)
              setCourseCodeState(c.code)
              setCourseNameState(c.name)
              setTargetIds([c.course_id])
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
  const canFinish = approved.length > 0

  // ─── Builder ─────────────────────────────────────────────────────────────

  const quickAdd = async () => {
    if (quickBusy || !quickPrompt.trim()) return
    setQuickBusy(true)
    try {
      const quiz = await quickAddQuiz(courseId, {
        prompt: quickPrompt.trim(),
        material_ids: selectedMaterials,
        level: genLevel,
      })
      setQuickPrompt('')
      await loadDrafts()
      if (quiz.time_limit_minutes) setTimeLimit(String(quiz.time_limit_minutes))
      if (quiz.title) setQuizTitle(quiz.title)
      if (quiz.closes_at) setClosesAt(dtLocal(new Date(quiz.closes_at)))
      showToast('AI drafted the quiz — review the questions below', 'success')
    } catch (e) {
      showToast(e.message || 'Could not build the quiz from that instruction', 'error')
    } finally {
      setQuickBusy(false)
    }
  }

  const syncFromMoodle = async () => {
    if (syncing) return
    setSyncing(true)
    try {
      await syncMaterials(courseId)
      await loadMaterials()
      showToast('Materials synced from Moodle', 'success')
    } catch (e) {
      showToast(e.message || 'Sync failed', 'error')
    } finally {
      setSyncing(false)
    }
  }

  const handleGenerate = async () => {
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
      setGenCount('5')
      await loadDrafts()
      showToast('Questions drafted', 'success')
    } catch (e) {
      showToast(e.message || 'Could not generate questions', 'error')
    } finally {
      setGenBusy(false)
    }
  }

  const handleAddQuestion = async () => {
    if (addBusy || !addText.trim()) return
    setAddBusy(true)
    try {
      const data = {
        course_id: courseId,
        type: addType,
        question: addText.trim(),
        level: genLevel,
        topic: addTopic.trim() || null,
      }
      if (addType === 'mcq') {
        const options = addOptions.map(o => o.trim()).filter(Boolean)
        if (options.length < 2) { showToast('Give at least 2 options', 'error'); setAddBusy(false); return }
        const correctIdx = 'ABCD'.indexOf(addCorrect)
        data.options = options
        data.correct_answer = options[Math.min(correctIdx, options.length - 1)]
      } else {
        data.suggested_answer = addSuggested.trim() || null
      }
      await createQuizQuestion(data)
      setAddVisible(false)
      setAddText(''); setAddOptions(['', '', '', '']); setAddSuggested(''); setAddTopic('')
      await loadDrafts()
      showToast('Question added as draft', 'success')
    } catch (e) {
      showToast(e.message || 'Could not add question', 'error')
    } finally {
      setAddBusy(false)
    }
  }

  const openEdit = (d) => {
    setEditTarget(d)
    setEditText(d.question)
    setEditOptions(d.options ?? [])
    setEditCorrect(d.correct_answer ?? '')
    setEditSuggested(d.suggested_answer ?? '')
  }

  const handleEditSave = async () => {
    if (editBusy || !editTarget) return
    setEditBusy(true)
    try {
      const data = { question: editText.trim() }
      if (editTarget.type === 'mcq') {
        data.options = editOptions.map(o => o.trim()).filter(Boolean)
        const idx = ('ABCD').indexOf(editCorrect)
        data.correct_answer = data.options[Math.min(Math.max(idx, 0), data.options.length - 1)]
      } else {
        data.suggested_answer = editSuggested.trim() || null
      }
      await editQuizQuestion(editTarget.id, data)
      setEditTarget(null)
      await loadDrafts()
      showToast('Question updated', 'success')
    } catch (e) {
      showToast(e.message || 'Could not save question', 'error')
    } finally {
      setEditBusy(false)
    }
  }

  const detailsPayload = () => ({
    title: quizTitle.trim() || `Quiz · ${courseCodeState ?? ''}`.trim(),
    time_limit_minutes: Math.max(1, Math.min(600, parseInt(timeLimit || '15', 10) || 15)),
    opens_at: opensAt ? new Date(opensAt).toISOString() : null,
    closes_at: closesAt ? new Date(closesAt).toISOString() : null,
    attempts_allowed: Math.max(1, Math.min(10, parseInt(attempts || '1', 10) || 1)),
    review_visible: reviewVisible,
  })

  const handlePublish = async () => {
    if (finishBusy || !canFinish) return
    setFinishBusy(true)
    try {
      const created = await publishQuiz({
        question_ids: approved.map(a => a.id),
        course_ids: targetIds.length ? targetIds : [courseId],
        ...detailsPayload(),
      })
      showToast(`Quiz published to ${created.length} class${created.length !== 1 ? 'es' : ''}`, 'success')
      navigation.navigate('LiveResults', {
        quizId: created[0].id, courseId: created[0].course_id,
        courseCode: courseCodeState, courseName: courseNameState,
      })
    } catch (e) {
      showToast(e.message || 'Could not publish quiz', 'error')
    } finally {
      setFinishBusy(false)
    }
  }

  const handleSaveDraft = async () => {
    if (finishBusy || drafts.length === 0) return
    setFinishBusy(true)
    try {
      await saveQuizDraft({
        question_ids: drafts.map(d => d.id),
        ...detailsPayload(),
      })
      showToast('Saved as draft — find it under Draft on the Quiz page', 'success')
      navigation.goBack()
    } catch (e) {
      showToast(e.message || 'Could not save draft', 'error')
    } finally {
      setFinishBusy(false)
    }
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Create Quiz"
        sub={courseCodeState ? `${courseCodeState} · ${courseNameState ?? ''}` : undefined}
        onBack={() => navigation.goBack()}
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>

        {/* 1 — AI quick-add */}
        <Section tint="purple" badge="AI quick-add">
          <Text style={styles.hintText}>
            Say what you want, e.g. <Text style={styles.hintBold}>“create 5 mcq, 2 short answer, duration 15min, valid two days from now”</Text> — the AI reads your materials, drafts the questions and fills the details.
          </Text>
          <TextInput
            style={styles.quickInput}
            value={quickPrompt}
            onChangeText={setQuickPrompt}
            placeholder="create 5 mcq, 2 short answer, duration 15min…"
            placeholderTextColor={C.textHint}
            multiline
            testID="quiz-quick-prompt"
          />
          <TouchableOpacity
            style={[styles.btn, styles.btnPrimary, (!quickPrompt.trim() || quickBusy) && styles.btnDisabled]}
            onPress={quickAdd}
            disabled={!quickPrompt.trim() || quickBusy}
            testID="quiz-quick-go"
          >
            {quickBusy
              ? <ActivityIndicator size="small" color="#fff" />
              : <Ionicons name="sparkles" size={16} color="#fff" />}
            <Text style={styles.btnPrimaryText}>{quickBusy ? 'Drafting…' : 'Draft with AI'}</Text>
          </TouchableOpacity>
        </Section>

        {/* 2 — materials + manual building */}
        <Section tint="blue" badge="Build questions">
          <View style={styles.materialsHead}>
            <Text style={styles.subLabel}>Course materials (synced from Moodle)</Text>
            <TouchableOpacity style={styles.syncBtn} onPress={syncFromMoodle} disabled={syncing} testID="quiz-sync">
              {syncing
                ? <ActivityIndicator size={12} color={C.primary} />
                : <Ionicons name="sync" size={13} color={C.primary} />}
              <Text style={styles.syncText}>{syncing ? 'Syncing…' : 'Sync Moodle'}</Text>
            </TouchableOpacity>
          </View>
          {materialsLoading && <View style={styles.loadingSmall}><ActivityIndicator size={16} color={C.primary} /></View>}
          {!materialsLoading && materials.length === 0 && (
            <Text style={styles.hintText}>No indexed materials yet — press “Sync Moodle”, then generate from them.</Text>
          )}
          <View style={styles.materialsList}>
            {materials.map(m => (
              <TouchableOpacity
                key={m.id}
                style={[styles.materialChip, selectedMaterials.includes(m.id) && styles.materialChipActive]}
                onPress={() => setSelectedMaterials(prev =>
                  prev.includes(m.id) ? prev.filter(id => id !== m.id) : [...prev, m.id]
                )}
              >
                <Text style={[styles.materialChipText, selectedMaterials.includes(m.id) && styles.materialChipTextActive]} numberOfLines={1}>{m.title}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.pillRow}>
            <Text style={styles.subLabel}>Level for new questions</Text>
            <View style={styles.pills}>
              {['beginner', 'intermediate', 'advanced'].map(l => (
                <TouchableOpacity key={l} style={[styles.pill, genLevel === l && styles.pillActive]} onPress={() => setGenLevel(l)}>
                  <Text style={[styles.pillText, genLevel === l && styles.pillTextActive]}>{l.charAt(0).toUpperCase() + l.slice(1)}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View style={styles.buildRow}>
            <TouchableOpacity style={[styles.buildBtn, { backgroundColor: C.blueLt }]} onPress={() => { loadMaterials(); setGenerateVisible(true) }} testID="quiz-generate">
              <Ionicons name="sparkles-outline" size={16} color={C.blueDk} />
              <Text style={[styles.buildBtnText, { color: C.blueDk }]}>Generate from materials</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.buildBtn, { backgroundColor: C.yellowLt }]} onPress={() => setAddVisible(true)} testID="quiz-add-question">
              <Ionicons name="add-circle-outline" size={16} color={C.yellowDk} />
              <Text style={[styles.buildBtnText, { color: C.yellowDk }]}>Add question manually</Text>
            </TouchableOpacity>
          </View>
        </Section>

        {/* 3 — review questions */}
        <Section
          tint="green"
          badge="Review questions"
          right={<Text style={styles.counter}>{drafts.length} draft · {approved.length} approved</Text>}
        >
          {draftsLoading && <View style={styles.loadingSmall}><ActivityIndicator size={16} color={C.primary} /></View>}
          {!draftsLoading && drafts.length === 0 && (
            <View style={styles.empty}>
              <Ionicons name="create-outline" size={28} color={C.textHint} />
              <Text style={styles.emptyText}>No questions yet — draft with AI, generate, or add manually.</Text>
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
                  {d.type === 'short_answer' && !!d.suggested_answer && (
                    <View style={[styles.optionChip, styles.optionChipCorrect]}>
                      <Text style={[styles.optionChipText, styles.optionChipTextCorrect]} numberOfLines={1}>ideal: {d.suggested_answer}</Text>
                    </View>
                  )}
                </View>
                <View style={styles.draftMeta}>
                  <Badge variant={d.status === 'approved' ? 'green' : 'gray'}>{d.status.charAt(0).toUpperCase() + d.status.slice(1)}</Badge>
                  <Text style={styles.metaText}>{d.type === 'mcq' ? 'MCQ' : 'Short answer'} · {d.level} · {d.topic || '—'}</Text>
                </View>
              </View>
              <View style={styles.draftActions}>
                {d.status === 'draft' && (
                  <>
                    <TouchableOpacity style={styles.iconBtn} onPress={() => openEdit(d)} testID={`quiz-edit-${d.id}`}>
                      <Ionicons name="create-outline" size={16} color={C.primary} />
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.iconBtn} onPress={() => approveQuizQuestion(d.id).then(loadDrafts).then(() => showToast('Approved', 'success')).catch(e => showToast(e.message, 'error'))} testID={`quiz-approve-${d.id}`}>
                      <Ionicons name="checkmark-outline" size={16} color={C.green} />
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.iconBtn} onPress={() => deleteQuizQuestion(d.id).then(loadDrafts).catch(e => showToast(e.message, 'error'))} testID={`quiz-delete-${d.id}`}>
                      <Ionicons name="trash-outline" size={16} color={C.red} />
                    </TouchableOpacity>
                  </>
                )}
                {d.status === 'approved' && (
                  <TouchableOpacity style={styles.iconBtn} onPress={() => showToast(`${d.options?.length ?? 0} options · correct: ${d.correct_answer ?? '—'}`, 'info')}>
                    <Ionicons name="eye-outline" size={16} color={C.textSub} />
                  </TouchableOpacity>
                )}
              </View>
            </View>
          ))}
        </Section>

        {/* 4 — quiz details */}
        <Section tint="yellow" badge="Quiz details">
          <Text style={styles.subLabel}>Title</Text>
          <TextInput style={styles.input} value={quizTitle} onChangeText={setQuizTitle}
            placeholder="e.g. Week 3 quiz" placeholderTextColor={C.textHint} />
          <View style={styles.detailRow}>
            <View style={styles.detailCol}>
              <Text style={styles.subLabel}>Time limit (min)</Text>
              <TextInput style={styles.input} value={timeLimit} onChangeText={setTimeLimit} keyboardType="numeric" />
            </View>
            <View style={styles.detailCol}>
              <Text style={styles.subLabel}>Attempts allowed</Text>
              <TextInput style={styles.input} value={attempts} onChangeText={setAttempts} keyboardType="numeric" />
            </View>
          </View>
          <View style={styles.detailRow}>
            <View style={styles.detailCol}>
              <Text style={styles.subLabel}>Open</Text>
              <TextInput style={styles.input} value={opensAt} onChangeText={setOpensAt} placeholder="YYYY-MM-DDTHH:MM" placeholderTextColor={C.textHint} />
            </View>
            <View style={styles.detailCol}>
              <Text style={styles.subLabel}>Close</Text>
              <TextInput style={styles.input} value={closesAt} onChangeText={setClosesAt} placeholder="YYYY-MM-DDTHH:MM" placeholderTextColor={C.textHint} />
            </View>
          </View>
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.subLabel}>Students see results after answering</Text>
              <Text style={styles.hintText}>Turn off to keep scores and correct answers hidden from students.</Text>
            </View>
            <Switch value={reviewVisible} onValueChange={setReviewVisible} trackColor={{ true: C.green }} testID="quiz-review-visible" />
          </View>
        </Section>

        {/* 5 — publish / draft */}
        <Section tint="orange" badge="Finish">
          <Text style={styles.subLabel}>Publish to class(es)</Text>
          <View style={styles.materialsList}>
            {courses.map(c => (
              <TouchableOpacity
                key={c.id}
                style={[styles.materialChip, targetIds.includes(c.course_id) && styles.materialChipActive]}
                onPress={() => setTargetIds(prev =>
                  prev.includes(c.course_id) ? prev.filter(id => id !== c.course_id) : [...prev, c.course_id]
                )}
              >
                <Text style={[styles.materialChipText, targetIds.includes(c.course_id) && styles.materialChipTextActive]}>{c.code}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.hintText}>
            {canFinish
              ? `${approved.length} approved question${approved.length !== 1 ? 's' : ''} will be published to the selected class${targetIds.length !== 1 ? 'es' : ''}.`
              : 'Approve at least one question above before publishing.'}
          </Text>
          <View style={styles.btnRow}>
            <TouchableOpacity
              style={[styles.btn, styles.btnOutline]}
              onPress={handleSaveDraft}
              disabled={finishBusy || drafts.length === 0}
              testID="quiz-save-draft"
            >
              <Ionicons name="document-text-outline" size={16} color={C.text} />
              <Text style={styles.btnOutlineText}>Save as draft</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.btn, styles.btnPrimary, !canFinish && styles.btnDisabled]}
              onPress={handlePublish}
              disabled={finishBusy || !canFinish}
              testID="quiz-publish"
            >
              <Ionicons name="send-outline" size={16} color="#fff" />
              <Text style={styles.btnPrimaryText}>{finishBusy ? 'Working…' : 'Publish'}</Text>
            </TouchableOpacity>
          </View>
        </Section>

        <View style={{ height: 24 }} />
      </ScrollView>

      {/* Generate-from-materials sheet */}
      <Sheet visible={generateVisible} onClose={() => setGenerateVisible(false)}>
        <View style={styles.modalBody}>
          <Text style={styles.modalTitle}>Generate questions</Text>
          <Text style={styles.modalSub}>Draft questions from your indexed course materials (LLM-generated; review before publishing).</Text>
          <Text style={styles.subLabel}>Type</Text>
          <View style={styles.pills}>
            {['mcq', 'short_answer'].map(t => (
              <TouchableOpacity key={t} style={[styles.pill, genType === t && styles.pillActive]} onPress={() => setGenType(t)}>
                <Text style={[styles.pillText, genType === t && styles.pillTextActive]}>{t === 'mcq' ? 'MCQ' : 'Short answer'}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.subLabel}>How many</Text>
          <TextInput style={styles.input} value={genCount} onChangeText={setGenCount} keyboardType="numeric" maxLength={2} />
          <View style={styles.btnRow}>
            <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => setGenerateVisible(false)}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={handleGenerate} disabled={genBusy || selectedMaterials.length === 0}>
              <Text style={styles.btnPrimaryText}>{genBusy ? 'Generating…' : 'Generate'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Sheet>

      {/* Add-question sheet */}
      <Sheet visible={addVisible} onClose={() => setAddVisible(false)}>
        <View style={styles.modalBody}>
          <Text style={styles.modalTitle}>Add a question</Text>
          <View style={styles.pills}>
            {['mcq', 'short_answer'].map(t => (
              <TouchableOpacity key={t} style={[styles.pill, addType === t && styles.pillActive]} onPress={() => setAddType(t)}>
                <Text style={[styles.pillText, addType === t && styles.pillTextActive]}>{t === 'mcq' ? 'MCQ' : 'Short answer'}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.subLabel}>Question</Text>
          <TextInput style={[styles.input, { minHeight: 70 }]} value={addText} onChangeText={setAddText} multiline placeholder="Type the question…" placeholderTextColor={C.textHint} />
          {addType === 'mcq' ? (
            <>
              <Text style={styles.subLabel}>Options (tap the letter to mark correct)</Text>
              {addOptions.map((o, i) => (
                <View key={i} style={styles.optionEditRow}>
                  <TouchableOpacity
                    style={[styles.letterChip, addCorrect === 'ABCD'[i] && styles.letterChipActive]}
                    onPress={() => setAddCorrect('ABCD'[i])}
                  >
                    <Text style={[styles.letterText, addCorrect === 'ABCD'[i] && styles.letterTextActive]}>{'ABCD'[i]}</Text>
                  </TouchableOpacity>
                  <TextInput
                    style={[styles.input, { flex: 1 }]}
                    value={o}
                    onChangeText={v => setAddOptions(prev => prev.map((x, j) => (j === i ? v : x)))}
                    placeholder={`Option ${'ABCD'[i]}`}
                    placeholderTextColor={C.textHint}
                  />
                </View>
              ))}
            </>
          ) : (
            <>
              <Text style={styles.subLabel}>Ideal answer (shown to you when grading)</Text>
              <TextInput style={[styles.input, { minHeight: 60 }]} value={addSuggested} onChangeText={setAddSuggested} multiline placeholder="The ideal short answer…" placeholderTextColor={C.textHint} />
            </>
          )}
          <Text style={styles.subLabel}>Topic (optional)</Text>
          <TextInput style={styles.input} value={addTopic} onChangeText={setAddTopic} placeholder="e.g. Recursion" placeholderTextColor={C.textHint} />
          <View style={styles.btnRow}>
            <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => setAddVisible(false)}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={handleAddQuestion} disabled={addBusy}>
              <Text style={styles.btnPrimaryText}>{addBusy ? 'Adding…' : 'Add draft'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Sheet>

      {/* Edit-question sheet */}
      <Sheet visible={!!editTarget} onClose={() => setEditTarget(null)}>
        <View style={styles.modalBody}>
          <Text style={styles.modalTitle}>Edit question</Text>
          <Text style={styles.modalSub}>{editTarget?.type === 'mcq' ? 'MCQ' : 'Short answer'} · {editTarget?.level}</Text>
          <Text style={styles.subLabel}>Question</Text>
          <TextInput style={[styles.input, { minHeight: 70 }]} value={editText} onChangeText={setEditText} multiline />
          {editTarget?.type === 'mcq' ? (
            <>
              <Text style={styles.subLabel}>Options (tap the letter to mark correct)</Text>
              {editOptions.map((o, i) => (
                <View key={i} style={styles.optionEditRow}>
                  <TouchableOpacity
                    style={[styles.letterChip, editCorrect === o && styles.letterChipActive]}
                    onPress={() => setEditCorrect(o)}
                  >
                    <Text style={[styles.letterText, editCorrect === o && styles.letterTextActive]}>{'ABCD'[i] ?? '?'}</Text>
                  </TouchableOpacity>
                  <TextInput
                    style={[styles.input, { flex: 1 }]}
                    value={o}
                    onChangeText={v => setEditOptions(prev => prev.map((x, j) => (j === i ? v : x)))}
                  />
                </View>
              ))}
            </>
          ) : (
            <>
              <Text style={styles.subLabel}>Ideal answer</Text>
              <TextInput style={[styles.input, { minHeight: 60 }]} value={editSuggested} onChangeText={setEditSuggested} multiline />
            </>
          )}
          <View style={styles.btnRow}>
            <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => setEditTarget(null)}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={handleEditSave} disabled={editBusy}>
              <Text style={styles.btnPrimaryText}>{editBusy ? 'Saving…' : 'Save'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Sheet>
    </View>
  )
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
  emptyText: { fontSize: 13, color: C.textSub, textAlign: 'center' },
  courseRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: C.card, borderRadius: 10, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
  courseRowBody: { flex: 1 },
  courseRowCode: { fontSize: 15, fontWeight: '800', color: C.primary },
  courseRowName: { fontSize: 13, fontWeight: '700', color: C.text, marginTop: 2 },
  section: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 14,
    borderWidth: 1, borderColor: C.border,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 },
  sectionBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  sectionBadgeText: { fontSize: 12, fontWeight: '800' },
  counter: { fontSize: 11, color: C.textHint, fontWeight: '600' },
  subLabel: { fontSize: 12, fontWeight: '700', color: C.text, marginBottom: 6 },
  hintText: { fontSize: 12, color: C.textHint, lineHeight: 17, marginBottom: 10 },
  hintBold: { fontWeight: '700', color: C.textSub },
  quickInput: {
    minHeight: 60, borderWidth: 1.5, borderColor: C.border, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: C.text,
    backgroundColor: C.gray50, marginBottom: 10, textAlignVertical: 'top',
  },
  materialsHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  syncBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 5, borderRadius: 8, backgroundColor: C.blueLt },
  syncText: { fontSize: 11, fontWeight: '700', color: C.blueDk },
  materialsList: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  materialChip: {
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1.5,
    borderColor: C.border, backgroundColor: C.card, maxWidth: '100%',
  },
  materialChipActive: { borderColor: C.primary, backgroundColor: C.blueLt },
  materialChipText: { fontSize: 12, color: C.text },
  materialChipTextActive: { color: C.primary, fontWeight: '700' },
  pillRow: { marginBottom: 12 },
  pills: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  pill: {
    flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1.5, borderColor: C.border,
    alignItems: 'center', backgroundColor: C.card,
  },
  pillActive: { backgroundColor: C.primary, borderColor: C.primary },
  pillText: { fontSize: 13, fontWeight: '600', color: C.textSub },
  pillTextActive: { color: '#fff' },
  buildRow: { flexDirection: 'row', gap: 8 },
  buildBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 12, borderRadius: 10,
  },
  buildBtnText: { fontSize: 13, fontWeight: '700' },
  draftCard: {
    backgroundColor: C.gray50, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: C.border, flexDirection: 'row',
    justifyContent: 'space-between', alignItems: 'center',
  },
  draftBody: { flex: 1, marginRight: 8 },
  draftQuestion: { fontSize: 13, fontWeight: '700', color: C.text, lineHeight: 19, marginBottom: 6 },
  optionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 },
  optionChip: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 5,
    borderRadius: 8, borderWidth: 1, borderColor: C.border, backgroundColor: C.card,
  },
  optionChipCorrect: { borderColor: C.green, backgroundColor: C.greenLt },
  optionChipText: { fontSize: 11, color: C.textSub },
  optionChipTextCorrect: { color: C.greenDk, fontWeight: '700' },
  draftMeta: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  metaText: { fontSize: 11, color: C.textHint },
  draftActions: { flexDirection: 'row', gap: 6 },
  iconBtn: { padding: 6 },
  detailRow: { flexDirection: 'row', gap: 10 },
  detailCol: { flex: 1, marginBottom: 10 },
  input: {
    height: 44, borderWidth: 1.5, borderColor: C.border, borderRadius: 10,
    paddingHorizontal: 12, fontSize: 14, color: C.text, backgroundColor: C.card,
    marginBottom: 10,
  },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 2 },
  btnRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  btn: { flex: 1, ...BUTTON },
  btnPrimary: { backgroundColor: C.primary },
  btnOutline: { borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card },
  btnDisabled: { backgroundColor: C.gray100 },
  btnPrimaryText: { fontSize: 15, fontWeight: '700', color: '#fff' },
  btnOutlineText: { fontSize: 15, fontWeight: '600', color: C.text },
  optionEditRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  letterChip: {
    width: 34, height: 34, borderRadius: 8, borderWidth: 1.5, borderColor: C.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.card,
  },
  letterChipActive: { backgroundColor: C.green, borderColor: C.green },
  letterText: { fontSize: 13, fontWeight: '800', color: C.textSub },
  letterTextActive: { color: '#fff' },
  handle: { width: 40, height: 4, backgroundColor: C.gray300, borderRadius: 2, alignSelf: 'center', marginBottom: 14 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 20, paddingTop: 12, maxHeight: Dimensions.get('window').height * 0.85,
  },
  modalBody: { paddingVertical: 8, paddingBottom: 24 },
  modalTitle: { fontSize: 18, fontWeight: '800', color: C.text, marginBottom: 4 },
  modalSub: { fontSize: 13, color: C.textSub, marginBottom: 12 },
})
