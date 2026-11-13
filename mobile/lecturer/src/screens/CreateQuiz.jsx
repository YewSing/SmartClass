// Module 6 — AI-Powered Quiz creation (FR-601..FR-605).
// Step 1: pick materials via a picker modal (handles many materials cleanly),
//         choose question type, and set any custom question count → generate.
// Step 2: review, edit question text / options / answers / suggested answers
//         (FR-604), then Save as Draft, Push to selected classes, or Push as
//         a Live QnA inside an open Interact session.
// Frontend-only: generation is simulated locally until M6/M8 are wired.
import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, Modal,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { GENERATED_QUESTIONS } from '../data/module2'
import { C } from '../theme'

const MATERIALS = [
  { id: 'm1', name: 'Week 8 — Scrum Framework', type: 'PDF', pages: '24 pages' },
  { id: 'm2', name: 'Week 9 — UML Diagrams', type: 'PPTX', pages: '38 slides' },
  { id: 'm3', name: 'Week 10 — Normalization', type: 'PDF', pages: '19 pages' },
  { id: 'm4', name: 'Week 11 — Estimation', type: 'DOCX', pages: '12 pages' },
  { id: 'm5', name: 'Week 12 — Testing Basics', type: 'PPTX', pages: '31 slides' },
  { id: 'm6', name: 'Lab 6 — Sprint Simulation', type: 'PDF', pages: '9 pages' },
  { id: 'm7', name: 'Week 13 — Deployment', type: 'PDF', pages: '16 pages' },
  { id: 'm8', name: 'Reading — Agile Estimation (extra)', type: 'PDF', pages: '5 pages' },
]

const CLASSES = [
  { id: 'c1', code: 'WIF3001', label: 'WIF3001 · Lecture 12' },
  { id: 'c2', code: 'WIA2004', label: 'WIA2004 · Lecture 11' },
  { id: 'c3', code: 'WIA2005', label: 'WIA2005 · Tutorial 5' },
]

const STATUS_BADGE = { approved: 'green', pending: 'yellow', rejected: 'red' }

export default function CreateQuiz({ navigation }) {
  const [step, setStep] = useState(1)
  const [selected, setSelected] = useState([])            // FR-601 materials
  const [materialPickerOpen, setMaterialPickerOpen] = useState(false)
  const [materialSearch, setMaterialSearch] = useState('')
  const [qType, setQType] = useState('mcq')
  const [customCount, setCustomCount] = useState('4')     // FR-601 — lecturer-defined
  const [generating, setGenerating] = useState(false)
  const [questions, setQuestions] = useState([])
  const [publishOpen, setPublishOpen] = useState(false)   // publish action sheet

  const [timeLimit, setTimeLimit] = useState('20 min')
  const [opensAt, setOpensAt] = useState('')
  const [closesAt, setClosesAt] = useState('')
  const [pushClasses, setPushClasses] = useState([])

  const filteredMaterials = MATERIALS.filter(m =>
    m.name.toLowerCase().includes(materialSearch.toLowerCase())
  )

  const toggleMaterial = id =>
    setSelected(s => (s.includes(id) ? s.filter(x => x !== id) : [...s, id]))

  const count = parseInt(customCount, 10)

  const generate = () => {
    if (!selected.length || !count || count < 1) return
    setGenerating(true)
    // Simulated LLM generation (FR-602) — replaced by an API call later.
    setTimeout(() => {
      const pool = GENERATED_QUESTIONS.filter(q =>
        qType === 'mixed' ? true : q.type === qType
      )
      const drafts = Array.from({ length: count }, (_, i) => {
        const src = pool[i % pool.length] ?? GENERATED_QUESTIONS[0]
        return { ...src, status: 'pending', id: `g${Date.now()}-${i}` }
      })
      setQuestions(drafts)
      setGenerating(false)
      setStep(2)
    }, 900)
  }

  // FR-604 — inline editing of every AI-generated detail
  const editQuestion = (id, text) =>
    setQuestions(qs => qs.map(q => (q.id === id ? { ...q, text } : q)))
  const editOption = (qid, oi, text) =>
    setQuestions(qs => qs.map(q => q.id === qid
      ? { ...q, options: q.options.map((o, j) => (j === oi ? text : o)) }
      : q))
  const editSuggested = (id, text) =>
    setQuestions(qs => qs.map(q => (q.id === id ? { ...q, suggested: text } : q)))
  const setCorrect = (qid, oi) =>
    setQuestions(qs => qs.map(q => (q.id === qid ? { ...q, correct: oi } : q)))
  const setStatus = (id, status) =>
    setQuestions(qs => qs.map(q => (q.id === id ? { ...q, status } : q)))
  const removeQuestion = id => setQuestions(qs => qs.filter(q => q.id !== id))
  const addOption = qid =>
    setQuestions(qs => qs.map(q => q.id === qid
      ? { ...q, options: [...(q.options ?? []), ''] } : q))
  const removeOption = (qid, oi) =>
    setQuestions(qs => qs.map(q => q.id === qid
      ? { ...q, options: q.options.filter((_, j) => j !== oi), correct: q.correct >= oi && q.correct > 0 ? q.correct - 1 : q.correct }
      : q))

  const approvedCount = questions.filter(q => q.status === 'approved').length
  const selectedNames = MATERIALS.filter(m => selected.includes(m.id))

  const togglePushClass = id =>
    setPushClasses(s => (s.includes(id) ? s.filter(x => x !== id) : [...s, id]))

  // ─── Step 1 — setup ──────────────────────────────────────────────────────────
  if (step === 1) {
    return (
      <View style={styles.flex}>
        <Topbar title="Generate Quiz" sub="Step 1 of 2 — choose source & settings" onBack={() => navigation.goBack()} />
        <ScrollView style={styles.flex} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.aiBanner}>
            <Ionicons name="sparkles" size={16} color={C.primary} />
            <Text style={styles.aiBannerText}>
              Questions are generated from your course materials with topic & source tags (FR-602/603).
            </Text>
          </View>

          {/* 1 · Materials — opens picker modal so many materials stay tidy */}
          <Text style={styles.label}>1 · Select materials</Text>
          <TouchableOpacity
            style={[styles.materialPickerBtn, selected.length > 0 && styles.materialPickerBtnOn]}
            onPress={() => setMaterialPickerOpen(true)}
          >
            <View style={styles.materialPickerLeft}>
              <Ionicons name="folder-open" size={18} color={selected.length ? C.primary : C.textSub} />
              <View style={styles.materialPickerTexts}>
                <Text style={[styles.materialPickerTitle, selected.length > 0 && { color: C.primary }]}>
                  {selected.length === 0
                    ? 'Choose course materials'
                    : `${selected.length} material${selected.length !== 1 ? 's' : ''} selected`}
                </Text>
                <Text style={styles.materialPickerSub} numberOfLines={1}>
                  {selected.length === 0
                    ? 'Tap to browse — from Moodle course page'
                    : selectedNames.map(m => m.name.split('— ')[1] ?? m.name).join(', ')}
                </Text>
              </View>
            </View>
            <Ionicons name="chevron-forward" size={16} color={C.textHint} />
          </TouchableOpacity>

          {/* 2 · Question type */}
          <Text style={styles.label}>2 · Question type</Text>
          <View style={styles.typeRow}>
            {[
              ['mcq', 'Multiple-choice', 'checkmark-circle'],
              ['short', 'Short-answer', 'pencil'],
              ['mixed', 'Mixed', 'grid'],
            ].map(([id, label, icon]) => (
              <TouchableOpacity key={id} style={[styles.typeBtn, qType === id && styles.typeBtnOn]} onPress={() => setQType(id)}>
                <Ionicons name={icon} size={16} color={qType === id ? C.primary : C.textSub} />
                <Text style={[styles.typeBtnText, qType === id && { color: C.primary }]}>{label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* 3 · Custom count — lecturer defines any number */}
          <Text style={styles.label}>3 · How many questions?</Text>
          <View style={styles.countRow}>
            <TouchableOpacity
              style={styles.countStepper}
              onPress={() => setCustomCount(String(Math.max(1, (parseInt(customCount, 10) || 1) - 1)))}
            >
              <Ionicons name="remove" size={16} color={C.text} />
            </TouchableOpacity>
            <TextInput
              style={styles.countInput}
              value={customCount}
              onChangeText={t => setCustomCount(t.replace(/[^0-9]/g, ''))}
              keyboardType="number-pad"
              maxLength={3}
              textAlign="center"
            />
            <TouchableOpacity
              style={styles.countStepper}
              onPress={() => setCustomCount(String(Math.min(99, (parseInt(customCount, 10) || 0) + 1)))}
            >
              <Ionicons name="add" size={16} color={C.text} />
            </TouchableOpacity>
            {count >= 1 && (
              <Text style={styles.countNote}>≈ {Math.max(1, Math.ceil(count * 0.8))}–{count} min to answer</Text>
            )}
          </View>

          <TouchableOpacity
            style={[styles.generateBtn, (!selected.length || generating || !count) && styles.btnDisabled]}
            onPress={generate}
            disabled={!selected.length || generating || !count}
          >
            <Ionicons name="sparkles" size={16} color="#fff" />
            <Text style={styles.generateBtnText}>
              {generating ? 'Generating with AI…' : `Generate ${count || '—'} question${count === 1 ? '' : 's'}`}
            </Text>
          </TouchableOpacity>
          {generating && <Text style={styles.genNote}>Reading selected materials · drafting questions · tagging topics…</Text>}
          <View style={{ height: 24 }} />
        </ScrollView>

        {/* Material picker modal — searchable, multi-select, scrollable */}
        <Modal visible={materialPickerOpen} transparent animationType="slide" onRequestClose={() => setMaterialPickerOpen(false)}>
          <View style={styles.modalOverlay}>
            <View style={[styles.modalSheet, { maxHeight: '82%' }]}>
              <View style={styles.pickerHandle} />
              <Text style={styles.modalTitle}>Select Course Materials</Text>
              <Text style={styles.modalSub}>From this course's Moodle page (FR-801). Tap to include / exclude.</Text>

              <View style={styles.searchBox}>
                <Ionicons name="search" size={15} color={C.textHint} />
                <TextInput
                  style={styles.searchInput}
                  placeholder="Search materials…"
                  placeholderTextColor={C.textHint}
                  value={materialSearch}
                  onChangeText={setMaterialSearch}
                />
                {materialSearch !== '' && (
                  <TouchableOpacity onPress={() => setMaterialSearch('')}>
                    <Ionicons name="close-circle" size={16} color={C.gray300} />
                  </TouchableOpacity>
                )}
              </View>

              {selected.length > 0 && (
                <View style={styles.selectedSummary}>
                  <Text style={styles.selectedSummaryText}>{selected.length} selected</Text>
                  <TouchableOpacity onPress={() => setSelected([])}>
                    <Text style={styles.clearSelText}>Clear all</Text>
                  </TouchableOpacity>
                </View>
              )}

              <ScrollView style={styles.materialList} keyboardShouldPersistTaps="handled">
                {filteredMaterials.map(m => {
                  const on = selected.includes(m.id)
                  return (
                    <TouchableOpacity
                      key={m.id}
                      style={[styles.materialRow, on && styles.materialOn]}
                      onPress={() => toggleMaterial(m.id)}
                    >
                      <Ionicons
                        name={on ? 'checkbox' : 'square-outline'}
                        size={19}
                        color={on ? C.primary : C.gray400}
                      />
                      <View style={styles.fileChip}><Text style={styles.fileChipText}>{m.type}</Text></View>
                      <View style={styles.materialTexts}>
                        <Text style={styles.materialName} numberOfLines={1}>{m.name}</Text>
                        <Text style={styles.materialMeta}>{m.pages}</Text>
                      </View>
                    </TouchableOpacity>
                  )
                })}
                {filteredMaterials.length === 0 && (
                  <Text style={styles.noResults}>No materials match "{materialSearch}".</Text>
                )}
                <View style={{ height: 10 }} />
              </ScrollView>

              <View style={styles.modalBtnRow}>
                <TouchableOpacity style={styles.modalCancel} onPress={() => setMaterialPickerOpen(false)}>
                  <Text style={styles.modalCancelText}>Done{selected.length ? ` (${selected.length})` : ''}</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      </View>
    )
  }

  // ─── Step 2 — review, edit, approve, publish ─────────────────────────────────
  return (
    <View style={styles.flex}>
      <Topbar
        title="Review Questions"
        sub={`Step 2 of 2 · ${approvedCount}/${questions.length} approved`}
        onBack={() => setStep(1)}
        right={
          <TouchableOpacity
            style={[styles.publishBtn, approvedCount === 0 && styles.btnDisabled]}
            onPress={() => setPublishOpen(true)}
            disabled={approvedCount === 0}
          >
            <Text style={styles.publishBtnText}>Next</Text>
          </TouchableOpacity>
        }
      />
      <ScrollView style={styles.flex} contentContainerStyle={styles.content}>
        <View style={styles.editHintBanner}>
          <Ionicons name="create-outline" size={14} color={C.primary} />
          <Text style={styles.editHintText}>
            Tap any text to edit — question, options, correct answer and AI-suggested answers (FR-604).
          </Text>
        </View>

        {questions.map((q, i) => (
          <View key={q.id} style={[styles.qCard, q.status === 'rejected' && styles.qCardRejected]}>
            <View style={styles.qTop}>
              <Text style={styles.qNum}>Q{i + 1}</Text>
              <Badge variant={STATUS_BADGE[q.status]}>
                {q.status === 'approved' ? 'Approved' : q.status === 'rejected' ? 'Rejected' : 'Pending review'}
              </Badge>
            </View>

            {/* Source & topic tags — FR-603 */}
            <View style={styles.tagRow}>
              <View style={styles.tagChip}>
                <Ionicons name="pricetag" size={9} color={C.purple} />
                <Text style={styles.tagChipText}>{q.topic}</Text>
              </View>
              <View style={[styles.tagChip, { backgroundColor: C.blueLt }]}>
                <Ionicons name="document" size={9} color={C.primary} />
                <Text style={[styles.tagChipText, { color: C.primary }]}>{q.source}</Text>
              </View>
            </View>

            {/* Question text — editable (FR-604) */}
            <Text style={styles.editLbl}>QUESTION</Text>
            <TextInput
              style={styles.qText}
              value={q.text}
              multiline
              onChangeText={t => editQuestion(q.id, t)}
              textAlignVertical="top"
            />

            {q.type === 'mcq' ? (
              <View>
                <Text style={styles.editLbl}>OPTIONS · tap ⋯ to set correct · tap ✕ to remove</Text>
                {q.options.map((opt, oi) => (
                  <View key={oi} style={[styles.optEditRow, q.correct === oi && styles.optCorrect]}>
                    <Text style={styles.optLetter}>{String.fromCharCode(65 + oi)}</Text>
                    <TextInput
                      style={styles.optEditInput}
                      value={opt}
                      onChangeText={t => editOption(q.id, oi, t)}
                      placeholder={`Option ${String.fromCharCode(65 + oi)}`}
                      placeholderTextColor={C.textHint}
                    />
                    <TouchableOpacity onPress={() => setCorrect(q.id, oi)} style={styles.correctToggle}>
                      <Ionicons name="checkmark" size={14} color={q.correct === oi ? '#fff' : C.gray400} />
                    </TouchableOpacity>
                    {q.options.length > 2 && (
                      <TouchableOpacity onPress={() => removeOption(q.id, oi)} style={styles.optDel}>
                        <Ionicons name="close" size={13} color={C.textSub} />
                      </TouchableOpacity>
                    )}
                  </View>
                ))}
                {q.options.length < 6 && (
                  <TouchableOpacity style={styles.addOptBtn} onPress={() => addOption(q.id)}>
                    <Ionicons name="add" size={13} color={C.primary} />
                    <Text style={styles.addOptText}>Add option</Text>
                  </TouchableOpacity>
                )}
              </View>
            ) : (
              <View>
                <Text style={styles.editLbl}>AI-SUGGESTED ANSWER · editable (FR-610 preview)</Text>
                <TextInput
                  style={styles.suggestedInput}
                  value={q.suggested}
                  multiline
                  onChangeText={t => editSuggested(q.id, t)}
                  textAlignVertical="top"
                />
              </View>
            )}

            {/* FR-604 — approve / reject / delete */}
            <View style={styles.qActions}>
              <TouchableOpacity
                style={[styles.qActionBtn, styles.approveBtn, q.status === 'approved' && styles.actionOnGreen]}
                onPress={() => setStatus(q.id, q.status === 'approved' ? 'pending' : 'approved')}
              >
                <Ionicons name="checkmark" size={14} color={q.status === 'approved' ? '#fff' : C.greenDk} />
                <Text style={[styles.qActionText, q.status === 'approved' && { color: '#fff' }]}>
                  {q.status === 'approved' ? 'Approved' : 'Approve'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.qActionBtn, styles.rejectBtn, q.status === 'rejected' && styles.actionOnRed]}
                onPress={() => setStatus(q.id, q.status === 'rejected' ? 'pending' : 'rejected')}
              >
                <Ionicons name="close" size={14} color={q.status === 'rejected' ? '#fff' : C.redDk} />
                <Text style={[styles.qActionText, q.status === 'rejected' && { color: '#fff' }]}>Reject</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.trashBtn} onPress={() => removeQuestion(q.id)}>
                <Ionicons name="trash-outline" size={15} color={C.textSub} />
              </TouchableOpacity>
            </View>
          </View>
        ))}

        {questions.length === 0 && (
          <View style={styles.emptyAll}>
            <Ionicons name="documents-outline" size={32} color={C.gray300} />
            <Text style={styles.emptyAllText}>All questions removed. Go back to generate again.</Text>
          </View>
        )}

        <View style={{ height: 80 }} />
      </ScrollView>

      {/* Publish action sheet — Save draft / Push to classes / Live QnA */}
      <Modal visible={publishOpen} transparent animationType="slide" onRequestClose={() => setPublishOpen(false)}>
        <View style={styles.modalOverlay}>
          <ScrollView style={styles.modalSheet} keyboardShouldPersistTaps="handled" bounces={false}>
            <View style={styles.pickerHandle} />
            <Text style={styles.modalTitle}>Publish {approvedCount} Question{approvedCount !== 1 ? 's' : ''}</Text>
            <Text style={styles.modalSub}>Choose how to deliver this quiz (FR-605).</Text>

            {/* Target classes */}
            <Text style={styles.modalLbl}>Push to which classes?</Text>
            <View style={styles.pushClassWrap}>
              {CLASSES.map(cl => {
                const on = pushClasses.includes(cl.id)
                return (
                  <TouchableOpacity
                    key={cl.id}
                    style={[styles.pushClassChip, on && styles.pushClassChipOn]}
                    onPress={() => togglePushClass(cl.id)}
                  >
                    <Ionicons
                      name={on ? 'checkbox' : 'square-outline'}
                      size={15}
                      color={on ? C.primary : C.gray400}
                    />
                    <Text style={styles.pushClassText}>{cl.code}</Text>
                  </TouchableOpacity>
                )
              })}
            </View>

            {/* Option A — save draft */}
            <TouchableOpacity style={styles.actionRow} onPress={() => { setPublishOpen(false); navigation.navigate('QuizList') }}>
              <View style={[styles.actionIcon, { backgroundColor: C.gray100 }]}>
                <Ionicons name="file-tray-full" size={17} color={C.gray600} />
              </View>
              <View style={styles.actionBody}>
                <Text style={styles.actionTitle}>Save as Draft</Text>
                <Text style={styles.actionSub}>Keep in Assessments — push later</Text>
              </View>
              <Ionicons name="chevron-forward" size={15} color={C.textHint} />
            </TouchableOpacity>

            {/* Option B — scheduled push (needs timing fields) */}
            <View style={styles.actionRow}>
              <View style={[styles.actionIcon, { backgroundColor: C.blueLt }]}>
                <Ionicons name="send" size={17} color={C.primary} />
              </View>
              <View style={styles.actionBody}>
                <Text style={styles.actionTitle}>Push as Quiz</Text>
                <Text style={styles.actionSub}>Timed attempt in the selected classes</Text>
              </View>
            </View>
            <View style={styles.timingBox}>
              <Text style={styles.modalLbl}>Time limit</Text>
              <View style={styles.timeRow}>
                {['10 min', '20 min', '30 min', '60 min'].map(t => (
                  <TouchableOpacity
                    key={t}
                    style={[styles.timeBtn, timeLimit === t && styles.timeBtnOn]}
                    onPress={() => setTimeLimit(t)}
                  >
                    <Text style={[styles.timeBtnText, timeLimit === t && { color: '#fff', fontWeight: '700' }]}>{t}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={styles.modalLbl}>Opens</Text>
              <TextInput
                style={styles.modalInput}
                placeholder="e.g. Today 5:00 PM (empty = now)"
                placeholderTextColor={C.textHint}
                value={opensAt}
                onChangeText={setOpensAt}
              />
              <Text style={styles.modalLbl}>Closes</Text>
              <TextInput
                style={styles.modalInput}
                placeholder="e.g. Fri 11:59 PM"
                placeholderTextColor={C.textHint}
                value={closesAt}
                onChangeText={setClosesAt}
              />
              <Text style={styles.modalNote}>Students get one attempt (FR-607). Attempts auto-submit when time runs out.</Text>
              <TouchableOpacity
                style={[styles.pushBtn, pushClasses.length === 0 && styles.btnDisabled]}
                disabled={pushClasses.length === 0}
                onPress={() => { setPublishOpen(false); navigation.navigate('QuizList') }}
              >
                <Ionicons name="send" size={14} color="#fff" />
                <Text style={styles.pushBtnText}>Push to {pushClasses.length || 0} class{pushClasses.length !== 1 ? 'es' : ''}</Text>
              </TouchableOpacity>
            </View>

            {/* Option C — live QnA in Interact session */}
            <View style={[styles.actionRow, { borderBottomWidth: 0 }]}>
              <View style={[styles.actionIcon, { backgroundColor: C.redLt }]}>
                <Ionicons name="pulse" size={17} color={C.red} />
              </View>
              <View style={styles.actionBody}>
                <Text style={styles.actionTitle}>Push as Live QnA</Text>
                <Text style={styles.actionSub}>Show inside an open Interact session — answers appear in real time</Text>
              </View>
            </View>
            <View style={styles.timingBox}>
              <View style={styles.liveWarnRow}>
                <Ionicons name="information-circle" size={13} color={C.primary} />
                <Text style={styles.liveWarnText}>
                  Live QnA requires an open interaction session (FR-501). Questions appear on student desks instantly, no time limit.
                </Text>
              </View>
              <TouchableOpacity
                style={[styles.liveBtn, pushClasses.length === 0 && styles.btnDisabled]}
                disabled={pushClasses.length === 0}
                onPress={() => { setPublishOpen(false); navigation.navigate('Interact') }}
              >
                <Ionicons name="pulse" size={14} color="#fff" />
                <Text style={styles.liveBtnText}>Go to Interact & push live</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.sheetCancel} onPress={() => setPublishOpen(false)}>
              <Text style={styles.sheetCancelText}>Cancel</Text>
            </TouchableOpacity>
            <View style={{ height: 8 }} />
          </ScrollView>
        </View>
      </Modal>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  aiBanner: {
    flexDirection: 'row', gap: 8, backgroundColor: C.blueLt,
    borderWidth: 1, borderColor: C.primary, borderRadius: 10,
    padding: 10, marginBottom: 16, alignItems: 'flex-start',
  },
  aiBannerText: { flex: 1, fontSize: 12, color: C.blueDk, lineHeight: 17 },
  label: { fontSize: 12, fontWeight: '700', color: C.text, marginBottom: 8, marginTop: 4 },

  /* material picker button */
  materialPickerBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderWidth: 1.5, borderColor: C.border, borderStyle: 'dashed',
    borderRadius: 12, padding: 13, backgroundColor: C.card, marginBottom: 8,
  },
  materialPickerBtnOn: { borderColor: C.primary, borderStyle: 'solid', backgroundColor: C.blueLt },
  materialPickerLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  materialPickerTexts: { flex: 1 },
  materialPickerTitle: { fontSize: 14, fontWeight: '700', color: C.textSub },
  materialPickerSub: { fontSize: 11, color: C.textHint, marginTop: 2 },

  /* type */
  typeRow: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  typeBtn: {
    flex: 1, alignItems: 'center', gap: 5, paddingVertical: 12,
    borderRadius: 10, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card,
  },
  typeBtnOn: { borderColor: C.primary, backgroundColor: C.blueLt },
  typeBtnText: { fontSize: 11, fontWeight: '600', color: C.textSub, textAlign: 'center' },

  /* custom count */
  countRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  countStepper: {
    width: 42, height: 42, borderRadius: 10, borderWidth: 1.5, borderColor: C.border,
    backgroundColor: C.card, alignItems: 'center', justifyContent: 'center',
  },
  countInput: {
    width: 64, height: 42, borderWidth: 1.5, borderColor: C.border, borderRadius: 10,
    backgroundColor: C.card, fontSize: 18, fontWeight: '800', color: C.text,
  },
  countNote: { flex: 1, fontSize: 10, color: C.textHint, textAlign: 'right' },
  generateBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: C.primary, borderRadius: 12, paddingVertical: 14, marginTop: 18,
  },
  generateBtnText: { fontSize: 15, fontWeight: '700', color: '#fff' },
  btnDisabled: { opacity: 0.45 },
  genNote: { fontSize: 11, color: C.textHint, textAlign: 'center', marginTop: 10 },

  publishBtn: { backgroundColor: C.primary, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  publishBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  editHintBanner: {
    flexDirection: 'row', gap: 8, alignItems: 'flex-start',
    backgroundColor: C.blueLt, borderRadius: 10, padding: 10, marginBottom: 12,
  },
  editHintText: { flex: 1, fontSize: 11, color: C.blueDk, lineHeight: 16 },

  /* question cards */
  qCard: {
    backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border,
    padding: 14, marginBottom: 10,
  },
  qCardRejected: { opacity: 0.6 },
  qTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  qNum: { fontSize: 12, fontWeight: '800', color: C.primary },
  tagRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginBottom: 10 },
  tagChip: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: C.purpleLt, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6,
  },
  tagChipText: { fontSize: 9, fontWeight: '700', color: C.purple },
  editLbl: {
    fontSize: 8, fontWeight: '800', color: C.textHint, letterSpacing: 0.6, marginBottom: 5,
  },
  qText: {
    fontSize: 14, fontWeight: '600', color: C.text, lineHeight: 20,
    borderWidth: 1, borderColor: C.border, borderRadius: 9,
    backgroundColor: C.gray50, padding: 10, marginBottom: 10,
  },
  optEditRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1.5, borderColor: C.border, borderRadius: 9,
    paddingLeft: 10, marginBottom: 6, backgroundColor: C.bg,
  },
  optCorrect: { borderColor: C.green, backgroundColor: C.greenLt },
  optLetter: { fontSize: 11, fontWeight: '800', color: C.gray600, width: 14 },
  optEditInput: { flex: 1, fontSize: 13, color: C.text, paddingVertical: 9 },
  correctToggle: {
    width: 30, height: 30, borderRadius: 8, backgroundColor: C.green,
    alignItems: 'center', justifyContent: 'center', marginRight: 3,
  },
  optDel: {
    width: 30, height: 30, alignItems: 'center', justifyContent: 'center', marginRight: 4,
  },
  addOptBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    alignSelf: 'flex-start', marginTop: 2, marginBottom: 8,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8,
    borderWidth: 1.5, borderColor: C.primary, borderStyle: 'dashed',
  },
  addOptText: { fontSize: 12, fontWeight: '700', color: C.primary },
  suggestedInput: {
    fontSize: 12, color: C.text, lineHeight: 17,
    borderWidth: 1, borderColor: C.border, borderRadius: 9,
    backgroundColor: C.gray50, padding: 10, marginBottom: 8, minHeight: 70,
  },
  qActions: { flexDirection: 'row', gap: 8, marginTop: 6 },
  qActionBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 9, borderRadius: 9, borderWidth: 1.5,
  },
  approveBtn: { borderColor: C.green, backgroundColor: C.greenLt },
  actionOnGreen: { backgroundColor: C.green, borderColor: C.green },
  rejectBtn: { borderColor: C.red, backgroundColor: C.redLt },
  actionOnRed: { backgroundColor: C.red, borderColor: C.red },
  qActionText: { fontSize: 12, fontWeight: '700' },
  trashBtn: {
    width: 38, alignItems: 'center', justifyContent: 'center',
    borderRadius: 9, borderWidth: 1.5, borderColor: C.border,
  },
  emptyAll: { alignItems: 'center', padding: 40, gap: 8 },
  emptyAllText: { fontSize: 13, color: C.textHint, textAlign: 'center' },

  /* modals */
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 18, paddingTop: 10, paddingBottom: 18,
  },
  pickerHandle: {
    width: 40, height: 4, borderRadius: 2, backgroundColor: C.gray300, alignSelf: 'center', marginBottom: 14,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: C.text, marginBottom: 4 },
  modalSub: { fontSize: 12, color: C.textSub, marginBottom: 12, lineHeight: 17 },
  modalLbl: { fontSize: 11, fontWeight: '700', color: C.text, marginBottom: 6, marginTop: 6 },
  searchBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1.5, borderColor: C.border, borderRadius: 10,
    backgroundColor: C.bg, paddingHorizontal: 12, paddingVertical: 9, marginBottom: 10,
  },
  searchInput: { flex: 1, fontSize: 14, color: C.text, paddingVertical: 0 },
  selectedSummary: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: C.blueLt, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, marginBottom: 8,
  },
  selectedSummaryText: { fontSize: 11, fontWeight: '800', color: C.primary },
  clearSelText: { fontSize: 11, fontWeight: '700', color: C.redDk },
  materialList: { flexGrow: 0 },
  materialRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: 1, borderColor: C.border, borderRadius: 10,
    padding: 11, marginBottom: 7, backgroundColor: C.bg,
  },
  materialOn: { borderColor: C.primary, backgroundColor: C.blueLt },
  fileChip: { backgroundColor: C.gray100, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5 },
  fileChipText: { fontSize: 9, fontWeight: '800', color: C.gray600 },
  materialTexts: { flex: 1 },
  materialName: { fontSize: 13, fontWeight: '600', color: C.text },
  materialMeta: { fontSize: 10, color: C.textHint, marginTop: 1 },
  noResults: { fontSize: 12, color: C.textHint, textAlign: 'center', paddingVertical: 20 },

  /* publish sheet */
  pushClassWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  pushClassChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderWidth: 1, borderColor: C.border, borderRadius: 9,
    paddingHorizontal: 10, paddingVertical: 8, backgroundColor: C.bg,
  },
  pushClassChipOn: { borderColor: C.primary, backgroundColor: C.blueLt },
  pushClassText: { fontSize: 12, fontWeight: '700', color: C.text },
  actionRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  actionIcon: { width: 36, height: 36, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  actionBody: { flex: 1 },
  actionTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  actionSub: { fontSize: 11, color: C.textSub, marginTop: 1, lineHeight: 15 },
  timingBox: {
    backgroundColor: C.gray50, borderWidth: 1, borderColor: C.border,
    borderRadius: 10, padding: 12, marginBottom: 4,
  },
  timeRow: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  timeBtn: {
    flex: 1, paddingVertical: 9, borderRadius: 8, borderWidth: 1.5,
    borderColor: C.border, alignItems: 'center', backgroundColor: C.card,
  },
  timeBtnOn: { backgroundColor: C.primary, borderColor: C.primary },
  timeBtnText: { fontSize: 12, fontWeight: '500', color: C.text },
  modalInput: {
    borderWidth: 1.5, borderColor: C.border, borderRadius: 10, backgroundColor: C.card,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: C.text, marginBottom: 8,
  },
  modalNote: { fontSize: 10, color: C.textHint, marginBottom: 10, lineHeight: 14 },
  pushBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 12,
  },
  pushBtnText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  liveWarnRow: { flexDirection: 'row', gap: 6, marginBottom: 10, alignItems: 'flex-start' },
  liveWarnText: { flex: 1, fontSize: 11, color: C.textSub, lineHeight: 16 },
  liveBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: C.red, borderRadius: 10, paddingVertical: 12,
  },
  liveBtnText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  sheetCancel: { alignItems: 'center', paddingVertical: 12, marginTop: 4 },
  sheetCancelText: { fontSize: 14, fontWeight: '600', color: C.textSub },
})
