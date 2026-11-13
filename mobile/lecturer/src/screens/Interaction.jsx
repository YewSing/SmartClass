// Module 5 — Classroom Interaction (lecturer view): FR-501, FR-503, FR-504,
// FR-506, FR-507, FR-508. Frontend-only with local state until M5 is wired.
import { useState } from 'react'
import {
  View, Text, ScrollView, TextInput, TouchableOpacity, StyleSheet, Modal, FlatList,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

const REACTIONS = [
  { id: 'thumbs', icon: 'thumbs-up', label: 'Good pace' },
  { id: 'slow', icon: 'speedometer', label: 'Too fast' },
  { id: 'example', icon: 'bullet-list', label: 'More examples' },
  { id: 'repeat', icon: 'repeat', label: 'Repeat that' },
]

export default function Interaction({ navigation }) {
  const [sessionOpen, setSessionOpen] = useState(false)
  const [questions, setQuestions] = useState([])          // FR-503 live feed
  const [answered, setAnswered] = useState({})
  const [newQ, setNewQ] = useState('')                     // FR-506 live question
  const [answeredLive, setAnsweredLive] = useState([])
  const [pollOpen, setPollOpen] = useState(false)          // FR-504
  const [pollQ, setPollQ] = useState('')
  const [pollOpts, setPollOpts] = useState(['', ''])
  const [activePoll, setActivePoll] = useState(null)
  const [votes, setVotes] = useState([0, 0, 0, 0])
  const [reactions, setReactions] = useState({ thumbs: 3, slow: 1, example: 2, repeat: 0 })
  const [iduCount, setIduCount] = useState(0)

  const toggleSession = () => {
    setSessionOpen(o => !o)
    if (sessionOpen) { setQuestions([]); setAnswered({}); setReactions({ thumbs: 0, slow: 0, example: 0, repeat: 0 }); setIduCount(0) }
  }

  const markAnswered = (id) => setAnswered(a => ({ ...a, [id]: true }))

  const createPoll = () => {
    const opts = pollOpts.map((o, i) => ({ text: o || `Option ${String.fromCharCode(65 + i)}` }))
    setActivePoll({ question: pollQ || 'Quick pulse check', options: opts.map(o => o.text) })
    setVotes(opts.map(() => 0))
    setPollOpen(false)
  }

  const addOption = () => setPollOpts(prev => [...prev, ''])

  const askLive = () => {
    if (!newQ.trim()) return
    setQuestions(q => [...q, { id: Date.now(), text: newQ.trim(), live: true }])
    setNewQ('')
  }

  const markLiveAnswered = (id) => setAnsweredLive(a => [...a, id])

  return (
    <View style={styles.flex}>
      <Topbar title="Interact" sub="Live classroom interaction" />

      {/* Session control — FR-501 */}
      <View style={styles.sessionRow}>
        <View style={styles.sessionInfo}>
          <Text style={styles.sessionClass}>WIF3001 · DK 6</Text>
          <Text style={styles.sessionMeta}>
            {sessionOpen ? 'Students can participate now' : 'Students cannot participate'}
          </Text>
        </View>
        <TouchableOpacity
          style={[styles.sessionBtn, sessionOpen ? styles.sessionBtnOn : styles.sessionBtnOff]}
          onPress={toggleSession}
        >
          <Ionicons name={sessionOpen ? 'stop-circle' : 'play-circle'} size={16} color="#fff" />
          <Text style={styles.sessionBtnText}>{sessionOpen ? 'Close' : 'Open'}</Text>
        </TouchableOpacity>
      </View>

      {sessionOpen && (
        <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
          {/* IDU counter — FR-508 */}
          <View style={[styles.card, iduCount >= 5 && styles.iduAlert]}>
            <View style={styles.iduRow}>
              <View>
                <Text style={styles.cardTitle}>"I Don't Understand" signals</Text>
                <Text style={styles.cardSub}>
                  {iduCount === 0
                    ? 'No signals yet — class is following'
                    : `${iduCount} student${iduCount !== 1 ? 's' : ''} need help right now`}
                </Text>
              </View>
              <Text style={[styles.iduCount, iduCount >= 5 && { color: C.red }]}>{iduCount}</Text>
            </View>
            {iduCount >= 5 && (
              <View style={styles.iduActions}>
                <TouchableOpacity style={styles.reteachBtn}>
                  <Ionicons name="refresh" size={13} color="#fff" />
                  <Text style={styles.reteachText}>Re-explain last topic</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.clearBtn} onPress={() => setIduCount(0)}>
                  <Text style={styles.clearText}>Clear</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>

          {/* Reactions — FR-507 */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Reactions</Text>
            <View style={styles.reactionRow}>
              {REACTIONS.map(r => (
                <View key={r.id} style={[styles.reactionCell, reactions[r.id] >= 5 && styles.reactionHot]}>
                  <Ionicons name={r.icon} size={16} color={reactions[r.id] >= 5 ? C.red : C.primary} />
                  <Text style={[styles.reactionNum, reactions[r.id] >= 5 && { color: C.red }]}>{reactions[r.id]}</Text>
                  <Text style={styles.reactionLbl} numberOfLines={1}>{r.label}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* Questions — FR-503 / FR-506 */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Questions ({questions.length})</Text>
              <Text style={styles.cardSub}>answered: {questions.filter(q => answered[q.id]).length}</Text>
            </View>

            {/* Ask the class a live question — FR-506 */}
            <TextInput
              style={styles.input}
              placeholder="Ask the class a live question…"
              placeholderTextColor={C.textHint}
              value={newQ}
              onChangeText={setNewQ}
            />
            <TouchableOpacity style={styles.askBtn} onPress={askLive}>
              <Ionicons name="chatbubble-send" size={13} color="#fff" />
              <Text style={styles.askBtnText}>Ask the class</Text>
            </TouchableOpacity>

            {questions.length === 0 && (
              <Text style={styles.emptyHint}>Student questions appear here in real time.</Text>
            )}
            {questions.map(q => (
              <View key={q.id} style={[styles.qRow, answered[q.id] && styles.qRowAnswered]}>
                <View style={styles.qBody}>
                  <Text style={[styles.qText, answered[q.id] && styles.qTextAnswered]}>{q.text}</Text>
                  {answered[q.id] && <Badge variant="green">Answered</Badge>}
                </View>
                {!answered[q.id] && (
                  <TouchableOpacity style={styles.answerBtn} onPress={() => markAnswered(q.id)}>
                    <Ionicons name="checkmark" size={14} color="#fff" />
                  </TouchableOpacity>
                )}
              </View>
            ))}
          </View>

          {/* Polls — FR-504 / FR-505 */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>Live poll</Text>
              {activePoll
                ? <Badge variant={votes.some(v => v > 0) ? 'green' : 'yellow'} dot>{votes.some(v => v > 0) ? 'Voting open' : 'Ready'}</Badge>
                : <Badge variant="gray">None</Badge>}
            </View>
            {!activePoll ? (
              <TouchableOpacity style={styles.createPollBtn} onPress={() => setPollOpen(true)}>
                <Ionicons name="add-circle" size={18} color={C.primary} />
                <Text style={styles.createPollText}>Create a poll</Text>
              </TouchableOpacity>
            ) : (
              <>
                <Text style={styles.pollQ}>{activePoll.question}</Text>
                {activePoll.options.map((opt, i) => {
                  const total = votes.reduce((a, b) => a + b, 0) || 1
                  const pct = Math.round((votes[i] / total) * 100)
                  return (
                    <View key={i} style={styles.pollRow}>
                      <Text style={styles.pollLetter}>{String.fromCharCode(65 + i)}</Text>
                      <Text style={styles.pollOptText} numberOfLines={1}>{opt}</Text>
                      <View style={styles.pollTrack}>
                        <View style={[styles.pollFill, { width: `${pct}%` }]} />
                      </View>
                      <Text style={styles.pollPct}>{pct}%</Text>
                    </View>
                  )
                })}
                <View style={styles.pollActions}>
                  <TouchableOpacity style={styles.pollVoteBtn} onPress={() => setVotes(v => v.map(x => x + 1))}>
                    <Text style={styles.pollVoteText}>Simulate votes</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.closePollBtn}
                    onPress={() => { setActivePoll(null); setPollOpts(['', '']); setPollQ('') }}
                  >
                    <Text style={styles.closePollText}>Close poll</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>

          {/* Simulate incoming (frontend demo controls) */}
          <View style={styles.demoRow}>
            <TouchableOpacity style={styles.demoBtn} onPress={() => setQuestions(q => [...q, { id: Date.now(), text: 'Why do we need sprint retrospectives?', live: false }])}>
              <Ionicons name="add" size={13} color={C.primary} />
              <Text style={styles.demoText}>Incoming question</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.demoBtn} onPress={() => setIduCount(c => c + 1)}>
              <Ionicons name="hand-left" size={13} color={C.red} />
              <Text style={styles.demoText}>IDU signal</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.demoBtn}
              onPress={() => setReactions(r => ({ ...r, thumbs: r.thumbs + 1 }))}
            >
              <Ionicons name="thumbs-up" size={13} color={C.green} />
              <Text style={styles.demoText}>Reaction</Text>
            </TouchableOpacity>
          </View>

          <View style={{ height: 24 }} />
        </ScrollView>
      )}

      {/* Poll creation modal — FR-504 */}
      <Modal visible={pollOpen} transparent animationType="slide" onRequestClose={() => setPollOpen(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Create Live Poll</Text>
            <Text style={styles.modalSub}>2 or more answer options · one vote per student (FR-505).</Text>
            <TextInput
              style={[styles.input, styles.modalInput]}
              placeholder="Poll question…"
              placeholderTextColor={C.textHint}
              value={pollQ}
              onChangeText={setPollQ}
            />
            {pollOpts.map((o, i) => (
              <View key={i} style={styles.optEditRow}>
                <Text style={styles.optEditLetter}>{String.fromCharCode(65 + i)}</Text>
                <TextInput
                  style={styles.input}
                  placeholder={`Option ${String.fromCharCode(65 + i)}`}
                  placeholderTextColor={C.textHint}
                  value={o}
                  onChangeText={t => setPollOpts(prev => prev.map((x, j) => (j === i ? t : x)))}
                />
              </View>
            ))}
            {pollOpts.length < 5 && (
              <TouchableOpacity style={styles.addOptBtn} onPress={addOption}>
                <Ionicons name="add" size={14} color={C.primary} />
                <Text style={styles.addOptText}>Add option</Text>
              </TouchableOpacity>
            )}
            <View style={styles.modalBtnRow}>
              <TouchableOpacity style={styles.modalCancel} onPress={() => setPollOpen(false)}>
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalCreate} onPress={createPoll}>
                <Text style={styles.modalCreateText}>Open poll</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  sessionRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: C.card, paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: C.border,
  },
  sessionClass: { fontSize: 14, fontWeight: '700', color: C.text },
  sessionMeta: { fontSize: 12, color: C.textSub, marginTop: 1 },
  sessionBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 16, paddingVertical: 9, borderRadius: 9,
  },
  sessionBtnOn: { backgroundColor: C.red },
  sessionBtnOff: { backgroundColor: C.green },
  sessionBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  card: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 12,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  iduAlert: { borderColor: C.red, borderWidth: 1.5, backgroundColor: C.redLt },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  cardSub: { fontSize: 11, color: C.textHint },
  iduRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  iduCount: { fontSize: 32, fontWeight: '900', color: C.text },
  iduActions: { flexDirection: 'row', gap: 8, marginTop: 10 },
  reteachBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    backgroundColor: C.red, borderRadius: 9, paddingVertical: 10,
  },
  reteachText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  clearBtn: { paddingVertical: 10, paddingHorizontal: 14, borderRadius: 9, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card, alignItems: 'center' },
  clearText: { fontSize: 13, fontWeight: '600', color: C.text },
  reactionRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  reactionCell: {
    flex: 1, alignItems: 'center', gap: 3, paddingVertical: 10,
    borderRadius: 10, borderWidth: 1, borderColor: C.border, backgroundColor: C.bg,
  },
  reactionHot: { borderColor: C.red, backgroundColor: C.redLt },
  reactionNum: { fontSize: 15, fontWeight: '800', color: C.primary },
  reactionLbl: { fontSize: 9, color: C.textSub },
  input: {
    borderWidth: 1.5, borderColor: C.border, borderRadius: 10, backgroundColor: C.bg,
    paddingHorizontal: 12, paddingVertical: 9, fontSize: 13, color: C.text, marginBottom: 8,
  },
  askBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    backgroundColor: C.primary, borderRadius: 9, paddingVertical: 10, marginBottom: 12,
  },
  askBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  emptyHint: { fontSize: 12, color: C.textHint, textAlign: 'center', paddingVertical: 16 },
  qRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderTopWidth: 1, borderTopColor: C.border, paddingVertical: 10,
  },
  qRowAnswered: { opacity: 0.65 },
  qBody: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  qText: { fontSize: 13, color: C.text, flexShrink: 1 },
  qTextAnswered: { textDecorationLine: 'line-through', color: C.textSub },
  answerBtn: {
    width: 30, height: 30, borderRadius: 15, backgroundColor: C.green,
    alignItems: 'center', justifyContent: 'center',
  },
  createPollBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    borderWidth: 1.5, borderColor: C.primary, borderStyle: 'dashed',
    borderRadius: 10, paddingVertical: 14,
  },
  createPollText: { fontSize: 13, fontWeight: '700', color: C.primary },
  pollQ: { fontSize: 14, fontWeight: '700', color: C.text, marginBottom: 10 },
  pollRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  pollLetter: { fontSize: 11, fontWeight: '800', color: C.gray600, width: 14 },
  pollOptText: { flex: 1, fontSize: 12, color: C.text },
  pollTrack: { width: 70, height: 5, borderRadius: 3, backgroundColor: C.gray100, overflow: 'hidden' },
  pollFill: { height: 5, backgroundColor: C.primary },
  pollPct: { fontSize: 11, fontWeight: '700', color: C.primary, width: 30, textAlign: 'right' },
  pollActions: { flexDirection: 'row', gap: 8, marginTop: 6 },
  pollVoteBtn: { flex: 1, alignItems: 'center', paddingVertical: 9, borderRadius: 9, borderWidth: 1.5, borderColor: C.border },
  pollVoteText: { fontSize: 12, fontWeight: '600', color: C.text },
  closePollBtn: { flex: 1, alignItems: 'center', paddingVertical: 9, borderRadius: 9, backgroundColor: C.red },
  closePollText: { fontSize: 12, fontWeight: '700', color: '#fff' },
  demoRow: {
    flexDirection: 'row', gap: 8, marginHorizontal: 16, marginTop: 12,
    paddingTop: 10, borderTopWidth: 1, borderTopColor: C.border,
  },
  demoBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    backgroundColor: C.card, borderRadius: 9, paddingVertical: 8,
    borderWidth: 1, borderColor: C.border,
  },
  demoText: { fontSize: 10, fontWeight: '600', color: C.textSub },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: C.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: C.text, marginBottom: 4 },
  modalSub: { fontSize: 12, color: C.textSub, marginBottom: 14 },
  modalInput: { marginBottom: 8 },
  optEditRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  optEditLetter: { fontSize: 12, fontWeight: '800', color: C.gray600, width: 14 },
  addOptBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2, marginBottom: 14 },
  addOptText: { fontSize: 13, fontWeight: '600', color: C.primary },
  modalBtnRow: { flexDirection: 'row', gap: 8 },
  modalCancel: { flex: 1, paddingVertical: 13, borderRadius: 10, borderWidth: 1.5, borderColor: C.border, alignItems: 'center' },
  modalCancelText: { fontSize: 15, fontWeight: '600', color: C.text },
  modalCreate: { flex: 1, paddingVertical: 13, borderRadius: 10, backgroundColor: C.green, alignItems: 'center' },
  modalCreateText: { fontSize: 15, fontWeight: '700', color: '#fff' },
})
