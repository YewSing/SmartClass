import { useState, useCallback, useEffect, useRef } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator,
  TextInput, Switch, FlatList, Alert, Modal,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
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

const REACTION_LABEL = {
  confused: 'Confused',
  pace_too_fast: 'Too fast',
  pace_too_slow: 'Too slow',
  understood: 'Understood',
  agree: 'Agree',
}
const REACTION_ICON = {
  confused: 'sad-outline',
  pace_too_fast: 'caret-forward-circle-outline',
  pace_too_slow: 'play-back-circle-outline',
  understood: 'checkmark-circle',
  agree: 'thumbs-up',
}

/** Section card: colored title heading (left) with optional `right` node on the same row. */
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
          <View style={styles.flex1} />
          {right}
        </View>
      )}
      {children}
    </View>
  )
}

function Pill({ on, onText = 'Open', offText = 'Closed' }) {
  return (
    <View style={[styles.pill, !on && styles.pillOff]}>
      <View style={[styles.pillDot, { backgroundColor: on ? C.green : C.gray500 }]} />
      <Text style={[styles.pillText, { color: on ? C.greenDk : C.textHint }]}>
        {on ? onText : offText}
      </Text>
    </View>
  )
}

function HistoryModal({ visible, onClose, title, data, empty, keyExtractor, renderItem }) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.sheetWrap}>
        <View style={styles.sheet}>
          <View style={styles.sheetHeader}>
            <Text style={styles.sheetTitle}>{title}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={8} testID="history-modal-close">
              <Ionicons name="close" size={22} color={C.textSub} />
            </TouchableOpacity>
          </View>
          <FlatList
            data={data}
            keyExtractor={keyExtractor}
            renderItem={renderItem}
            ListEmptyComponent={<Text style={styles.sheetEmpty}>{empty}</Text>}
            contentContainerStyle={{ paddingBottom: 24 }}
          />
        </View>
      </View>
    </Modal>
  )
}

export default function Participation({ route }) {
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

  // Reactions / IDU / questions
  const [reactionCounts, setReactionCounts] = useState({})
  const [myReaction, setMyReaction] = useState(null)
  const [iduCount, setIDUCount] = useState(0)
  const [hasIDU, setHasIDU] = useState(false)
  const [questions, setQuestions] = useState([])   // whole-session feed (mine flagged)

  // History modals
  const [showAllQuestions, setShowAllQuestions] = useState(false)
  const [showMyQuestions, setShowMyQuestions] = useState(false)

  const applyState = useCallback((s) => {
    setCurrent(s)
    setPoll(s.current_poll ?? null)
    setPollSelection(s.current_poll?.my_option_id ?? null)
    setLiveQuestion(s.live_question ?? null)
    setReactionCounts(s.reaction_counts ?? {})
    setMyReaction(s.my_reaction ?? null)
    setIDUCount(s.idu_distinct_students ?? 0)
    setHasIDU(Boolean(s.idu_has_signal))
    setQuestions(s.questions ?? s.my_questions ?? [])
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
      ; (async () => {
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

  useEffect(() => {
    if (paramInteractionId && paramInteractionId !== selectedId) setSelectedId(paramInteractionId)
  }, [paramInteractionId])

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

  // Toggle reaction: tapping the active reaction again cancels it (server deletes the row).
  const sendReaction = useCallback(async (reaction) => {
    if (!selectedId) return
    const cancelling = myReaction === reaction
    try {
      await sendInteractionReaction(selectedId, reaction)
      setMyReaction(cancelling ? null : reaction)
      await loadState(selectedId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [selectedId, myReaction, loadState, showToast])

  // Toggle IDU: tapping again cancels the signal.
  const sendIDU = useCallback(async () => {
    if (!selectedId) return
    try {
      const res = await sendInteractionIDU(selectedId)
      setHasIDU(Boolean(res?.has_signal))
      await loadState(selectedId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [selectedId, loadState, showToast])

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
  const hasVoted = Boolean(poll?.my_option_id)
  const canVote = isLive && poll?.is_open && !hasVoted
  const canRespond = isLive && liveQuestion?.is_active && !liveQuestion?.my_response
  const pollTotal = poll ? poll.options.reduce((s, o) => s + (o.votes ?? 0), 0) : 0
  const myQuestions = questions.filter(
    q => q.anonymous === false || q.student_id != null,
  )
  const answeredCount = questions.filter(q => q.answered).length

  return (
    <View style={styles.flex}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <TouchableOpacity style={styles.back} onPress={leaveSession}>
          <Ionicons name="chevron-back" size={24} color={C.textSub} />
        </TouchableOpacity>
        <View style={styles.headerBody}>
          <Text style={styles.headerTitle} numberOfLines={1}>{current.class_name}</Text>
          <Text style={styles.headerSub}>{current.class_code}</Text>
        </View>
        <View style={[styles.livePill, isLive ? styles.livePillOn : styles.livePillOff]}>
          <View style={[styles.liveDot, isLive ? styles.liveDotOn : styles.liveDotOff]} />
          <Text style={[styles.livePillText, isLive ? styles.livePillTextOn : styles.livePillTextOff]}>
            {isLive ? 'Live' : 'Closed'}
          </Text>
        </View>
      </View>

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

        {/* Lecturer's live question — full style card */}
        {liveQuestion && (
          <Section tint={liveQuestion.is_active ? 'purple' : 'gray'} badge="Live question" right={<Pill on={liveQuestion.is_active} />}>
            <Text style={styles.liveQuestionText}>{liveQuestion.question}</Text>
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
                  placeholder={canRespond ? 'Type your response…' : 'Question closed'}
                  maxLength={2000}
                  editable={canRespond}
                />
                <TouchableOpacity
                  testID="interaction-respond-btn"
                  style={[styles.respondBtn, (!canRespond || responding) && styles.sendBtnDisabled]}
                  onPress={sendResponse}
                  disabled={!responseDraft.trim() || responding || !canRespond}
                >
                  <Ionicons name="send" size={16} color="#fff" />
                </TouchableOpacity>
              </View>
            )}
          </Section>
        )}

        {/* Live poll — full-width radio options, one vote */}
        {poll && (
          <Section tint="blue" badge="Live poll" right={<Pill on={poll.is_open && isLive} />}>
            <Text style={styles.pollQuestion}>{poll.question}</Text>
            <Text style={styles.pollNote}>One vote per poll — results show after you vote</Text>
            {poll.options.map(opt => {
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
                  <View style={styles.pollRadioWrap}>
                    <View style={[styles.pollRadio, selected && styles.pollRadioSelected]} />
                    {selected && canVote && <Ionicons name="checkmark" size={16} color="#fff" />}
                  </View>
                  <Text style={styles.pollOptionText}>{opt.option_text}</Text>
                  {!canVote && (
                    <View style={styles.pollResult}>
                      <Text style={styles.pollPct}>{pct}%</Text>
                      <Text style={styles.pollVotes}>{opt.votes ?? 0} vote{(opt.votes ?? 0) !== 1 ? 's' : ''}</Text>
                    </View>
                  )}
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
          </Section>
        )}

        {/* Reactions — tap again to cancel */}
        <Section tint="orange" badge="React">
          <View style={styles.reactionsRow}>
            {Object.entries(REACTION_LABEL).map(([key, label]) => {
              const count = reactionCounts[key] ?? 0
              const mine = myReaction === key
              return (
                <TouchableOpacity
                  key={key}
                  testID={`interaction-reaction-${key}`}
                  style={[styles.reactionBtn, mine && styles.reactionBtnMine]}
                  onPress={() => sendReaction(key)}
                  disabled={!isLive}
                >
                  <Ionicons name={REACTION_ICON[key]} size={18} color={mine ? C.primary : C.textSub} />
                  <View style={styles.reactionLabelWrap}>
                    <Text style={[styles.reactionLabel, mine && styles.reactionLabelMine]}>{label}</Text>
                    <Text style={[styles.reactionCount, mine && styles.reactionCountMine]}>{count}</Text>
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
              disabled={!isLive}
            >
              <Ionicons name="hand-left-outline" size={20} color={hasIDU ? C.red : C.orangeDk} />
              <View style={styles.iduMeta}>
                <Text style={[styles.iduLabel, hasIDU && styles.iduLabelDone]}>I Don't Understand</Text>
                <Text style={[styles.iduLabelSub, hasIDU && styles.iduLabelSubDone]}>
                  {hasIDU ? 'Tap again to cancel' : 'Tap to raise your hand anonymously'}
                </Text>
              </View>
            </TouchableOpacity>
            <View style={styles.iduCountWrap}>
              <Text style={styles.iduCount}>{iduCount}</Text>
              <Text style={styles.iduCountLabel}>student{iduCount !== 1 ? 's' : ''}</Text>
            </View>
          </View>
        </Section>

        {/* Ask a question */}
        <Section tint="yellow" badge="Ask a question" right={<Text style={styles.sentCount}>{myQuestions.length} sent</Text>}>
          <TextInput
            testID="interaction-question-input"
            style={[styles.input, styles.textArea]}
            value={myQuestion}
            onChangeText={setMyQuestion}
            placeholder="Type your question for the lecturer..."
            maxLength={2000}
            multiline
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
            <Text style={styles.toggleLabel}>Send anonymously</Text>
            <TouchableOpacity
              testID="interaction-ask-btn"
              style={[styles.sendBtn, (sending || !isLive || !myQuestion.trim()) && styles.sendBtnDisabled]}
              onPress={sendQuestion}
              disabled={!myQuestion.trim() || sending || !isLive}
            >
              <Ionicons name="send" size={14} color="#fff" />
              <Text style={styles.sendBtnText}>{sending ? 'Sending…' : 'Send'}</Text>
            </TouchableOpacity>
          </View>
        </Section>

        {/* Session question feed — what the whole class asked, mine highlighted */}
        <Section tint="gray" badge="Questions" right={<Text style={styles.sentCount}>{questions.length - answeredCount} open</Text>}>
          {questions.length === 0 ? (
            <Text style={styles.emptyLine}>No questions asked yet.</Text>
          ) : (
            <>
              {questions.slice(0, 3).map(q => {
                const mine = myQuestions.some(m => m.id === q.id)
                return (
                  <View
                    key={q.id}
                    style={[styles.questionItem, q.answered ? styles.questionItemAnswered : styles.questionItemOpen, mine && styles.questionItemMine]}
                  >
                    <View style={styles.questionMetaTop}>
                      <Text style={styles.questionAuthor}>
                        {q.anonymous ? 'Anonymous' : (q.student_name ?? 'Student')}
                      </Text>
                      {mine && (
                        <View style={styles.minePill}><Text style={styles.minePillText}>Mine</Text></View>
                      )}
                      <View style={styles.flex1} />
                      <Text style={[styles.questionState, q.answered && styles.questionStateAnswered]}>
                        {q.answered ? '✓ Answered' : 'Waiting'}
                      </Text>
                    </View>
                    <Text style={styles.questionText}>{q.text}</Text>
                  </View>
                )
              })}
              {questions.length > 3 && (
                <TouchableOpacity
                  testID="interaction-see-all-questions"
                  style={styles.seeAllBtn}
                  onPress={() => setShowAllQuestions(true)}
                >
                  <Text style={styles.seeAllText}>See all {questions.length} questions</Text>
                  <Ionicons name="chevron-forward" size={14} color={C.primary} />
                </TouchableOpacity>
              )}
            </>
          )}
        </Section>
        <View style={{ height: 24 }} />
      </ScrollView>

      {/* Full question feed (most recent kept inline above) */}
      <HistoryModal
        visible={showAllQuestions}
        onClose={() => setShowAllQuestions(false)}
        title={`Questions (${questions.length})`}
        data={questions}
        keyExtractor={q => String(q.id)}
        empty="No questions asked yet."
        renderItem={({ item }) => {
          const mine = myQuestions.some(m => m.id === item.id)
          return (
            <View
              style={[styles.sheetItem, item.answered ? styles.questionItemAnswered : styles.questionItemOpen, mine && styles.questionItemMine]}
            >
              <View style={styles.questionMetaTop}>
                <Text style={styles.questionAuthor}>
                  {item.anonymous ? 'Anonymous' : (item.student_name ?? 'Student')}
                </Text>
                {mine && (
                  <View style={styles.minePill}><Text style={styles.minePillText}>Mine</Text></View>
                )}
                <View style={styles.flex1} />
                <Text style={[styles.questionState, item.answered && styles.questionStateAnswered]}>
                  {item.answered ? '✓ Answered' : 'Waiting'}
                </Text>
              </View>
              <Text style={styles.questionText}>{item.text}</Text>
            </View>
          )
        }}
      />

      {/* My questions only */}
      <HistoryModal
        visible={showMyQuestions}
        onClose={() => setShowMyQuestions(false)}
        title={`My questions (${myQuestions.length})`}
        data={myQuestions}
        keyExtractor={q => String(q.id)}
        empty="You haven't asked anything yet."
        renderItem={({ item }) => (
          <View style={[styles.sheetItem, item.answered ? styles.questionItemAnswered : styles.questionItemOpen]}>
            <Text style={styles.questionText}>{item.text}</Text>
            <Text style={[styles.questionState, item.answered && styles.questionStateAnswered]}>
              {item.answered ? '✓ Answered' : 'Waiting for an answer'}
            </Text>
          </View>
        )}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { paddingBottom: 24 },
  header: {
    paddingHorizontal: 16,
    paddingBottom: 14,
    alignItems: 'center',
    justifyContent: 'space-between',
    flexDirection: 'row',
  },
  back: { padding: 4 },
  headerBody: { flex: 1 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: C.text },
  headerSub: { fontSize: 12, color: C.textSub },
  livePill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4,
  },
  livePillOn: { backgroundColor: 'rgba(16, 185, 129, 0.15)' },
  livePillOff: { backgroundColor: 'rgba(220, 38, 38, 0.12)' },
  liveDot: { width: 7, height: 7, borderRadius: 4 },
  liveDotOn: { backgroundColor: C.green },
  liveDotOff: { backgroundColor: C.red },
  livePillText: { fontSize: 11, fontWeight: '700' },
  livePillTextOn: { color: C.greenDk },
  livePillTextOff: { color: C.redDk },
  // Tinted section card
  section: {
    borderRadius: 14,
    marginHorizontal: 16,
    marginTop: 14,
    padding: 14,
    backgroundColor: C.card,
  },
  sectionBadge: {
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  sectionBadgeText: { fontSize: 10, fontWeight: '800' },
  sectionHead: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 10,
  },
  sentCount: { fontSize: 11, fontWeight: '700', color: C.textHint },
  emptyLine: { fontSize: 13, color: C.textHint, marginTop: 4 },
  // Pills
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderRadius: 20, paddingHorizontal: 9, paddingVertical: 4,
    backgroundColor: C.greenLt,
  },
  pillOff: { backgroundColor: C.gray100 },
  pillDot: { width: 7, height: 7, borderRadius: 4 },
  pillText: { fontSize: 11, fontWeight: '700' },
  // Inputs
  input: {
    backgroundColor: C.gray100,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: C.text,
    fontSize: 14,
  },
  textArea: { minHeight: 80, textAlignVertical: 'top' },
  toggleRow: {
    flexDirection: 'row', alignItems: 'center', marginTop: 10, gap: 8,
  },
  toggleLabel: { fontSize: 13, color: C.text, flex: 1 },
  sendBtn: {
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  sendBtnDisabled: { backgroundColor: C.gray300 },
  sendBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  voteBtn: {
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingVertical: 11,
    alignItems: 'center',
    marginTop: 4,
  },
  voteBtnDisabled: { backgroundColor: C.gray300 },
  voteBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  // Status banner
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
  // Session picker
  list: { paddingHorizontal: 16 },
  sectionTitle: {
    fontSize: 13, fontWeight: '700', color: C.textSub, marginTop: 14, marginBottom: 8,
  },
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
  // Live question
  liveQuestionText: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 8 },
  responseRow: { flexDirection: 'row', gap: 8 },
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
  // Poll
  pollQuestion: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 6 },
  pollNote: { fontSize: 11, color: C.textHint, marginBottom: 10 },
  pollOption: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    marginBottom: 8,
    backgroundColor: C.card,
  },
  pollOptionSelected: { borderColor: C.primary, backgroundColor: C.blueLt },
  pollOptionLocked: { opacity: 0.85 },
  pollRadioWrap: { alignItems: 'center', justifyContent: 'center' },
  pollRadio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: C.border },
  pollRadioSelected: { borderColor: C.primary, backgroundColor: C.primary },
  pollOptionText: { flex: 1, fontSize: 14, color: C.text, marginLeft: 10, marginRight: 8 },
  pollResult: { flexDirection: 'row', gap: 4 },
  pollPct: { fontSize: 12, fontWeight: '700', color: C.primary },
  pollVotes: { fontSize: 12, color: C.textSub },
  // Reactions
  reactionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  reactionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: C.gray100,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  reactionBtnMine: { borderColor: C.primary, borderWidth: 1.5, backgroundColor: C.blueLt },
  reactionLabelWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  reactionLabel: { fontSize: 11, fontWeight: '600' },
  reactionLabelMine: { fontWeight: '800' },
  reactionCount: { fontSize: 11, fontWeight: '700' },
  reactionCountMine: { fontWeight: '800' },
  // IDU
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
  iduBtnDone: { backgroundColor: C.redLt, borderColor: C.red },
  iduLabel: { fontSize: 13, fontWeight: '700', color: C.orangeDk },
  iduLabelDone: { color: C.redDk },
  iduMeta: { flex: 1 },
  iduLabelSub: { fontSize: 10, color: C.textHint, marginTop: 1 },
  iduLabelSubDone: { color: C.redDk },
  iduCountWrap: { alignItems: 'center', gap: 4, paddingLeft: 8 },
  iduCount: { fontSize: 20, fontWeight: '800', color: C.orangeDk },
  iduCountLabel: { fontSize: 12, color: C.textSub },
  // Question feed
  questionItem: {
    borderRadius: 10, padding: 10, marginBottom: 8,
    borderWidth: 1, borderColor: 'transparent',
    backgroundColor: C.gray50,
  },
  questionItemOpen: { backgroundColor: C.blueLt, borderColor: C.primary },
  questionItemAnswered: { backgroundColor: C.gray50, borderColor: C.border, opacity: 0.85 },
  questionItemMine: { borderLeftWidth: 3, borderLeftColor: C.primary },
  questionMetaTop: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  questionAuthor: { fontSize: 11, fontWeight: '700', color: C.textSub },
  minePill: { backgroundColor: C.blueLt, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1 },
  minePillText: { fontSize: 9, fontWeight: '800', color: C.primary },
  questionState: { fontSize: 11, fontWeight: '700', color: C.textHint },
  questionStateAnswered: { color: C.greenDk },
  questionText: { fontSize: 14, color: C.text },
  seeAllBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 2, paddingVertical: 8, marginTop: 2,
    borderTopWidth: 1, borderTopColor: C.gray100,
  },
  seeAllText: { fontSize: 12, fontWeight: '700', color: C.primary },
  // Bottom sheet
  sheetWrap: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(15, 23, 42, 0.45)' },
  sheet: {
    backgroundColor: C.card,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    maxHeight: '82%', paddingHorizontal: 16, paddingTop: 14, paddingBottom: 20,
  },
  sheetHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10,
  },
  sheetTitle: { fontSize: 16, fontWeight: '800', color: C.text },
  sheetEmpty: { fontSize: 13, color: C.textHint, textAlign: 'center', paddingVertical: 24 },
  sheetItem: {
    borderRadius: 10, padding: 10, marginBottom: 8,
    borderWidth: 1, borderColor: C.border,
  },
})
