import { useState, useEffect, useCallback, useRef } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, TextInput,
  RefreshControl, Alert, ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { useLecturer } from '../context/LecturerContext'
import { getToken, refreshAccessToken, BASE } from '../services/client'
import {
  getInteraction, getOpenInteractions, getInteractions, closeInteraction,
  createPoll, closePoll, getPolls, postLiveQuestion, getLiveQuestion,
  markQuestionAnswered, getQuestions, getReactions, getIduCount,
} from '../services/api'
import { connectInteractionLive } from '../services/interactionLive'
import { C } from '../theme'

const REACTIONS = ['confused', 'pace_too_fast', 'pace_too_slow', 'understood', 'agree']
const REACTION_LABEL = {
  confused: 'Confused',
  pace_too_fast: 'Too fast',
  pace_too_slow: 'Too slow',
  understood: 'Understood',
  agree: 'Agree',
}
const REACTION_ICON = {
  confused: 'sad-outline',
  pace_too_fast: 'fast-forward-outline',
  pace_too_slow: 'play-back-outline',
  understood: 'checkmark-circle-outline',
  agree: 'thumbs-up-outline',
}

/**
 * The lecturer's live view of one interaction session (UC-501 step 4, S26).
 * Opening happens on Home; closing lives in the header action here (and Home
 * re-reads `GET /lecturer/interactions/open` when it regains focus).
 * Insight first (S26b): IDU + reactions + student questions sit at the top,
 * the session tools (poll, live question) sit below them.
 */
export default function InteractionControl({ route, navigation }) {
  const { showToast } = useLecturer()
  const insets = useSafeAreaInsets()
  const wsRef = useRef(null)
  const reloadTimer = useRef(null)

  const paramInteractionId = route.params?.interaction_id
  const paramOccurrenceId = route.params?.occurrence_id

  const [interaction, setInteraction] = useState(null)   // {id, class_code, class_name, status}
  const [fallbackList, setFallbackList] = useState([])
  const [loading, setLoading] = useState(Boolean(paramInteractionId || paramOccurrenceId))
  const [refreshing, setRefreshing] = useState(false)

  // Live data
  const [poll, setPoll] = useState(null)
  const [liveQuestion, setLiveQuestion] = useState(null)
  const [questions, setQuestions] = useState([])
  const [reactionCounts, setReactionCounts] = useState({})
  const [iduCount, setIDUCount] = useState(0)

  // Poll creation state
  const [pollDraft, setPollDraft] = useState('')
  const [pollOptions, setPollOptions] = useState(['', ''])
  const [creatingPoll, setCreatingPoll] = useState(false)

  // Live question state
  const [liveDraft, setLiveDraft] = useState('')
  const [postingQuestion, setPostingQuestion] = useState(false)

  const interactionId = interaction?.id ?? paramInteractionId ?? null
  const isOpen = interaction ? interaction.status === 'open' : true

  // Resolve the session from route params, or fall back to the lecturer's open sessions.
  useEffect(() => {
    let cancelled = false
    setLoading(Boolean(paramInteractionId || paramOccurrenceId))
    ;(async () => {
      try {
        if (paramInteractionId) {
          const found = await getInteraction(paramInteractionId)
          if (!cancelled) setInteraction(found)
        } else if (paramOccurrenceId) {
          const list = await getInteractions(paramOccurrenceId)
          if (!cancelled) {
            setInteraction(list.find(i => i.status === 'open') ?? list[0] ?? null)
          }
        } else {
          const list = await getOpenInteractions()
          if (!cancelled) {
            setFallbackList(list)
            if (list.length === 1) setInteraction(list[0])
          }
        }
      } catch (e) {
        if (!cancelled) showToast(e.message, 'error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [paramInteractionId, paramOccurrenceId, showToast])

  const loadLive = useCallback(async (id) => {
    if (!id) return
    // A fresh session has no live question yet (404), which must not hide the polls
    // and questions that do exist — so each call settles on its own.
    const results = await Promise.allSettled([
      getPolls(id), getLiveQuestion(id), getQuestions(id), getReactions(id), getIduCount(id),
    ])
    const value = (i) => (results[i].status === 'fulfilled' ? results[i].value : null)
    const pollsRes = value(0)
    setPoll((pollsRes ?? [])[0] ?? null)
    setLiveQuestion(value(1))
    setQuestions(value(2) ?? [])
    const counts = {}
    ;(value(3) ?? []).forEach(r => { counts[r.reaction] = r.count })
    setReactionCounts(counts)
    setIDUCount(value(4)?.distinct_students ?? 0)

    const failure = results.find(
      r => r.status === 'rejected' && r.reason?.status !== 404,
    )
    if (failure) showToast(failure.reason.message, 'error')
  }, [showToast])

  // Debounced reload — every websocket event lands here once.
  const scheduleReload = useCallback(() => {
    clearTimeout(reloadTimer.current)
    reloadTimer.current = setTimeout(() => loadLive(interactionId), 250)
  }, [interactionId, loadLive])

  // (Re)connect to the room for the resolved session.
  useEffect(() => {
    wsRef.current?.close()
    wsRef.current = null
    if (!interactionId) return
    loadLive(interactionId)
    const ws = connectInteractionLive({
      interactionId,
      baseUrl: BASE,
      getToken,
      refreshToken: refreshAccessToken,
      onEvent: (data) => {
        switch (data.event) {
          case 'interaction_closed':
            setInteraction(prev => prev ? { ...prev, status: 'closed' } : prev)
            scheduleReload()
            break
          case 'poll_created':
          case 'poll_vote':
          case 'poll_closed':
          case 'live_question_posted':
          case 'live_question_response':
          case 'reaction_updated':
          case 'idu_signal':
            scheduleReload()
            break
        }
      },
    })
    wsRef.current = ws
    return () => {
      clearTimeout(reloadTimer.current)
      ws.close()
    }
  }, [interactionId, loadLive, scheduleReload])

  const stopSession = useCallback(async () => {
    if (!interactionId || !isOpen) return
    try {
      await closeInteraction(interactionId)
      setInteraction(prev => prev ? { ...prev, status: 'closed' } : prev)
      scheduleReload()
      showToast('Session closed', 'success')
    } catch (e) {
      Alert.alert('Could not close session', e.message)
    }
  }, [interactionId, isOpen, showToast, scheduleReload])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadLive(interactionId)
    setRefreshing(false)
  }, [interactionId, loadLive])

  const addPollOption = () => setPollOptions([...pollOptions, ''])
  const removePollOption = (idx) => setPollOptions(pollOptions.filter((_, i) => i !== idx))
  const setPollOption = (idx, value) => {
    const next = [...pollOptions]
    next[idx] = value
    setPollOptions(next)
  }

  const createPollAction = useCallback(async () => {
    const options = pollOptions.filter(o => o.trim()).map(o => o.trim())
    if (!pollDraft.trim() || options.length < 2 || creatingPoll) return
    setCreatingPoll(true)
    try {
      await createPoll(interactionId, { question: pollDraft.trim(), options })
      setPollDraft('')
      setPollOptions(['', ''])
      await loadLive(interactionId)
    } catch (e) {
      Alert.alert('Could not create poll', e.message)
    } finally {
      setCreatingPoll(false)
    }
  }, [pollDraft, pollOptions, creatingPoll, interactionId, createPoll, loadLive])

  // FR-504: close voting on this poll — the session stays open.
  const closePollAction = useCallback(async () => {
    if (!poll) return
    try {
      await closePoll(interactionId, poll.id)
      await loadLive(interactionId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [poll, interactionId, closePoll, loadLive, showToast])

  const postLiveQuestionAction = useCallback(async () => {
    if (!liveDraft.trim() || !interactionId || postingQuestion) return
    setPostingQuestion(true)
    try {
      await postLiveQuestion(interactionId, liveDraft.trim())
      setLiveDraft('')
      await loadLive(interactionId)
    } catch (e) {
      Alert.alert('Could not post question', e.message)
    } finally {
      setPostingQuestion(false)
    }
  }, [liveDraft, interactionId, postingQuestion, postLiveQuestion, loadLive])

  const markAnswered = useCallback(async (question) => {
    if (!interactionId || question.answered) return
    try {
      await markQuestionAnswered(interactionId, question.id)
      await loadLive(interactionId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [interactionId, markQuestionAnswered, showToast, loadLive])

  // Insight numbers (S26b): what needs the lecturer's attention right now.
  const openQuestions = questions.filter(q => !q.answered)
  const sortedQuestions = [...openQuestions, ...questions.filter(q => q.answered)]
  const totalReactions = Object.values(reactionCounts).reduce((s, v) => s + (v ?? 0), 0)
  const topReaction = REACTIONS.reduce(
    (best, r) => ((reactionCounts[r] ?? 0) > (reactionCounts[best] ?? 0) ? r : best), null,
  )

  const headerSub = interaction
    ? `${interaction.class_code} · ${isOpen ? 'Open' : 'Closed'}`
    : paramInteractionId
      ? 'Loading…'
      : 'No open session'

  const closeAction = (
    <TouchableOpacity
      testID="interaction-close-session"
      onPress={stopSession}
      disabled={loading || !isOpen}
      accessibilityLabel={isOpen ? 'Close session' : 'Session closed'}
      style={styles.closeBtn}
    >
      <Ionicons name={isOpen ? 'stop-circle' : 'checkmark-circle'} size={18} color={isOpen ? C.red : C.textSub} />
      <Text style={[styles.closeBtnText, { color: isOpen ? C.red : C.textSub }]}>
        {isOpen ? 'Close' : 'Closed'}
      </Text>
    </TouchableOpacity>
  )

  return (
    <View style={styles.flex}>
      <Topbar title="Interaction" sub={headerSub} onBack={() => navigation.goBack()} right={closeAction} />
      {loading ? (
        <View style={styles.center}><ActivityIndicator color={C.primary} /></View>
      ) : !interactionId ? (
        fallbackList.length > 0 ? (
          <ScrollView style={styles.flex} contentContainerStyle={styles.content}>
            <Text style={[styles.sectionTitle, styles.pickTitle]}>Open sessions</Text>
            {fallbackList.map(s => (
              <TouchableOpacity
                key={s.id}
                testID={`interaction-open-session-${s.id}`}
                style={styles.sessionRow}
                onPress={() => setInteraction(s)}
              >
                <View style={styles.sessionDotWrap}>
                  <View style={styles.sessionDot} />
                  <View>
                    <Text style={styles.questionText}>{s.class_code}</Text>
                    <Text style={styles.emptyResponses}>{s.class_name}</Text>
                  </View>
                </View>
                <Ionicons name="chevron-forward" size={16} color={C.gray300} />
              </TouchableOpacity>
            ))}
          </ScrollView>
        ) : (
          <View style={styles.empty}>
            <Ionicons name="chatbubble-outline" size={48} color={C.textHint} />
            <Text style={styles.emptyText}>No open interaction session</Text>
            <Text style={styles.emptySub}>Start one from the Home screen.</Text>
          </View>
        )
      ) : (
        <ScrollView
          style={styles.flex}
          showsVerticalScrollIndicator={false}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />}
          contentContainerStyle={styles.content}
        >
          <View style={[styles.statusBar, isOpen ? styles.statusOpen : styles.statusClosed]}>
            <View style={[styles.statusDot, isOpen ? styles.statusDotOpen : styles.statusDotClosed]} />
            <Text style={[styles.statusText, isOpen ? styles.statusOpenText : styles.statusClosedText]}>
              {isOpen ? 'Session is open — students can join' : 'Session is closed'}
            </Text>
          </View>

          {/* Class pulse — the insight strip (S26b): IDU, reactions, open questions first */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.sectionTitle}>Class pulse</Text>
              <Badge variant={isOpen ? 'green' : 'gray'} dot>
                {isOpen ? 'Live' : 'Ended'}
              </Badge>
            </View>
            <View style={styles.pulseRow}>
              <View style={[styles.pulseTile, { backgroundColor: C.orangeLt }]}>
                <Ionicons name="help-buoy" size={15} color={C.orangeDk} />
                <Text testID="interaction-idu-count" style={[styles.pulseNum, { color: C.orangeDk }]}>
                  {iduCount}
                </Text>
                <Text style={[styles.pulseLabel, { color: C.orangeDk }]} numberOfLines={1}>
                  don't understand
                </Text>
              </View>
              <View style={[styles.pulseTile, { backgroundColor: C.blueLt }]}>
                <Ionicons name="chatbubbles" size={15} color={C.blueDk} />
                <Text style={[styles.pulseNum, { color: C.blueDk }]}>{openQuestions.length}</Text>
                <Text style={[styles.pulseLabel, { color: C.blueDk }]} numberOfLines={1}>
                  open question{openQuestions.length !== 1 ? 's' : ''}
                </Text>
              </View>
              <View style={[styles.pulseTile, { backgroundColor: C.greenLt }]}>
                <Ionicons
                  name={topReaction ? REACTION_ICON[topReaction] : 'happy-outline'}
                  size={15}
                  color={C.greenDk}
                />
                <Text style={[styles.pulseNum, { color: C.greenDk }]}>
                  {topReaction ? (reactionCounts[topReaction] ?? 0) : totalReactions}
                </Text>
                <Text style={[styles.pulseLabel, { color: C.greenDk }]} numberOfLines={1}>
                  {topReaction ? REACTION_LABEL[topReaction].toLowerCase() : 'reactions'}
                </Text>
              </View>
            </View>
            <View style={styles.reactionsRow}>
              {REACTIONS.map(r => (
                <View
                  key={r}
                  style={[styles.reactionChip, (reactionCounts[r] ?? 0) > 0 && styles.reactionChipActive]}
                  testID={`interaction-reaction-${r}`}
                >
                  <Ionicons name={REACTION_ICON[r]} size={14} color={C.textSub} />
                  <Text style={styles.reactionLabel}>{REACTION_LABEL[r]}</Text>
                  <Text style={styles.reactionCount}>{reactionCounts[r] ?? 0}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* Student questions (FR-502/503) — right under the pulse, unanswered first */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.sectionTitle}>Student questions</Text>
              {openQuestions.length > 0 && (
                <Badge variant="blue" dot>{openQuestions.length} open</Badge>
              )}
            </View>
            {questions.length === 0 ? (
              <Text style={styles.emptyResponses}>No questions yet.</Text>
            ) : sortedQuestions.map(q => (
              <View
                key={q.id}
                style={[styles.questionItem, q.answered ? styles.questionItemAnswered : styles.questionItemOpen]}
              >
                <View
                  style={[styles.questionBar, q.answered ? styles.questionBarAnswered : styles.questionBarOpen]}
                />
                <View style={styles.questionBody}>
                  <Text style={styles.questionText}>{q.text}</Text>
                  {q.anonymous ? (
                    <View style={styles.anonPill}>
                      <Ionicons name="eye-off-outline" size={10} color={C.gray600} />
                      <Text style={styles.anonPillText}>Anonymous</Text>
                    </View>
                  ) : null}
                  <View style={styles.questionMeta}>
                    <Text style={[styles.questionMetaText, q.answered && styles.questionMetaAnswered]}>
                      {q.answered ? 'Answered' : 'Needs an answer'}
                    </Text>
                    {!q.answered && isOpen && (
                      <TouchableOpacity
                        testID={`interaction-mark-answered-${q.id}`}
                        style={styles.markBtn}
                        onPress={() => markAnswered(q)}
                      >
                        <Ionicons name="checkmark" size={12} color={C.greenDk} />
                        <Text style={styles.markBtnText}>Mark answered</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                </View>
              </View>
            ))}
          </View>

          {/* Live question + responses */}
          {liveQuestion && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.sectionTitle}>Live question</Text>
                <Badge variant={liveQuestion.is_active ? 'blue' : 'gray'} dot>
                  {liveQuestion.is_active ? 'Live' : 'Closed'}
                </Badge>
              </View>
              <Text style={styles.liveQuestionText}>{liveQuestion.question}</Text>
              {liveQuestion.responses?.length > 0 ? (
                <>
                  <Text style={styles.responsesTitle}>
                    {liveQuestion.responses.length} response{liveQuestion.responses.length === 1 ? '' : 's'}
                  </Text>
                  {liveQuestion.responses.map(r => (
                    <View key={r.id} style={styles.responseItem}>
                      <Text style={styles.responseText}>{r.response}</Text>
                    </View>
                  ))}
                </>
              ) : (
                <Text style={styles.emptyResponses}>No responses yet.</Text>
              )}
            </View>
          )}

          {/* Latest poll with results (FR-504/505); stays visible after voting closes */}
          {poll && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.sectionTitle}>Latest poll</Text>
                <Badge variant={poll.is_open ? 'blue' : 'gray'} dot>
                  {poll.is_open ? 'Open' : 'Closed'}
                </Badge>
              </View>
              <Text style={styles.pollQuestion}>{poll.question}</Text>
              {poll.options.map(o => {
                const total = poll.options.reduce((s, o2) => s + (o2.votes ?? 0), 0)
                const pct = total > 0 ? Math.round(((o.votes ?? 0) / total) * 100) : 0
                return (
                  <View key={o.id} style={styles.barCol}>
                    <View style={styles.barRow}>
                      <Text style={styles.barOptLabel}>{o.option_text}</Text>
                      <Text style={styles.barOptPct}>{pct}%</Text>
                    </View>
                    <View style={styles.barTrack}>
                      <View style={[styles.barFill, { width: `${pct}%` }]} />
                    </View>
                    <Text style={styles.barCount}>{o.votes ?? 0} vote{o.votes !== 1 ? 's' : ''}</Text>
                  </View>
                )
              })}
              <TouchableOpacity
                testID="interaction-close-poll-btn"
                style={[styles.closePollBtn, !poll.is_open && styles.closePollBtnDone]}
                onPress={closePollAction}
                disabled={!isOpen || !poll.is_open}
              >
                <Ionicons
                  name={poll.is_open ? 'lock-closed-outline' : 'lock-closed'}
                  size={16}
                  color={poll.is_open ? C.red : C.textSub}
                />
                <Text style={[styles.closePollBtnText, !poll.is_open && { color: C.textSub }]}>
                  {poll.is_open ? 'Close voting' : 'Voting closed'}
                </Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Create a poll (FR-504) */}
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Create a poll</Text>
            <TextInput
              testID="interaction-poll-question-input"
              style={styles.input}
              value={pollDraft}
              onChangeText={setPollDraft}
              placeholder="Poll question…"
              maxLength={500}
              editable={isOpen}
            />
            {pollOptions.map((opt, idx) => (
              <View key={idx} style={styles.optionRow}>
                <TextInput
                  testID={`interaction-poll-option-${idx}`}
                  style={styles.optionInput}
                  value={opt}
                  onChangeText={v => setPollOption(idx, v)}
                  placeholder={`Option ${idx + 1}…`}
                  maxLength={100}
                  editable={isOpen}
                />
                {pollOptions.length > 2 && (
                  <TouchableOpacity onPress={() => removePollOption(idx)} hitSlop={8}>
                    <Ionicons name="trash-outline" size={18} color={C.textSub} />
                  </TouchableOpacity>
                )}
              </View>
            ))}
            <TouchableOpacity
              testID="interaction-add-poll-option"
              style={styles.addOption}
              onPress={addPollOption}
              hitSlop={8}
              disabled={!isOpen}
            >
              <Ionicons name="add-circle-outline" size={18} color={C.primary} />
              <Text style={styles.addOptionText}>Add option</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="interaction-create-poll-btn"
              style={[styles.primaryBtn, (creatingPoll || !isOpen) && styles.btnDisabled]}
              onPress={createPollAction}
              disabled={creatingPoll || !isOpen}
            >
              <Text style={styles.primaryBtnText}>{creatingPoll ? 'Creating…' : 'Create poll'}</Text>
            </TouchableOpacity>
          </View>

          {/* Ask the class (FR-506) */}
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Ask the class</Text>
            <TextInput
              testID="interaction-live-question-input"
              style={styles.input}
              value={liveDraft}
              onChangeText={setLiveDraft}
              placeholder="Post a live question…"
              maxLength={500}
              multiline
              editable={isOpen}
            />
            <TouchableOpacity
              testID="interaction-post-question-btn"
              style={[styles.primaryBtn, (!liveDraft.trim() || postingQuestion || !isOpen) && styles.btnDisabled]}
              onPress={postLiveQuestionAction}
              disabled={!liveDraft.trim() || postingQuestion || !isOpen}
            >
              <Text style={styles.primaryBtnText}>{postingQuestion ? 'Posting…' : 'Post question'}</Text>
            </TouchableOpacity>
          </View>
          <View style={{ height: 24 }} />
        </ScrollView>
      )}
      <View style={{ height: insets.bottom }} />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { paddingBottom: 24 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  empty: { padding: 40, alignItems: 'center' },
  emptyText: { fontSize: 14, color: C.textSub, marginTop: 8 },
  emptySub: { fontSize: 12, color: C.textHint, marginTop: 6 },
  closeBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  closeBtnText: { fontSize: 13, fontWeight: '700' },
  pickTitle: { marginHorizontal: 16, marginTop: 16, marginBottom: 8 },
  sessionRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: C.card, marginHorizontal: 16, marginBottom: 8,
    borderRadius: 10, borderWidth: 1, borderColor: C.border, padding: 12,
  },
  sessionDotWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sessionDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.green },
  card: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 10,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  cardHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 8,
  },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: C.textSub, marginBottom: 6 },
  input: {
    backgroundColor: C.gray100, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, color: C.text, fontSize: 14,
  },
  optionRow: {
    flexDirection: 'row', gap: 8, alignItems: 'center',
    backgroundColor: C.gray100, borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 8, marginTop: 6,
  },
  optionInput: { flex: 1, fontSize: 14, color: C.text },
  addOption: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, paddingVertical: 4 },
  addOptionText: { fontSize: 13, color: C.primary, fontWeight: '600' },
  primaryBtn: { backgroundColor: C.primary, borderRadius: 8, paddingVertical: 10, alignItems: 'center', marginTop: 10 },
  btnDisabled: { opacity: 0.5 },
  primaryBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  statusBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 16, paddingVertical: 9, borderRadius: 10,
    marginHorizontal: 16, marginTop: 8, borderWidth: 1,
  },
  statusOpen: { backgroundColor: C.greenLt, borderColor: C.green },
  statusClosed: { backgroundColor: C.redLt, borderColor: C.red },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusDotOpen: { backgroundColor: C.green },
  statusDotClosed: { backgroundColor: C.red },
  statusText: { fontSize: 13, fontWeight: '700' },
  statusOpenText: { color: C.greenDk },
  statusClosedText: { color: C.redDk },
  // Class pulse (S26b)
  pulseRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  pulseTile: {
    flex: 1, borderRadius: 10, alignItems: 'center',
    paddingVertical: 10, paddingHorizontal: 4, gap: 2,
  },
  pulseNum: { fontSize: 20, fontWeight: '800' },
  pulseLabel: { fontSize: 10, fontWeight: '600', textAlign: 'center' },
  reactionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  reactionChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: C.gray100, borderRadius: 20,
    paddingHorizontal: 10, paddingVertical: 6,
  },
  reactionChipActive: { backgroundColor: C.blueLt, borderWidth: 1, borderColor: C.primary },
  reactionLabel: { fontSize: 11, color: C.textSub },
  reactionCount: { fontSize: 12, fontWeight: '700', color: C.primary },
  // Student questions
  questionItem: {
    flexDirection: 'row', borderRadius: 8, backgroundColor: C.gray50,
    padding: 10, marginBottom: 8,
  },
  questionItemOpen: { backgroundColor: C.blueLt },
  questionItemAnswered: { backgroundColor: C.gray50, opacity: 0.8 },
  questionBar: { width: 3, borderRadius: 2, marginRight: 10 },
  questionBarOpen: { backgroundColor: C.primary },
  questionBarAnswered: { backgroundColor: C.gray300 },
  questionBody: { flex: 1 },
  questionText: { fontSize: 14, color: C.text },
  anonPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start',
    backgroundColor: C.gray100, borderRadius: 8, paddingHorizontal: 6,
    paddingVertical: 2, marginTop: 4,
  },
  anonPillText: { fontSize: 10, fontWeight: '700', color: C.gray600 },
  questionMeta: { flexDirection: 'row', gap: 8, marginTop: 6, alignItems: 'center' },
  questionMetaText: { fontSize: 11, color: C.textHint },
  questionMetaAnswered: { color: C.green, fontWeight: '700' },
  markBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 8, paddingVertical: 4,
    backgroundColor: C.card, borderRadius: 6, borderWidth: 1, borderColor: C.green,
  },
  markBtnText: { fontSize: 11, fontWeight: '700', color: C.greenDk },
  liveQuestionText: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 8 },
  responsesTitle: { fontSize: 12, fontWeight: '700', color: C.textSub, marginBottom: 6 },
  responseItem: { paddingVertical: 6, backgroundColor: C.gray100, borderRadius: 6, marginBottom: 6, paddingHorizontal: 8 },
  responseText: { fontSize: 13, color: C.text },
  emptyResponses: { fontSize: 13, color: C.textHint, marginTop: 4 },
  pollQuestion: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 10 },
  barCol: { marginBottom: 10 },
  barRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  barOptLabel: { fontSize: 13, color: C.text },
  barOptPct: { fontSize: 13, fontWeight: '700', color: C.primary },
  barTrack: { height: 8, backgroundColor: C.gray100, borderRadius: 4, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: C.primary, borderRadius: 4 },
  barCount: { fontSize: 12, color: C.textSub },
  closePollBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, alignSelf: 'flex-start' },
  closePollBtnDone: { opacity: 0.7 },
  closePollBtnText: { fontSize: 13, fontWeight: '700', color: C.red },
})
