import { useState, useCallback, useEffect, useRef } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator,
  TextInput, Switch, FlatList, Alert,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { LinearGradient } from 'expo-linear-gradient'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useFocusEffect } from '@react-navigation/native'
import { useStudent } from '../context/StudentContext'
import {
  getOpenInteractions,
  getInteractionState,
  askInteractionQuestion,
  respondToLiveQuestion,
  voteInteractionPoll,
  sendInteractionReaction,
  sendInteractionIDU,
} from '../services/api'
import { connectInteractionLive } from '../services/interactionLive'
import { getToken, refreshAccessToken, BASE } from '../services/client'
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
  understood: 'checkmark-circle',
  agree: 'thumbs-up',
}
// S25b: each reaction carries its own accent so the chips read at a glance.
const REACTION_COLOR = {
  confused: { bg: C.orangeLt, fg: C.orangeDk },
  pace_too_fast: { bg: C.redLt, fg: C.redDk },
  pace_too_slow: { bg: C.yellowLt, fg: C.yellowDk },
  understood: { bg: C.greenLt, fg: C.greenDk },
  agree: { bg: C.blueLt, fg: C.blueDk },
}

export default function Participation({ route, navigation }) {
  const { showToast } = useStudent()
  const insets = useSafeAreaInsets()
  const wsRef = useRef(null)
  const reloadTimer = useRef(null)

  const paramInteractionId = route.params?.interaction_id ?? null

  const [interactions, setInteractions] = useState([])
  const [selectedId, setSelectedId] = useState(paramInteractionId)
  const [current, setCurrent] = useState(null)
  const [loading, setLoading] = useState(Boolean(paramInteractionId))
  const [refreshing, setRefreshing] = useState(false)

  // Ask-a-question state
  const [myQuestion, setMyQuestion] = useState('')
  const [anonymous, setAnonymous] = useState(false)
  const [sending, setSending] = useState(false)

  // Lecturer's live question
  const [liveQuestion, setLiveQuestion] = useState(null)
  const [responseDraft, setResponseDraft] = useState('')
  const [responding, setResponding] = useState(false)

  // Poll
  const [poll, setPoll] = useState(null)
  const [pollSelection, setPollSelection] = useState(null)
  const [voting, setVoting] = useState(false)

  // Reactions / IDU / own questions
  const [reactionCounts, setReactionCounts] = useState({})
  const [myReaction, setMyReaction] = useState(null)
  const [iduCount, setIDUCount] = useState(0)
  const [hasIDU, setHasIDU] = useState(false)
  const [questions, setQuestions] = useState([])

  const applyState = useCallback((s) => {
    setCurrent(s)
    setPoll(s.current_poll ?? null)
    setPollSelection(s.current_poll?.my_option_id ?? null)
    setLiveQuestion(s.live_question ?? null)
    setReactionCounts(s.reaction_counts ?? {})
    setMyReaction(s.my_reaction ?? null)
    setIDUCount(s.idu_distinct_students ?? 0)
    setHasIDU(Boolean(s.idu_has_signal))
    setQuestions(s.my_questions ?? [])
  }, [])

  const clearState = useCallback(() => {
    setCurrent(null)
    setPoll(null)
    setPollSelection(null)
    setLiveQuestion(null)
    setReactionCounts({})
    setMyReaction(null)
    setIDUCount(0)
    setHasIDU(false)
    setQuestions([])
    setResponseDraft('')
  }, [])

  // Load one session's full state (works while open or closed).
  const loadState = useCallback(async (id) => {
    if (!id) return
    try {
      applyState(await getInteractionState(id))
    } catch (e) {
      if (e.status === 404) {
        clearState()
      } else {
        showToast(e.message, 'error')
      }
    }
  }, [applyState, clearState, showToast])

  // Opening cold (no route param) lists the sessions the student can join.
  useFocusEffect(useCallback(() => {
    let cancelled = false
    ;(async () => {
      if (paramInteractionId) return
      setLoading(true)
      try {
        const list = await getOpenInteractions()
        if (cancelled) return
        setInteractions(list)
        if (!selectedId && list.length) setSelectedId(list[0].id)
      } catch (e) {
        if (!cancelled) showToast(e.message, 'error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [paramInteractionId, selectedId, showToast]))

  // A newer route param (Home -> another session) wins.
  useEffect(() => {
    if (paramInteractionId && paramInteractionId !== selectedId) setSelectedId(paramInteractionId)
  }, [paramInteractionId])

  // Fetch the selected session's state.
  useEffect(() => {
    if (!selectedId) { clearState(); return }
    let cancelled = false
    setLoading(true)
    loadState(selectedId).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [selectedId, loadState, clearState])

  // Live updates: every websocket event triggers one debounced refetch.
  const scheduleReload = useCallback(() => {
    clearTimeout(reloadTimer.current)
    reloadTimer.current = setTimeout(() => loadState(selectedId), 200)
  }, [selectedId, loadState])

  useEffect(() => {
    wsRef.current?.close()
    wsRef.current = null
    if (!selectedId) return
    const ws = connectInteractionLive({
      interactionId: selectedId,
      baseUrl: BASE,
      getToken,
      refreshToken: refreshAccessToken,
      onEvent: (data) => {
        if (data.event === 'interaction_closed') {
          setCurrent(prev => (prev ? { ...prev, status: 'closed' } : prev))
        }
        scheduleReload()
      },
    })
    wsRef.current = ws
    return () => {
      clearTimeout(reloadTimer.current)
      ws.close()
    }
  }, [selectedId, scheduleReload])

  const joinSession = useCallback((id) => setSelectedId(id), [])

  const leaveSession = useCallback(() => {
    setSelectedId(null)
    clearState()
  }, [clearState])

  const sendQuestion = useCallback(async () => {
    if (!myQuestion.trim() || !selectedId) return
    setSending(true)
    try {
      await askInteractionQuestion(selectedId, { text: myQuestion.trim(), anonymous })
      setMyQuestion('')
      setAnonymous(false)
      await loadState(selectedId)
    } catch (e) {
      Alert.alert('Could not send question', e.message)
    } finally {
      setSending(false)
    }
  }, [myQuestion, anonymous, selectedId, loadState])

  const sendResponse = useCallback(async () => {
    if (!responseDraft.trim() || !selectedId || !liveQuestion || responding) return
    setResponding(true)
    try {
      await respondToLiveQuestion(selectedId, liveQuestion.id, responseDraft.trim())
      setResponseDraft('')
      await loadState(selectedId)
    } catch (e) {
      Alert.alert('Could not send response', e.message)
    } finally {
      setResponding(false)
    }
  }, [responseDraft, selectedId, liveQuestion, responding, loadState])

  const votePoll = useCallback(async () => {
    if (!pollSelection || !poll || voting) return
    setVoting(true)
    try {
      await voteInteractionPoll(poll.id, pollSelection)
      await loadState(selectedId)
    } catch (e) {
      Alert.alert('Could not vote', e.message)
    } finally {
      setVoting(false)
    }
  }, [pollSelection, poll, voting, selectedId, loadState])

  const sendReaction = useCallback(async (reaction) => {
    if (!selectedId) return
    try {
      await sendInteractionReaction(selectedId, reaction)
      setMyReaction(reaction)
      await loadState(selectedId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [selectedId, loadState, showToast])

  const sendIDU = useCallback(async () => {
    if (!selectedId || hasIDU) return
    try {
      await sendInteractionIDU(selectedId)
      setHasIDU(true)
      await loadState(selectedId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [selectedId, hasIDU, loadState, showToast])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    if (selectedId) await loadState(selectedId)
    setRefreshing(false)
  }, [selectedId, loadState])

  // ── No session selected: list what's open ─────────────────────────────────
  if (!selectedId) {
    return (
      <View style={styles.flex}>
        <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
          <Text style={styles.headerTitle}>Class Interaction</Text>
          <Text style={styles.headerSub}>Join a live session to ask questions, vote and react</Text>
        </View>
        {loading ? (
          <View style={styles.empty}>
            <ActivityIndicator color={C.primary} />
          </View>
        ) : interactions.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="chatbubble-outline" size={48} color={C.textHint} />
            <Text style={styles.emptyText}>No open interaction sessions</Text>
            <Text style={styles.emptySub}>Ask your lecturer to start a class interaction.</Text>
          </View>
        ) : (
          <View style={styles.list}>
            <Text style={styles.sectionTitle}>Open sessions</Text>
            {interactions.map(i => (
              <TouchableOpacity
                key={i.id}
                testID={interactions.length === 1 ? 'interaction-session-card' : `interaction-session-${i.id}`}
                style={styles.sessionRow}
                onPress={() => joinSession(i.id)}
              >
                <View style={styles.sessionDotWrap}>
                  <View style={styles.sessionDot} />
                  <View style={styles.sessionInfo}>
                    <Text style={styles.sessionClass}>{i.class_code}</Text>
                    <Text style={styles.sessionName} numberOfLines={1}>{i.class_name}</Text>
                  </View>
                </View>
                <View style={styles.sessionBadge}>
                  <Text style={styles.sessionBadgeText}>Open</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>
    )
  }

  if (loading && !current) {
    return (
      <View style={styles.flex}>
        <View style={styles.empty}><ActivityIndicator color={C.primary} /></View>
      </View>
    )
  }

  if (!current) {
    return (
      <View style={styles.flex}>
        <View style={styles.empty}>
          <Ionicons name="alert-circle-outline" size={48} color={C.textHint} />
          <Text style={styles.emptyText}>Session unavailable</Text>
          <TouchableOpacity style={styles.backToList} onPress={leaveSession}>
            <Text style={styles.backToListText}>Back to open sessions</Text>
          </TouchableOpacity>
        </View>
      </View>
    )
  }

  const isLive = current.status === 'open'
  const latestPoll = poll
  const hasVoted = Boolean(latestPoll?.my_option_id)
  const canVote = isLive && latestPoll?.is_open && !hasVoted
  const canRespond = isLive && liveQuestion?.is_active && !liveQuestion?.my_response
  const pollTotal = latestPoll
    ? latestPoll.options.reduce((s, o) => s + (o.votes ?? 0), 0)
    : 0

  return (
    <View style={styles.flex}>
      {/* Gradient header (S25b): class identity + live pill */}
      <LinearGradient
        colors={[C.primary, C.blueDk]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.header, { paddingTop: insets.top + 12 }]}
      >
        <TouchableOpacity style={styles.back} onPress={leaveSession}>
          <Ionicons name="chevron-back" size={24} color="#fff" />
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{current.class_name}</Text>
        <View style={styles.headerMetaRow}>
          <Text style={styles.headerSub}>{current.class_code}</Text>
          <View style={[styles.livePill, isLive ? styles.livePillOn : styles.livePillOff]}>
            <View style={[styles.liveDot, isLive ? styles.liveDotOn : styles.liveDotOff]} />
            <Text style={[styles.livePillText, isLive ? styles.livePillTextOn : styles.livePillTextOff]}>
              {isLive ? 'Live now' : 'Closed'}
            </Text>
          </View>
        </View>
      </LinearGradient>

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />}
        contentContainerStyle={styles.content}
      >
        {/* Status banner */}
        <View style={[styles.statusBar, isLive ? styles.statusOpen : styles.statusClosed]}>
          <View style={[styles.statusDot, isLive ? styles.statusDotOpen : styles.statusDotClosed]} />
          <Text style={[styles.statusText, isLive ? styles.statusOpenText : styles.statusClosedText]}>
            {isLive ? 'Session is open — participate now' : 'Session is closed'}
          </Text>
        </View>

        {/* Lecturer's live question — time-sensitive, first (S25b) */}
        {liveQuestion && (
          <View style={[styles.card, liveQuestion.is_active ? styles.cardAccentBlue : null]}>
            <View style={styles.cardHeader}>
              <Text style={styles.sectionTitle}>Lecturer's question</Text>
              <View style={[styles.pill, liveQuestion.is_active ? styles.pillLive : styles.pillClosed]}>
                <Text style={[styles.pillText, liveQuestion.is_active ? styles.pillLiveText : styles.pillClosedText]}>
                  {liveQuestion.is_active ? 'Live' : 'Closed'}
                </Text>
              </View>
            </View>
            <Text style={styles.liveQuestion}>{liveQuestion.question}</Text>
            {liveQuestion.my_response ? (
              <View style={styles.myResponse}>
                <Text style={styles.myResponseLabel}>Your response</Text>
                <Text style={styles.myResponseText}>{liveQuestion.my_response}</Text>
              </View>
            ) : (
              <View style={styles.responseRow}>
                <TextInput
                  testID="interaction-response-input"
                  style={[styles.input, styles.responseInput]}
                  value={responseDraft}
                  onChangeText={setResponseDraft}
                  placeholder={canRespond ? 'Your response…' : 'Question closed'}
                  maxLength={2000}
                  editable={canRespond}
                />
                <TouchableOpacity
                  testID="interaction-respond-btn"
                  style={[styles.respondBtn, (!canRespond || responding) && styles.sendBtnDisabled]}
                  onPress={sendResponse}
                  disabled={!responseDraft.trim() || responding || !canRespond}
                >
                  <Text style={styles.sendBtnText}>{responding ? '…' : 'Respond'}</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}

        {/* Live poll */}
        {latestPoll && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.sectionTitle}>Poll</Text>
              <View style={[styles.pill, latestPoll.is_open && isLive ? styles.pillLive : styles.pillClosed]}>
                <Text style={[styles.pillText, latestPoll.is_open && isLive ? styles.pillLiveText : styles.pillClosedText]}>
                  {latestPoll.is_open && isLive ? 'Open' : 'Closed'}
                </Text>
              </View>
            </View>
            <Text style={styles.pollQuestion}>{latestPoll.question}</Text>
            {latestPoll.options.map(opt => {
              const selected = pollSelection === opt.id
              const pct = pollTotal > 0 ? Math.round(((opt.votes ?? 0) / pollTotal) * 100) : 0
              return (
                <TouchableOpacity
                  key={opt.id}
                  testID={`interaction-poll-option-${opt.id}`}
                  style={[
                    styles.pollOption,
                    selected && styles.pollOptionSelected,
                    !canVote && styles.pollOptionLocked,
                  ]}
                  onPress={() => { if (canVote) setPollSelection(opt.id) }}
                  disabled={!canVote}
                >
                  <View style={styles.pollOptionRow}>
                    <Text style={styles.pollOptionText}>{opt.option_text}</Text>
                    <Text style={styles.pollOptionVotes}>{opt.votes ?? 0} vote{(opt.votes ?? 0) !== 1 ? 's' : ''}{!canVote ? ` · ${pct}%` : ''}</Text>
                  </View>
                  {!canVote && (
                    <View style={styles.barTrack}>
                      <View style={[styles.barFill, selected && styles.barFillSelected, { width: `${pct}%` }]} />
                    </View>
                  )}
                  {selected && canVote && <Ionicons name="checkmark-circle" size={20} color={C.primary} />}
                </TouchableOpacity>
              )
            })}
            <TouchableOpacity
              testID="interaction-vote-btn"
              style={[styles.voteBtn, (!pollSelection || !canVote || voting) && styles.voteBtnDisabled]}
              onPress={votePoll}
              disabled={!pollSelection || !canVote || voting}
            >
              <Text style={styles.voteBtnText}>
                {voting ? 'Voting…' : hasVoted ? 'Voted' : 'Vote'}
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Reactions + IDU (FR-507/508) — coloured chips */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Reactions</Text>
          <View style={styles.reactionsRow}>
            {REACTIONS.map(r => {
              const count = reactionCounts[r] ?? 0
              const mine = myReaction === r
              const accent = REACTION_COLOR[r]
              return (
                <TouchableOpacity
                  key={r}
                  testID={`interaction-reaction-${r}`}
                  style={[
                    styles.reactionBtn,
                    { backgroundColor: accent.bg },
                    mine && styles.reactionBtnMine,
                  ]}
                  onPress={() => sendReaction(r)}
                  disabled={!isLive}
                >
                  <Ionicons name={REACTION_ICON[r]} size={18} color={accent.fg} />
                  <View style={styles.reactionLabelWrap}>
                    <Text style={[styles.reactionLabel, { color: accent.fg }, mine && styles.reactionLabelMine]}>
                      {REACTION_LABEL[r]}
                    </Text>
                    <Text style={[styles.reactionCount, { color: accent.fg }, mine && styles.reactionCountMine]}>
                      {count}
                    </Text>
                  </View>
                </TouchableOpacity>
              )
            })}
          </View>
          <View style={styles.iduRow}>
            <TouchableOpacity
              testID="interaction-idu-btn"
              style={[styles.iduBtn, hasIDU && styles.iduBtnDone]}
              onPress={sendIDU}
              disabled={hasIDU || !isLive}
            >
              <Ionicons name="help-buoy" size={20} color={hasIDU ? C.green : C.orange} />
              <Text style={[styles.iduLabel, hasIDU && styles.iduLabelDone]}>{hasIDU ? 'IDU sent' : "I Don't Understand"}</Text>
            </TouchableOpacity>
            <View style={styles.iduCountWrap}>
              <Text style={styles.iduCount}>{iduCount} student{iduCount !== 1 ? 's' : ''}</Text>
            </View>
          </View>
        </View>

        {/* Ask a question */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Ask a question</Text>
          <TextInput
            testID="interaction-question-input"
            style={styles.input}
            value={myQuestion}
            onChangeText={setMyQuestion}
            placeholder="Type your question…"
            maxLength={2000}
            multiline
            numberOfLines={3}
            editable={isLive}
          />
          <View style={styles.toggleRow}>
            <Switch
              testID="interaction-anonymous-toggle"
              value={anonymous}
              onValueChange={setAnonymous}
              disabled={!isLive}
              trackColor={{ false: C.gray300, true: C.primary }}
              thumbColor={anonymous ? C.primary : C.gray500}
            />
            <Text style={styles.toggleLabel}>Anonymous</Text>
          </View>
          <TouchableOpacity
            testID="interaction-ask-btn"
            style={[styles.sendBtn, (sending || !isLive) && styles.sendBtnDisabled]}
            onPress={sendQuestion}
            disabled={!myQuestion.trim() || sending || !isLive}
          >
            <Text style={styles.sendBtnText}>{sending ? 'Sending…' : 'Ask'}</Text>
          </TouchableOpacity>
        </View>

        {/* Own questions */}
        {questions.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Your questions</Text>
            <FlatList
              data={questions}
              keyExtractor={item => String(item.id)}
              scrollEnabled={false}
              renderItem={({ item }) => (
                <View style={styles.questionItem}>
                  <Text style={styles.questionText}>{item.text}</Text>
                  <View style={styles.questionMeta}>
                    <Text style={styles.questionAnon}>{item.anonymous ? 'Anonymous' : 'You'}</Text>
                    <Text style={[styles.questionMetaText, item.answered && styles.questionMetaAnswered]}>
                      · {item.answered ? 'Answered' : 'Open'}
                    </Text>
                  </View>
                </View>
              )}
            />
          </View>
        )}
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { paddingBottom: 24 },
  header: {
    backgroundColor: C.primary,
    paddingHorizontal: 16,
    paddingBottom: 14,
    alignItems: 'flex-start',
    borderBottomLeftRadius: 18,
    borderBottomRightRadius: 18,
  },
  back: { position: 'absolute', top: 12, left: 12, padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#fff', paddingLeft: 28 },
  headerMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 3, paddingLeft: 28 },
  headerSub: { fontSize: 12, color: '#BFDBFE' },
  livePill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(255,255,255,0.18)',
    borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3,
  },
  livePillOff: { backgroundColor: 'rgba(255,255,255,0.12)' },
  liveDot: { width: 6, height: 6, borderRadius: 3 },
  liveDotOn: { backgroundColor: '#86EFAC' },
  liveDotOff: { backgroundColor: '#FCA5A5' },
  livePillText: { fontSize: 10, fontWeight: '700', color: '#fff' },
  livePillTextOff: { color: '#E5E7EB' },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: C.textSub,
    marginHorizontal: 16,
    marginTop: 14,
    marginBottom: 8,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  card: {
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginTop: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 14,
  },
  cardAccentBlue: { borderColor: C.primary, borderWidth: 1.5 },
  input: {
    backgroundColor: C.gray100,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: C.text,
    fontSize: 14,
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 10,
  },
  toggleLabel: { fontSize: 13, color: C.text, marginLeft: 8 },
  sendBtn: {
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  sendBtnDisabled: { backgroundColor: C.gray300 },
  sendBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  voteBtn: {
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  voteBtnDisabled: { backgroundColor: C.gray300 },
  voteBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 10,
    marginHorizontal: 16,
    marginTop: 12,
    borderWidth: 1,
  },
  statusOpen: { backgroundColor: C.greenLt, borderColor: C.green },
  statusClosed: { backgroundColor: C.redLt, borderColor: C.red },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusDotOpen: { backgroundColor: C.green },
  statusDotClosed: { backgroundColor: C.red },
  statusText: { fontSize: 13, fontWeight: '700' },
  statusOpenText: { color: C.greenDk },
  statusClosedText: { color: C.redDk },
  list: { paddingHorizontal: 16 },
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: C.card,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: C.border,
  },
  sessionDotWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sessionDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.green },
  sessionInfo: { flex: 1 },
  sessionClass: { fontSize: 14, fontWeight: '700', color: C.text },
  sessionName: { fontSize: 12, color: C.textSub, marginTop: 2 },
  sessionBadge: { backgroundColor: C.greenLt, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  sessionBadgeText: { fontSize: 11, fontWeight: '700', color: C.greenDk },
  empty: { padding: 40, alignItems: 'center' },
  emptyText: { fontSize: 14, color: C.textSub },
  emptySub: { fontSize: 12, color: C.textHint, marginTop: 6 },
  backToList: { marginTop: 12, padding: 8 },
  backToListText: { fontSize: 13, fontWeight: '700', color: C.primary },
  liveQuestion: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 10 },
  responseRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  responseInput: { flex: 1 },
  respondBtn: {
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 14,
    justifyContent: 'center',
  },
  myResponse: { backgroundColor: C.greenLt, borderRadius: 8, padding: 10 },
  myResponseLabel: { fontSize: 11, fontWeight: '700', color: C.greenDk },
  myResponseText: { fontSize: 14, color: C.text, marginTop: 2 },
  pill: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3 },
  pillLive: { backgroundColor: C.greenLt },
  pillClosed: { backgroundColor: C.gray100 },
  pillText: { fontSize: 10, fontWeight: '700' },
  pillLiveText: { color: C.greenDk },
  pillClosedText: { color: C.textHint },
  pollQuestion: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 10 },
  pollOption: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 8,
    padding: 10,
    marginBottom: 6,
    backgroundColor: C.card,
    flexWrap: 'wrap',
  },
  pollOptionSelected: { borderColor: C.primary, backgroundColor: C.blueLt },
  pollOptionLocked: { opacity: 0.9 },
  pollOptionRow: { flex: 1, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  pollOptionText: { fontSize: 14, color: C.text },
  pollOptionVotes: { fontSize: 12, color: C.textSub },
  barTrack: {
    width: '100%',
    height: 6,
    backgroundColor: C.gray100,
    borderRadius: 3,
    overflow: 'hidden',
    marginTop: 6,
  },
  barFill: { height: '100%', backgroundColor: C.gray300, borderRadius: 3 },
  barFillSelected: { backgroundColor: C.primary },
  reactionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  reactionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  reactionBtnMine: { borderColor: C.primary, borderWidth: 1.5 },
  reactionLabelWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  reactionLabel: { fontSize: 11, fontWeight: '600' },
  reactionLabelMine: { fontWeight: '800' },
  reactionCount: { fontSize: 11, fontWeight: '700' },
  reactionCountMine: { fontWeight: '800' },
  iduRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
  iduBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.orangeLt,
    borderColor: C.orange,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    flex: 1,
  },
  iduBtnDone: { backgroundColor: C.greenLt, borderColor: C.green },
  iduLabel: { fontSize: 13, fontWeight: '700', color: C.orangeDk },
  iduLabelDone: { color: C.greenDk },
  iduCountWrap: { alignItems: 'center', gap: 4, paddingLeft: 8 },
  iduCount: { fontSize: 13, color: C.textSub },
  questionItem: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.gray100 },
  questionText: { fontSize: 14, color: C.text },
  questionMeta: { flexDirection: 'row', gap: 6, marginTop: 4 },
  questionAnon: { fontSize: 11, fontWeight: '700', color: C.primary },
  questionMetaText: { fontSize: 11, color: C.textHint },
  questionMetaAnswered: { color: C.green, fontWeight: '700' },
})
