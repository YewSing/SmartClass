import { useState, useEffect, useCallback, useRef } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, TextInput,
  Switch, Modal, FlatList, Dimensions, Alert,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  getClasses, getMaterials, syncMaterials, getQuizDrafts,
  editQuizQuestion, approveQuizQuestion, deleteQuizQuestion,
  createQuizQuestion, quickAddQuiz, publishQuiz, saveQuizDraft,
  updateQuizDraft, publishQuizDraft,
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

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAY_NAMES = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

/** Number input with −/+ stepper buttons (still typeable). */
function NumberField({ value, onChange, min = 1, max = 999, step = 1, testID }) {
  const clamp = (v) => Math.max(min, Math.min(max, v))
  const bump = (dir) => {
    const cur = parseInt(value, 10)
    onChange(String(clamp((Number.isNaN(cur) ? min : cur) + dir * step)))
  }
  return (
    <View style={styles.numRow}>
      <TouchableOpacity style={styles.stepBtn} onPress={() => bump(-1)} testID={testID ? `${testID}-dec` : undefined}>
        <Ionicons name="remove" size={16} color={C.text} />
      </TouchableOpacity>
      <TextInput
        style={styles.inputNum}
        value={value}
        onChangeText={onChange}
        keyboardType="number-pad"
        testID={testID}
      />
      <TouchableOpacity style={styles.stepBtn} onPress={() => bump(1)} testID={testID ? `${testID}-inc` : undefined}>
        <Ionicons name="add" size={16} color={C.text} />
      </TouchableOpacity>
    </View>
  )
}

/** Date-time field with a calendar picker modal (+ quick chips) — pure RN, works on web. */
function DateTimeField({ value, onChange, testID }) {
  const [open, setOpen] = useState(false)
  const parsed = value ? new Date(value) : null
  const [viewMonth, setViewMonth] = useState(() => parsed ?? new Date())
  const [sel, setSel] = useState(() => parsed ?? new Date())

  const openPicker = () => {
    const base = value ? new Date(value) : new Date()
    setSel(base)
    setViewMonth(base)
    setOpen(true)
  }

  const firstWeekday = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), 1).getDay()
  const daysInMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 0).getDate()
  const sameDay = (a, b) => a && b && a.toDateString() === b.toDateString()

  const shiftMonth = (dir) => setViewMonth(new Date(viewMonth.getFullYear(), viewMonth.getMonth() + dir, 1))
  const bumpMinutes = (delta) => {
    const next = new Date(sel)
    next.setMinutes(next.getMinutes() + delta)
    setSel(next)
  }
  const bumpHours = (delta) => {
    const next = new Date(sel)
    next.setHours(next.getHours() + delta)
    setSel(next)
  }
  const quick = (make) => {
    const next = make()
    setSel(next)
    setViewMonth(next)
  }

  const confirm = () => { onChange(dtLocal(sel)); setOpen(false) }
  const clear = () => { onChange(''); setOpen(false) }

  return (
    <View>
      <TouchableOpacity style={styles.dateBtn} onPress={openPicker} testID={testID}>
        <Ionicons name="calendar-outline" size={15} color={C.yellowDk} />
        <Text style={[styles.dateBtnText, !value && { color: C.textHint }]}>
          {value ? dtLocal(parsed).replace('T', ' ') : 'not set'}
        </Text>
      </TouchableOpacity>

      <Modal visible={open} animationType="slide" transparent onRequestClose={() => setOpen(false)}>
        <View style={styles.overlay}>
          <View style={styles.pickerSheet}>
            {/* quick chips */}
            <View style={styles.chipRow}>
              {[
                ['Now', () => new Date()],
                ['+15 min', () => new Date(Date.now() + 15 * 60000)],
                ['+1 hour', () => new Date(Date.now() + 60 * 60000)],
                ['Tomorrow', () => { const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(8, 0, 0, 0); return d }],
                ['+2 days', () => { const d = new Date(); d.setDate(d.getDate() + 2); return d }],
                ['+7 days', () => { const d = new Date(); d.setDate(d.getDate() + 7); return d }],
              ].map(([label, make]) => (
                <TouchableOpacity key={label} style={styles.quickChip} onPress={() => quick(make)}>
                  <Text style={styles.quickChipText}>{label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* month header */}
            <View style={styles.monthRow}>
              <TouchableOpacity style={styles.stepBtn} onPress={() => shiftMonth(-1)}>
                <Ionicons name="chevron-back" size={16} color={C.text} />
              </TouchableOpacity>
              <Text style={styles.monthLabel}>
                {MONTH_NAMES[viewMonth.getMonth()]} {viewMonth.getFullYear()}
              </Text>
              <TouchableOpacity style={styles.stepBtn} onPress={() => shiftMonth(1)}>
                <Ionicons name="chevron-forward" size={16} color={C.text} />
              </TouchableOpacity>
            </View>

            {/* day grid */}
            <View style={styles.weekRow}>
              {DAY_NAMES.map((d, i) => <Text key={i} style={styles.weekDay}>{d}</Text>)}
            </View>
            <View style={styles.grid}>
              {Array.from({ length: firstWeekday }).map((_, i) => <View key={`b${i}`} style={styles.dayCell} />)}
              {Array.from({ length: daysInMonth }).map((_, i) => {
                const day = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), i + 1)
                const on = sameDay(day, sel)
                return (
                  <TouchableOpacity key={i} style={[styles.dayCell, on && styles.dayCellOn]} onPress={() => setSel(new Date(day))}>
                    <Text style={[styles.dayText, on && styles.dayTextOn]}>{i + 1}</Text>
                  </TouchableOpacity>
                )
              })}
            </View>

            {/* time steppers */}
            <View style={styles.timeRow}>
              <View style={styles.timeGroup}>
                <Text style={styles.subLabel}>Hour</Text>
                <View style={styles.timeSteppers}>
                  <TouchableOpacity style={styles.stepBtnSm} onPress={() => bumpHours(-1)}>
                    <Ionicons name="remove" size={13} color={C.text} />
                  </TouchableOpacity>
                  <Text style={styles.timeValue}>{String(sel.getHours()).padStart(2, '0')}</Text>
                  <TouchableOpacity style={styles.stepBtnSm} onPress={() => bumpHours(1)}>
                    <Ionicons name="add" size={13} color={C.text} />
                  </TouchableOpacity>
                </View>
              </View>
              <View style={styles.timeGroup}>
                <Text style={styles.subLabel}>Minute</Text>
                <View style={styles.timeSteppers}>
                  <TouchableOpacity style={styles.stepBtnSm} onPress={() => bumpMinutes(-5)}>
                    <Ionicons name="remove" size={13} color={C.text} />
                  </TouchableOpacity>
                  <Text style={styles.timeValue}>{String(sel.getMinutes()).padStart(2, '0')}</Text>
                  <TouchableOpacity style={styles.stepBtnSm} onPress={() => bumpMinutes(5)}>
                    <Ionicons name="add" size={13} color={C.text} />
                  </TouchableOpacity>
                </View>
              </View>
            </View>

            <View style={styles.btnRow}>
              <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={clear}>
                <Text style={styles.btnOutlineText}>Clear</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => setOpen(false)}>
                <Text style={styles.btnOutlineText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={confirm}>
                <Text style={styles.btnPrimaryText}>Set</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  )
}

export default function CreateQuiz({ navigation, route }) {
  const { showToast } = useLecturer()
  const { courseId: paramCourseId, courseCode, courseName, draftQuiz: draftQuizParam } = (route?.params ?? {})
  const draftQuiz = draftQuizParam ?? null
  const draftQuizId = draftQuiz?.id ?? null

  const [currentDraftQuizId, setCurrentDraftQuizId] = useState(draftQuizId)

  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [courseId, setCourseId] = useState(paramCourseId ?? draftQuiz?.course_id)
  const [courseCodeState, setCourseCodeState] = useState(courseCode)
  const [courseNameState, setCourseNameState] = useState(courseName)

  const [drafts, setDrafts] = useState([])
  const [draftsLoading, setDraftsLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)

  // One AI drafting sheet: materials (optional) + natural-language prompt + level.
  // With materials selected the AI grounds the questions in them; with none it drafts
  // from the prompt + level alone.
  const [aiVisible, setAiVisible] = useState(false)
  const [materials, setMaterials] = useState([])
  const [materialsLoading, setMaterialsLoading] = useState(false)
  const [selectedMaterials, setSelectedMaterials] = useState([])
  const [genLevel, setGenLevel] = useState('beginner')
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

  // Editing an existing draft quiz set — prefill the details from it
  const leaveAllowed = useRef(false)
  const handlersRef = useRef({})
  useEffect(() => {
    if (!draftQuiz) return
    setQuizTitle(draftQuiz.title ?? '')
    if (draftQuiz.time_limit_minutes) setTimeLimit(String(draftQuiz.time_limit_minutes))
    if (draftQuiz.opens_at) setOpensAt(dtLocal(new Date(draftQuiz.opens_at)))
    if (draftQuiz.closes_at) setClosesAt(dtLocal(new Date(draftQuiz.closes_at)))
    setAttempts(String(draftQuiz.attempts_allowed ?? 1))
    setReviewVisible(draftQuiz.review_visible !== false)
    if (draftQuiz.course_id != null) {
      setCourseId(draftQuiz.course_id)
      setTargetIds([draftQuiz.course_id])
    }
  }, [draftQuizId])

  const loadDrafts = useCallback(async (id = courseId, qid = currentDraftQuizId) => {
    if (!id) return
    setDraftsLoading(true)
    try {
      const opts = qid != null ? { quizId: qid } : { unlinkedOnly: true }
      const list = await getQuizDrafts(id, opts)
      setDrafts(list)
    } catch (e) { setError(e.message) }
    finally { setDraftsLoading(false) }
  }, [courseId, currentDraftQuizId])

  const loadMaterials = useCallback(async (id = courseId) => {
    if (!id) return
    setMaterialsLoading(true)
    try {
      const list = await getMaterials(id)
      setMaterials(list)
      setSelectedMaterials(list.map(m => m.id))
    } catch (e) { /* materials may not be indexed yet */ }
    finally { setMaterialsLoading(false) }
  }, [courseId])

  // pick a class inside the Draft-with-AI sheet (no separate chooser page)
  const selectCourse = useCallback((c) => {
    setCourseId(c.course_id)
    setCourseCodeState(c.code)
    setCourseNameState(c.name)
    setTargetIds([c.course_id])
    loadDrafts(c.course_id)
    loadMaterials(c.course_id)
  }, [loadDrafts, loadMaterials])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const list = await getClasses()
        if (cancelled) return
        setCourses(list)
        if (!paramCourseId && list.length > 0) {
          const first = list[0]
          setCourseId(first.course_id)
          setCourseCodeState(first.code)
          setCourseNameState(first.name)
          setTargetIds([first.course_id])
        }
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [paramCourseId])

  useEffect(() => {
    let cancelled = false
    if (courseId) loadDrafts().then(() => { if (!cancelled) setLoading(false) })
    else setLoading(false)
    return () => { cancelled = true }
  }, [courseId, loadDrafts])

  // Warn before leaving an unsaved builder session (draft sets are edited in place,
  // so only a brand-new session with questions is at risk of losing work).
  const dirty = !loading && !currentDraftQuizId && drafts.length > 0
  useEffect(() => {
    if (!dirty) return
    const unsub = navigation.addListener('beforeRemove', (e) => {
      if (leaveAllowed.current) return
      e.preventDefault()
      const action = e.data.action
      if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
        if (window.confirm('Leave the quiz builder? This session will not be saved — save as a draft if you want to edit it later.')) {
          leaveAllowed.current = true
          navigation.dispatch(action)
        }
        return
      }
      Alert.alert(
        'Leave quiz builder?',
        'This create-quiz session will not be saved. Save it as a draft if you want to edit it later.',
        [
          { text: 'Stay', style: 'cancel' },
          { text: 'Save as draft', onPress: () => handlersRef.current.saveDraft?.(action) },
          { text: 'Leave without saving', style: 'destructive', onPress: () => { leaveAllowed.current = true; navigation.dispatch(action) } },
        ],
      )
    })
    return unsub
  }, [dirty, navigation])

  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title="Create Quiz" />
        <View style={styles.loading}>
          <ActivityIndicator size="large" color={C.primary} />
          <Text style={styles.loadingText}>Loading…</Text>
        </View>
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
      setAiVisible(false)
      if (quiz?.id) {
        setCurrentDraftQuizId(quiz.id)
        await loadDrafts(courseId, quiz.id)
      } else {
        await loadDrafts()
      }
      if (quiz.time_limit_minutes) setTimeLimit(String(quiz.time_limit_minutes))
      if (quiz.title) setQuizTitle(quiz.title)
      if (quiz.closes_at) setClosesAt(dtLocal(new Date(quiz.closes_at)))
      showToast('AI drafted the quiz — review the questions below', 'success')
    } catch (e) {
      let msg
      if (e?.status === 503) {
        msg = 'The AI service is unavailable right now — check the backend LLM configuration (LLM_API_KEY) or try again later'
      } else if (e?.status === 502) {
        msg = 'The AI returned a malformed answer — please try again'
      } else if (e?.status === 422) {
        // FastAPI validation errors come back as an array — show something readable
        msg = typeof e.message === 'string' && !e.message.startsWith('[')
          ? e.message
          : 'Could not read that instruction — try e.g. "create 5 mcq, 2 short answer, duration 15min, valid two days from now"'
      } else {
        msg = e.message || 'Could not build the quiz from that instruction'
      }
      showToast(msg, 'error')
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

  const handleSaveDraft = async (afterAction) => {
    if (finishBusy || drafts.length === 0) return
    setFinishBusy(true)
    try {
      await saveQuizDraft({
        question_ids: drafts.map(d => d.id),
        ...detailsPayload(),
      })
      showToast('Saved as draft — find it under Draft on the Quiz page', 'success')
      leaveAllowed.current = true
      if (afterAction) navigation.dispatch(afterAction)
      else navigation.goBack()
    } catch (e) {
      showToast(e.message || 'Could not save draft', 'error')
    } finally {
      setFinishBusy(false)
    }
  }

  const handleUpdateDraft = async () => {
    if (finishBusy || !currentDraftQuizId) return
    setFinishBusy(true)
    try {
      await updateQuizDraft(currentDraftQuizId, detailsPayload())
      showToast('Draft updated', 'success')
      leaveAllowed.current = true
      navigation.goBack()
    } catch (e) {
      showToast(e.message || 'Could not update draft', 'error')
    } finally {
      setFinishBusy(false)
    }
  }

  const handlePublishDraft = async () => {
    if (finishBusy || !currentDraftQuizId || !canFinish) return
    setFinishBusy(true)
    try {
      const created = await publishQuizDraft(currentDraftQuizId)
      showToast(`Quiz published to ${created.length} class${created.length !== 1 ? 'es' : ''}`, 'success')
      leaveAllowed.current = true
      navigation.navigate('LiveResults', {
        quizId: created[0].id, courseId: created[0].course_id,
        courseCode: courseCodeState, courseName: courseNameState,
      })
    } catch (e) {
      showToast(e.message || 'Could not publish draft', 'error')
    } finally {
      setFinishBusy(false)
    }
  }
  handlersRef.current = { saveDraft: handleSaveDraft }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Create Quiz"
        sub={courseCodeState ? `${courseCodeState} · ${courseNameState ?? ''}` : undefined}
        onBack={() => navigation.goBack()}
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>

        {/* 1 — build: one AI drafting button + manual add */}
        <Section tint="purple" badge="Build questions">
          <Text style={styles.hintText}>
            <Text style={styles.hintBold}>Draft with AI</Text> walks you through picking materials (optional), describing the quiz in your own words and a level — then drafts the questions and fills the details. Or add questions by hand.
          </Text>
          <View style={styles.buildRow}>
            <TouchableOpacity style={[styles.buildBtn, { backgroundColor: C.blueLt }]} onPress={() => { loadMaterials(); setAiVisible(true) }} testID="quiz-generate">
              <Ionicons name="sparkles-outline" size={16} color={C.blueDk} />
              <Text style={[styles.buildBtnText, { color: C.blueDk }]}>Draft with AI</Text>
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
                    <Text style={styles.idealAnswer} numberOfLines={3}>Ideal answer: {d.suggested_answer}</Text>
                  )}
                </View>
                <View style={styles.draftMeta}>
                  <Badge variant={d.status === 'approved' ? 'green' : 'gray'}>{d.status.charAt(0).toUpperCase() + d.status.slice(1)}</Badge>
                  <Text style={styles.metaText}>{d.type === 'mcq' ? 'MCQ' : 'Short answer'} · {d.level} · {d.topic || '—'}</Text>
                </View>
              </View>
              <View style={styles.draftActions}>
                {d.status !== 'deleted' && (
                  <>
                    <TouchableOpacity style={styles.iconBtn} onPress={() => openEdit(d)} testID={`quiz-edit-${d.id}`}>
                      <Ionicons name="create-outline" size={16} color={C.primary} />
                    </TouchableOpacity>
                    {d.status === 'draft' ? (
                      <TouchableOpacity style={styles.iconBtn} onPress={() => { approveQuizQuestion(d.id).then(() => loadDrafts()).then(() => showToast('Approved', 'success')).catch(e => showToast(e.message, 'error')) }} testID={`quiz-approve-${d.id}`}>
                        <Ionicons name="checkmark-outline" size={16} color={C.green} />
                      </TouchableOpacity>
                    ) : (
                      <TouchableOpacity style={styles.iconBtn} onPress={() => { approveQuizQuestion(d.id).then(() => loadDrafts()).then(() => showToast('Approval reverted — question back to draft', 'info')).catch(e => showToast(e.message, 'error')) }} testID={`quiz-unapprove-${d.id}`}>
                        <Ionicons name="arrow-undo-outline" size={16} color={C.orange} />
                      </TouchableOpacity>
                    )}
                    <TouchableOpacity style={styles.iconBtn} onPress={() => { deleteQuizQuestion(d.id).then(() => loadDrafts()).catch(e => showToast(e.message, 'error')) }} testID={`quiz-delete-${d.id}`}>
                      <Ionicons name="trash-outline" size={16} color={C.red} />
                    </TouchableOpacity>
                  </>
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
              <NumberField value={timeLimit} onChange={setTimeLimit} min={1} max={600} testID="quiz-timelimit" />
            </View>
            <View style={styles.detailCol}>
              <Text style={styles.subLabel}>Attempts allowed</Text>
              <NumberField value={attempts} onChange={setAttempts} min={1} max={10} testID="quiz-attempts" />
            </View>
          </View>
          <View style={styles.detailRow}>
            <View style={styles.detailCol}>
              <Text style={styles.subLabel}>Open</Text>
              <DateTimeField value={opensAt} onChange={setOpensAt} testID="quiz-opens" />
            </View>
            <View style={styles.detailCol}>
              <Text style={styles.subLabel}>Close</Text>
              <DateTimeField value={closesAt} onChange={setClosesAt} testID="quiz-closes" />
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
            {currentDraftQuizId ? (
              <>
                <TouchableOpacity
                  style={[styles.btn, styles.btnOutline]}
                  onPress={handleUpdateDraft}
                  disabled={finishBusy}
                  testID="quiz-update-draft"
                >
                  <Ionicons name="save-outline" size={16} color={C.text} />
                  <Text style={styles.btnOutlineText}>Save changes</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.btn, styles.btnPrimary, !canFinish && styles.btnDisabled]}
                  onPress={handlePublishDraft}
                  disabled={finishBusy || !canFinish}
                  testID="quiz-publish"
                >
                  <Ionicons name="send-outline" size={16} color="#fff" />
                  <Text style={styles.btnPrimaryText}>{finishBusy ? 'Working…' : 'Publish'}</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <TouchableOpacity
                  style={[styles.btn, styles.btnOutline]}
                  onPress={() => handleSaveDraft()}
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
              </>
            )}
          </View>
        </Section>

        <View style={{ height: 24 }} />
      </ScrollView>

      {/* Draft with AI — one flow: materials (optional) + prompt + level */}
      <Sheet visible={aiVisible} onClose={() => setAiVisible(false)}>
        <View style={styles.modalBody}>
          <Text style={styles.modalTitle}>Draft with AI</Text>
          <Text style={styles.modalSub}>
            Pick the class and (optionally) materials to ground the questions in them — or leave the materials unselected and the AI drafts from your message alone.
          </Text>

          {/* class picker — decides which course's materials show below */}
          <Text style={styles.subLabel}>Class</Text>
          <View style={styles.materialsList}>
            {courses.map(c => (
              <TouchableOpacity
                key={c.id}
                style={[styles.materialChip, courseId === c.course_id && styles.materialChipActive]}
                onPress={() => selectCourse(c)}
                testID={`ai-class-${c.course_id}`}
              >
                <Text style={[styles.materialChipText, courseId === c.course_id && styles.materialChipTextActive]}>{c.code}</Text>
              </TouchableOpacity>
            ))}
          </View>

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
            <Text style={styles.hintText}>No indexed materials yet — press “Sync Moodle”, or just write your message below.</Text>
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

          <Text style={styles.subLabel}>Your message</Text>
          <TextInput
            style={styles.quickInput}
            value={quickPrompt}
            onChangeText={setQuickPrompt}
            placeholder="create 5 mcq, 2 short answer, duration 15min, valid two days from now"
            placeholderTextColor={C.textHint}
            multiline
            testID="quiz-quick-prompt"
          />

          <Text style={styles.subLabel}>Level</Text>
          <View style={styles.pills}>
            {['beginner', 'intermediate', 'advanced'].map(l => (
              <TouchableOpacity key={l} style={[styles.pill, genLevel === l && styles.pillActive]} onPress={() => setGenLevel(l)}>
                <Text style={[styles.pillText, genLevel === l && styles.pillTextActive]}>{l.charAt(0).toUpperCase() + l.slice(1)}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.btnRow}>
            <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => setAiVisible(false)}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
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
    maxWidth: '100%',
  },
  optionChipCorrect: { borderColor: C.green, backgroundColor: C.greenLt },
  optionChipText: { fontSize: 11, color: C.textSub, flexShrink: 1 },
  optionChipTextCorrect: { color: C.greenDk, fontWeight: '700' },
  idealAnswer: {
    fontSize: 11, fontWeight: '700', color: C.greenDk, lineHeight: 16,
    backgroundColor: C.greenLt, borderRadius: 8, padding: 8, marginBottom: 6,
  },
  draftMeta: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  metaText: { fontSize: 11, color: C.textHint },
  draftActions: { flexDirection: 'row', gap: 6 },
  iconBtn: { padding: 6 },
  detailRow: { flexDirection: 'row', gap: 8 },
  detailCol: { flex: 1, minWidth: 0, marginBottom: 10 },
  numRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 10 },
  stepBtn: {
    width: 28, height: 32, borderRadius: 8, borderWidth: 1.5, borderColor: C.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.card,
  },
  stepBtnSm: {
    width: 26, height: 26, borderRadius: 7, borderWidth: 1.2, borderColor: C.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.card,
  },
  inputNum: {
    flex: 1, height: 34, borderWidth: 1.5, borderColor: C.border, borderRadius: 8,
    paddingHorizontal: 10, fontSize: 14, color: C.text, backgroundColor: C.card, textAlign: 'center',
  },
  dateBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, height: 34, paddingHorizontal: 10,
    borderWidth: 1.5, borderColor: C.border, borderRadius: 8, backgroundColor: C.card,
    marginBottom: 10, alignSelf: 'flex-start', minWidth: 150,
  },
  dateBtnText: { fontSize: 13, fontWeight: '600', color: C.text },
  pickerSheet: {
    backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 20, paddingTop: 14, paddingBottom: 24,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 },
  quickChip: {
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8,
    backgroundColor: C.blueLt, borderWidth: 1, borderColor: C.blueLt,
  },
  quickChipText: { fontSize: 11, fontWeight: '700', color: C.blueDk },
  monthRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  monthLabel: { fontSize: 15, fontWeight: '800', color: C.text },
  weekRow: { flexDirection: 'row', marginBottom: 2 },
  weekDay: { flex: 1, textAlign: 'center', fontSize: 11, fontWeight: '700', color: C.textHint },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  dayCell: {
    width: `${100 / 7}%`, alignItems: 'center', justifyContent: 'center',
    height: 34, borderRadius: 8,
  },
  dayCellOn: { backgroundColor: C.primary },
  dayText: { fontSize: 13, color: C.text },
  dayTextOn: { color: '#fff', fontWeight: '800' },
  timeRow: { flexDirection: 'row', gap: 24, marginVertical: 12 },
  timeGroup: { alignItems: 'flex-start' },
  timeSteppers: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  timeValue: { fontSize: 16, fontWeight: '800', color: C.text, minWidth: 28, textAlign: 'center' },
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
