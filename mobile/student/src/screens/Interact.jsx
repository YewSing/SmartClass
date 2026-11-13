// Module 5 — Classroom Interaction (student view): FR-502, FR-505, FR-507, FR-508.
// Frontend-only: the session state, questions and polls come from module2 mock
// fixtures and local component state until Module 5 is wired to the backend.
import { useState } from 'react'
import {
  View, Text, ScrollView, TextInput, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { LIVE_ACTIVITY } from '../data/module2'
import { C } from '../theme'

const REACTIONS = [
  { id: 'thumbs', icon: 'thumbs-up', label: 'Good pace' },
  { id: 'slow', icon: 'speedometer', label: 'Too fast' },
  { id: 'example', icon: 'bullet-list', label: 'More examples' },
  { id: 'repeat', icon: 'repeat', label: 'Repeat that' },
]

export default function Interact({ navigation }) {
  const activity = LIVE_ACTIVITY
  const [anonymous, setAnonymous] = useState(false)
  const [question, setQuestion] = useState('')
  const [submitted, setSubmitted] = useState([])
  const [voted, setVoted] = useState(activity.poll.voted)
  const [myVote, setMyVote] = useState(null)
  const [votes, setVotes] = useState(activity.poll.options.map(() => Math.floor(Math.random() * 6) + 2))
  const [reacted, setReacted] = useState({})
  const [idu, setIdu] = useState(false)

  if (!activity.open) {
    return (
      <View style={styles.flex}>
        <Topbar title="Interact" sub="Live classroom activities" />
        <View style={styles.empty}>
          <Ionicons name="videocam-off-outline" size={36} color={C.gray300} />
          <Text style={styles.emptyTitle}>No interaction session open</Text>
          <Text style={styles.emptySub}>Your lecturer opens interactions during class time.</Text>
        </View>
      </View>
    )
  }

  const submitQuestion = () => {
    if (!question.trim()) return
    setSubmitted(prev => [...prev, { id: Date.now(), text: question.trim(), anonymous }])
    setQuestion('')
    setAnonymous(false)
  }

  const vote = (i) => {
    if (voted) return
    setVotes(v => v.map((n, j) => (j === i ? n + 1 : n)))
    setMyVote(i)
    setVoted(true)
  }

  const react = (id) => setReacted(r => ({ ...r, [id]: !r[id] }))
  const reactionCount = Object.values(reacted).filter(Boolean).length

  return (
    <View style={styles.flex}>
      <Topbar title="Interact" sub={`${activity.course} · ${activity.room}`} />

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Live session banner */}
        <View style={styles.liveBanner}>
          <View style={styles.liveDotWrap}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>LIVE</Text>
          </View>
          <Text style={styles.liveLecturer}>Dr. Tan Wei Liang is interacting with the class</Text>
        </View>

        {/* Live poll — FR-505 */}
        <View style={[styles.card, styles.cardHighlight]}>
          <View style={styles.cardHeader}>
            <View style={[styles.tagChip, { backgroundColor: C.purpleLt }]}>
              <Ionicons name="bar-chart" size={9} color={C.purple} />
              <Text style={[styles.tagText, { color: C.purple }]}>Live poll</Text>
            </View>
            <Badge variant={voted ? 'green' : 'blue'} dot>{voted ? 'Voted' : 'Open'}</Badge>
          </View>
          <Text style={styles.pollQ}>{activity.poll.question}</Text>
          {activity.poll.options.map((opt, i) => {
            const total = votes.reduce((a, b) => a + b, 0)
            const pct = Math.round((votes[i] / total) * 100)
            return (
              <TouchableOpacity
                key={i}
                style={[styles.pollOpt, voted && myVote === i && styles.pollOptMine]}
                onPress={() => vote(i)}
                disabled={voted}
              >
                <View style={styles.pollLetter}><Text style={styles.pollLetterText}>{String.fromCharCode(65 + i)}</Text></View>
                <Text style={styles.pollOptText}>{opt}</Text>
                {voted && (
                  <View style={styles.pollResult}>
                    <View style={styles.pollTrack}>
                      <View style={[styles.pollFill, { width: `${pct}%` }]} />
                    </View>
                    <Text style={styles.pollPct}>{pct}%</Text>
                  </View>
                )}
              </TouchableOpacity>
            )
          })}
          {!voted && <Text style={styles.pollNote}>One vote per poll · results show after you vote</Text>}
        </View>

        {/* Ask a question — FR-502 */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.tagChip, { backgroundColor: C.blueLt }]}>
              <Ionicons name="help-circle" size={9} color={C.primary} />
              <Text style={[styles.tagText, { color: C.primary }]}>Ask a question</Text>
            </View>
            <Text style={styles.sendCount}>{submitted.length} sent</Text>
          </View>
          <TextInput
            style={styles.textarea}
            placeholder="Type your question for the lecturer…"
            placeholderTextColor={C.textHint}
            multiline
            value={question}
            onChangeText={setQuestion}
            textAlignVertical="top"
          />
          <View style={styles.askRow}>
            <TouchableOpacity style={styles.anonToggle} onPress={() => setAnonymous(a => !a)}>
              <Ionicons
                name={anonymous ? 'checkbox' : 'square-outline'}
                size={18}
                color={anonymous ? C.primary : C.gray400}
              />
              <Text style={styles.anonText}>Send anonymously</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.sendBtn, !question.trim() && styles.btnDisabled]}
              onPress={submitQuestion}
              disabled={!question.trim()}
            >
              <Ionicons name="send" size={14} color="#fff" />
              <Text style={styles.sendBtnText}>Send</Text>
            </TouchableOpacity>
          </View>
          {submitted.map(q => (
            <View key={q.id} style={styles.sentRow}>
              <Ionicons name="checkmark-circle" size={14} color={C.green} />
              <Text style={styles.sentText} numberOfLines={1}>{q.text}</Text>
              {q.anonymous && <Badge variant="gray">Anonymous</Badge>}
            </View>
          ))}
        </View>

        {/* Reactions — FR-507 */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.tagChip, { backgroundColor: C.greenLt }]}>
              <Ionicons name="happy" size={9} color={C.green} />
              <Text style={[styles.tagText, { color: C.green }]}>React</Text>
            </View>
            {reactionCount > 0 && <Text style={styles.sendCount}>{reactionCount} sent</Text>}
          </View>
          <View style={styles.reactionRow}>
            {REACTIONS.map(r => (
              <TouchableOpacity
                key={r.id}
                style={[styles.reactionBtn, reacted[r.id] && styles.reactionBtnOn]}
                onPress={() => react(r.id)}
              >
                <Ionicons name={r.icon} size={18} color={reacted[r.id] ? C.primary : C.textSub} />
                <Text style={[styles.reactionLbl, reacted[r.id] && { color: C.primary }]}>{r.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* I Don't Understand — FR-508 */}
        <TouchableOpacity
          style={[styles.iduBtn, idu && styles.iduBtnOn]}
          onPress={() => setIdu(v => !v)}
          activeOpacity={0.8}
        >
          <Ionicons name={idu ? 'hand-left' : 'hand-left-outline'} size={20} color={idu ? '#fff' : C.red} />
          <Text style={[styles.iduText, idu && { color: '#fff' }]}>
            {idu ? "I Don't Understand — signal sent" : "I Don't Understand"}
          </Text>
          <Text style={[styles.iduHint, idu && { color: '#FECACA' }]}>
            {idu ? 'Lecturer has been notified' : 'Tap to raise your hand anonymously'}
          </Text>
        </TouchableOpacity>

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40, gap: 6 },
  emptyTitle: { fontSize: 15, fontWeight: '700', color: C.text },
  emptySub: { fontSize: 13, color: C.textHint, textAlign: 'center' },
  liveBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: C.redLt, marginHorizontal: 16, marginTop: 12,
    borderRadius: 12, padding: 12, borderWidth: 1, borderColor: C.red,
  },
  liveDotWrap: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.red },
  liveText: { fontSize: 12, fontWeight: '800', color: C.redDk, letterSpacing: 0.5 },
  liveLecturer: { flex: 1, fontSize: 12, color: C.redDk, fontWeight: '600' },
  card: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 12,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  cardHighlight: { borderColor: C.primary },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  tagChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  tagText: { fontSize: 10, fontWeight: '800' },
  sendCount: { fontSize: 11, color: C.textHint },
  pollQ: { fontSize: 15, fontWeight: '700', color: C.text, lineHeight: 21, marginBottom: 12 },
  pollOpt: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: 1, borderColor: C.border, borderRadius: 10,
    padding: 10, marginBottom: 8, backgroundColor: C.bg,
  },
  pollOptMine: { borderColor: C.primary, backgroundColor: C.blueLt },
  pollLetter: {
    width: 24, height: 24, borderRadius: 12, backgroundColor: C.gray100,
    alignItems: 'center', justifyContent: 'center',
  },
  pollLetterText: { fontSize: 12, fontWeight: '800', color: C.gray600 },
  pollOptText: { fontSize: 13, color: C.text, fontWeight: '500' },
  pollResult: { flexDirection: 'row', alignItems: 'center', gap: 6, marginLeft: 'auto' },
  pollTrack: { width: 60, height: 5, borderRadius: 3, backgroundColor: C.gray100, overflow: 'hidden' },
  pollFill: { height: 5, backgroundColor: C.primary },
  pollPct: { fontSize: 11, fontWeight: '700', color: C.primary, width: 32, textAlign: 'right' },
  pollNote: { fontSize: 11, color: C.textHint, marginTop: 2 },
  textarea: {
    borderWidth: 1.5, borderColor: C.border, borderRadius: 10,
    backgroundColor: C.bg, padding: 10, fontSize: 14, color: C.text,
    minHeight: 72, marginBottom: 10,
  },
  askRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  anonToggle: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  anonText: { fontSize: 12, color: C.textSub, fontWeight: '500' },
  sendBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: C.primary, paddingHorizontal: 16, paddingVertical: 9, borderRadius: 9,
  },
  sendBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  btnDisabled: { opacity: 0.4 },
  sentRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.greenLt, borderRadius: 8, padding: 8, marginTop: 8,
  },
  sentText: { flex: 1, fontSize: 12, color: C.greenDk, fontWeight: '500' },
  reactionRow: { flexDirection: 'row', gap: 8 },
  reactionBtn: {
    flex: 1, alignItems: 'center', gap: 4, paddingVertical: 10,
    borderRadius: 10, borderWidth: 1, borderColor: C.border, backgroundColor: C.bg,
  },
  reactionBtnOn: { borderColor: C.primary, backgroundColor: C.blueLt },
  reactionLbl: { fontSize: 10, color: C.textSub, fontWeight: '600', textAlign: 'center' },
  iduBtn: {
    marginHorizontal: 16, marginTop: 12, borderRadius: 14,
    borderWidth: 1.5, borderColor: C.red, backgroundColor: C.redLt,
    alignItems: 'center', paddingVertical: 18, gap: 4,
  },
  iduBtnOn: { backgroundColor: C.red, borderColor: C.red },
  iduText: { fontSize: 15, fontWeight: '800', color: C.redDk },
  iduHint: { fontSize: 11, color: C.textHint },
})
