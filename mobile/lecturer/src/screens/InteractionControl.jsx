import { useState, useEffect, useCallback, useRef } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, TextInput,
  RefreshControl, Alert, ActivityIndicator, Modal, FlatList,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import Topbar from '../components/Topbar'
import { useLecturer } from '../context/LecturerContext'
import { getToken, refreshAccessToken, BASE } from '../services/client'
import {
  getInteraction, getOpenInteractions, getInteractions,
  createPoll, closePoll, getPolls, postLiveQuestion, getLiveQuestion,
  markQuestionAnswered, getQuestions, getReactions, getIduCount,
} from '../services/api'
import { connectInteractionLive } from '../services/interactionLive'
import { C } from '../theme'

const REACTIONS = ['understood', 'agree', 'confused', 'pace_too_fast', 'pace_too_slow']
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
  understood: 'checkmark-circle-outline',
  agree: 'thumbs-up-outline',
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
    <View style={[styles.pill, on ? styles.pillOn : styles.pillOff]}>
      <View style={[styles.pillDot, { backgroundColor: on ? C.green : C.gray500 }]} />
      <Text style={[styles.pillText, { color: on ? C.greenDk : C.textHint }]}>
        {on ? onText : offText}
      </Text>
    </View>
  )
}

/** Modal sheet listing the full history of one section (polls, questions, responses…). */
function HistoryModal({ visible, onClose, title, empty, renderItem, data, keyExtractor }) {
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

/**
 * The lecturer's live view of one interaction session (UC-501 step 4, S26/S29).
 * Layout mirrors the student participation style: one card per section, each showing
 * the most recent item with a "See all" button that opens the full history in a modal —
 * the main controls stay visible no matter how much arrives during the session.
 */
export default function InteractionControl({ route, navigation }) {
  const { showToast } = useLecturer()
  const insets = useSafeAreaInsets()
  const wsRef = useRef(null)
  const reloadTimer = useRef(null)

  const paramInteractionId = route.params?.interaction_id
  const paramOccurrenceId = route.params?.occurrence_id

  const [interaction, setInteraction] = useState(null)
  const [fallbackList, setFallbackList] = useState([])
  const [loading, setLoading] = useState(Boolean(paramInteractionId || paramOccurrenceId))
  const [refreshing, setRefreshing] = useState(false)

  // Live data
  const [polls, setPolls] = useState([])
  const [liveQuestion, setLiveQuestion] = useState(null)
  const [questions, setQuestions] = useState([])
  const [reactionCounts, setReactionCounts] = useState({})
  const [iduCount, setIDUCount] = useState(0)

  // History modals
  const [showAllQuestions, setShowAllQuestions] = useState(false)
  const [showAllPolls, setShowAllPolls] = useState(false)
  const [showAllResponses, setShowAllResponses] = useState(false)

  // Poll creation state
  const [showPollForm, setShowPollForm] = useState(false)
  const [pollDraft, setPollDraft] = useState('')
  const [pollOptions, setPollOptions] = useState(['', ''])
  const [creatingPoll, setCreatingPoll] = useState(false)

  // Live question state
  const [showLiveForm, setShowLiveForm] = useState(false)
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
    const results = await Promise.allSettled([
      getPolls(id), getLiveQuestion(id), getQuestions(id), getReactions(id), getIduCount(id),
    ])
    const value = (i) => (results[i].status === 'fulfilled' ? results[i].value : null)
    setPolls(value(0) ?? [])
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
          // question_asked / question_answered included: a student's new question
          // (or a mark-answered from another device) refreshes the list automatically.
          case 'question_asked':
          case 'question_answered':
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
      setShowPollForm(false)
      await loadLive(interactionId)
      showToast('Poll created', 'success')
    } catch (e) {
      Alert.alert('Could not create poll', e.message)
    } finally {
      setCreatingPoll(false)
    }
  }, [pollDraft, pollOptions, creatingPoll, interactionId, createPoll, loadLive, showToast])

  // FR-504: close voting on this poll — the session stays open.
  const closePollAction = useCallback(async (p) => {
    try {
      await closePoll(interactionId, p.id)
      await loadLive(interactionId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [interactionId, closePoll, loadLive, showToast])

  const postLiveQuestionAction = useCallback(async () => {
    if (!liveDraft.trim() || !interactionId || postingQuestion) return
    setPostingQuestion(true)
    try {
      await postLiveQuestion(interactionId, liveDraft.trim())
      setLiveDraft('')
      setShowLiveForm(false)
      await loadLive(interactionId)
      showToast('Question posted to the class', 'success')
    } catch (e) {
      Alert.alert('Could not post question', e.message)
    } finally {
      setPostingQuestion(false)
    }
  }, [liveDraft, interactionId, postingQuestion, postLiveQuestion, loadLive, showToast])

  // FR-502/503: mark a student question as answered.
  const markAnswered = useCallback(async (question) => {
    if (!interactionId || question.answered) return
    try {
      await markQuestionAnswered(interactionId, question.id)
      await loadLive(interactionId)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }, [interactionId, markQuestionAnswered, showToast, loadLive])

  // Derived: newest first everywhere.
  const openQuestions = questions.filter(q => !q.answered)
  const sortedQuestions = [...openQuestions, ...questions.filter(q => q.answered)]
  const latestQuestion = sortedQuestions[0] ?? null
  const latestPoll = polls[0] ?? null
  const totalResponses = liveQuestion?.responses?.length ?? 0
  const totalReactions = Object.values(reactionCounts).reduce((s, v) => s + (v ?? 0), 0)
  const topReaction = REACTIONS.reduce(
    (best, r) => ((reactionCounts[r] ?? 0) > (reactionCounts[best] ?? 0) ? r : best), null,
  )

  const headerSub = interaction
    ? `${interaction.class_code} · ${isOpen ? 'Open' : 'Closed'}`
    : paramInteractionId
      ? 'Loading…'
      : 'No open session'

  // ── Resolving / empty states ───────────────────────────────────────────────
  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title="Interaction" sub={headerSub} onBack={() => navigation.goBack()} />
        <View style={styles.center}><ActivityIndicator color={C.primary} /></View>
      </View>
    )
  }

  if (!interactionId) {
    return (
      <View style={styles.flex}>
        <Topbar title="Interaction" sub={headerSub} onBack={() => navigation.goBack()} />
        {fallbackList.length > 0 ? (
          <ScrollView style={styles.flex} contentContainerStyle={styles.content}>
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
                    <Text style={styles.sessionClass}>{s.class_code}</Text>
                    <Text style={styles.sessionSub}>{s.class_name}</Text>
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
        )}
      </View>
    )
  }

  // ── Live control screen ────────────────────────────────────────────────────
  return (
    <View style={styles.flex}>
      <Topbar title="Interaction" sub={headerSub} onBack={() => navigation.goBack()} />

      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />}
        contentContainerStyle={styles.content}
      >
        {/* Class pulse — what needs attention right now */}
        <Section tint="yellow" badge="Live status" style={styles.sectionTight}>
          <View style={styles.pulseRow}>
            <View style={[styles.pulseTile, { backgroundColor: C.orangeLt }]}>
              <Ionicons name="hand-left-outline" size={15} color={C.orangeDk} />
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
        </Section>

        {/* Student questions — the most recent one inline, history in a modal */}
        <Section tint="gray" badge="Student questions" right={<Pill on={true} onText={`${openQuestions.length} open`} />}>
          {latestQuestion ? (
            <>
              <View style={[styles.questionItem, latestQuestion.answered ? styles.questionItemAnswered : styles.questionItemOpen]}>
                <Text style={styles.questionText}>{latestQuestion.text}</Text>
                <View style={styles.questionMeta}>
                  {latestQuestion.anonymous ? (
                    <View style={styles.anonPill}>
                      <Ionicons name="eye-off-outline" size={10} color={C.gray600} />
                      <Text style={styles.anonPillText}>Anonymous</Text>
                    </View>
                  ) : (
                    <Text style={styles.questionAuthorName} numberOfLines={1}>
                      {latestQuestion.student_name ?? 'Student'}
                    </Text>
                  )}
                  <Text style={[styles.questionMetaText, latestQuestion.answered && styles.questionMetaAnswered]}>
                    {latestQuestion.answered ? 'Answered' : 'Needs an answer'}
                  </Text>
                  {!latestQuestion.answered && isOpen && (
                    <TouchableOpacity
                      testID={`interaction-mark-answered-${latestQuestion.id}`}
                      style={styles.markBtn}
                      onPress={() => markAnswered(latestQuestion)}
                    >
                      <Ionicons name="checkmark" size={12} color={C.greenDk} />
                      <Text style={styles.markBtnText}>Mark answered</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
              {questions.length > 1 && (
                <TouchableOpacity
                  testID="interaction-see-all-questions"
                  style={styles.seeAllBtn}
                  onPress={() => setShowAllQuestions(true)}
                >
                  <Text style={styles.seeAllText}>
                    See all {questions.length} questions
                  </Text>
                  <Ionicons name="chevron-forward" size={14} color={C.primary} />
                </TouchableOpacity>
              )}
            </>
          ) : (
            <Text style={styles.emptyLine}>No questions yet.</Text>
          )}
        </Section>

        {/* Live question to the class */}
        <Section tint="purple" badge="Live question" right={liveQuestion ? <Pill on={liveQuestion.is_active} /> : null}>
          {liveQuestion ? (
            <>
              <Text style={styles.liveQuestionText}>{liveQuestion.question}</Text>
              <View style={styles.sectionHead}>
                <Text style={styles.responsesTitle}>
                  {totalResponses} response{totalResponses === 1 ? '' : 's'}
                </Text>
                {totalResponses > 0 && (
                  <TouchableOpacity
                    testID="interaction-see-all-responses"
                    style={styles.seeAllBtnInline}
                    onPress={() => setShowAllResponses(true)}
                  >
                    <Text style={styles.seeAllText}>See all</Text>
                    <Ionicons name="chevron-forward" size={14} color={C.primary} />
                  </TouchableOpacity>
                )}
              </View>
              {liveQuestion.responses?.length > 0 && (
                <View style={styles.responseItem}>
                  <Text style={styles.responseText} numberOfLines={3}>
                    {liveQuestion.responses[0].response}
                  </Text>
                </View>
              )}
              {!liveQuestion.is_active && isOpen && (
                <Text style={styles.emptyLine}>Closed — post a new question below.</Text>
              )}
            </>
          ) : (
            <Text style={styles.emptyLine}>Nothing asked to the class yet.</Text>
          )}
          <TouchableOpacity
            testID="interaction-ask-class-toggle"
            style={[styles.actionBtn, styles.actionBtnBlue, !isOpen && styles.btnDisabled]}
            onPress={() => setShowLiveForm(true)}
            disabled={!isOpen}
          >
            <Ionicons name="megaphone-outline" size={16} color="#fff" />
            <Text style={styles.actionBtnText}>{liveQuestion ? 'Ask a new question' : 'Ask the class'}</Text>
          </TouchableOpacity>
        </Section>

        {/* Latest poll with results */}
        <Section tint="blue" badge="Poll" right={latestPoll ? <Pill on={latestPoll.is_open} onText="Open" offText="Closed" /> : null}>
          {latestPoll ? (
            <>
              <Text style={styles.pollQuestion}>{latestPoll.question}</Text>
              {latestPoll.options.map(o => {
                const total = latestPoll.options.reduce((s, o2) => s + (o2.votes ?? 0), 0)
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
              <View style={styles.rowGap}>
                {latestPoll.is_open && (
                  <TouchableOpacity
                    testID="interaction-close-poll-btn"
                    style={[styles.actionBtn, styles.actionBtnRed, !isOpen && styles.btnDisabled]}
                    onPress={() => closePollAction(latestPoll)}
                    disabled={!isOpen}
                  >
                    <Ionicons name="lock-closed-outline" size={15} color="#fff" />
                    <Text style={styles.actionBtnText}>Close voting</Text>
                  </TouchableOpacity>
                )}
                {polls.length > 1 && (
                  <TouchableOpacity
                    testID="interaction-see-all-polls"
                    style={[styles.actionBtn, styles.actionBtnGhost]}
                    onPress={() => setShowAllPolls(true)}
                  >
                    <Ionicons name="stats-chart-outline" size={15} color={C.primary} />
                    <Text style={[styles.actionBtnText, { color: C.primary }]}>
                      See all {polls.length} polls
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
            </>
          ) : (
            <Text style={styles.emptyLine}>No poll yet.</Text>
          )}
          <TouchableOpacity
            testID="interaction-create-poll-toggle"
            style={[styles.actionBtn, styles.actionBtnBlue, !isOpen && styles.btnDisabled]}
            onPress={() => setShowPollForm(true)}
            disabled={!isOpen}
          >
            <Ionicons name="add-circle-outline" size={16} color="#fff" />
            <Text style={styles.actionBtnText}>Create a poll</Text>
          </TouchableOpacity>
        </Section>

        <View style={{ height: 24 }} />
      </ScrollView>

      {/* ── History modals ── */}
      <HistoryModal
        visible={showAllQuestions}
        onClose={() => setShowAllQuestions(false)}
        title={`All questions (${questions.length})`}
        data={sortedQuestions}
        keyExtractor={q => String(q.id)}
        empty="No questions yet."
        renderItem={({ item }) => (
          <View style={[styles.sheetItem, item.answered ? styles.questionItemAnswered : styles.questionItemOpen]}>
            <Text style={styles.questionText}>{item.text}</Text>
            <View style={styles.questionMeta}>
              {item.anonymous ? (
                <View style={styles.anonPill}>
                  <Ionicons name="eye-off-outline" size={10} color={C.gray600} />
                  <Text style={styles.anonPillText}>Anonymous</Text>
                </View>
              ) : (
                <Text style={styles.questionAuthorName} numberOfLines={1}>
                  {item.student_name ?? 'Student'}
                </Text>
              )}
              <Text style={[styles.questionMetaText, item.answered && styles.questionMetaAnswered]}>
                {item.answered ? 'Answered' : 'Needs an answer'}
              </Text>
              {!item.answered && isOpen && (
                <TouchableOpacity
                  testID={`interaction-mark-answered-${item.id}`}
                  style={styles.markBtn}
                  onPress={() => markAnswered(item)}
                >
                  <Ionicons name="checkmark" size={12} color={C.greenDk} />
                  <Text style={styles.markBtnText}>Mark answered</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        )}
      />

      <HistoryModal
        visible={showAllPolls}
        onClose={() => setShowAllPolls(false)}
        title={`All polls (${polls.length})`}
        data={polls}
        keyExtractor={p => String(p.id)}
        empty="No polls yet."
        renderItem={({ item }) => (
          <View style={styles.sheetItem}>
            <View style={styles.sectionHead}>
              <Text style={styles.pollQuestion} numberOfLines={2}>{item.question}</Text>
              <Pill on={item.is_open} />
            </View>
            {item.options.map(o => {
              const total = item.options.reduce((s, o2) => s + (o2.votes ?? 0), 0)
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
                </View>
              )
            })}
            {item.is_open && (
              <TouchableOpacity
                testID={`interaction-close-poll-${item.id}`}
                style={[styles.markBtn, { alignSelf: 'flex-start' }]}
                onPress={() => closePollAction(item)}
              >
                <Ionicons name="lock-closed-outline" size={12} color={C.red} />
                <Text style={[styles.markBtnText, { color: C.red }]}>Close voting</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      />

      <HistoryModal
        visible={showAllResponses}
        onClose={() => setShowAllResponses(false)}
        title={`Responses (${totalResponses})`}
        data={liveQuestion?.responses ?? []}
        keyExtractor={r => String(r.id)}
        empty="No responses yet."
        renderItem={({ item }) => (
          <View style={styles.sheetItem}>
            <Text style={styles.sheetItemName}>{item.student_name}</Text>
            <Text style={styles.responseText}>{item.response}</Text>
          </View>
        )}
      />

      {/* ── Compose modals ── */}
      <Modal visible={showPollForm} animationType="slide" transparent onRequestClose={() => setShowPollForm(false)}>
        <View style={styles.sheetWrap}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Create a poll</Text>
              <TouchableOpacity onPress={() => setShowPollForm(false)} hitSlop={8}>
                <Ionicons name="close" size={22} color={C.textSub} />
              </TouchableOpacity>
            </View>
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
              style={[styles.actionBtn, styles.actionBtnBlue, (creatingPoll || !isOpen) && styles.btnDisabled]}
              onPress={createPollAction}
              disabled={creatingPoll || !isOpen}
            >
              <Text style={styles.actionBtnText}>{creatingPoll ? 'Creating…' : 'Create poll'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Modal visible={showLiveForm} animationType="slide" transparent onRequestClose={() => setShowLiveForm(false)}>
        <View style={styles.sheetWrap}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Ask the class</Text>
              <TouchableOpacity onPress={() => setShowLiveForm(false)} hitSlop={8}>
                <Ionicons name="close" size={22} color={C.textSub} />
              </TouchableOpacity>
            </View>
            <TextInput
              testID="interaction-live-question-input"
              style={[styles.input, styles.textArea]}
              value={liveDraft}
              onChangeText={setLiveDraft}
              placeholder="Post a live question…"
              maxLength={500}
              multiline
              editable={isOpen}
            />
            <TouchableOpacity
              testID="interaction-post-question-btn"
              style={[styles.actionBtn, styles.actionBtnBlue, (!liveDraft.trim() || postingQuestion || !isOpen) && styles.btnDisabled]}
              onPress={postLiveQuestionAction}
              disabled={!liveDraft.trim() || postingQuestion || !isOpen}
            >
              <Text style={styles.actionBtnText}>{postingQuestion ? 'Posting…' : 'Post question'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <View style={{ height: insets.bottom }} />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { paddingBottom: 24 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  empty: { padding: 40, alignItems: 'center' },
  emptyText: { fontSize: 14, color: C.textSub, marginTop: 8 },
  emptySub: { fontSize: 12, color: C.textHint, marginTop: 6 },
  // Tinted section card (participation style)
  section: {
    borderRadius: 14,
    marginHorizontal: 16,
    marginTop: 12,
    padding: 14,
    backgroundColor: C.card,
  },
  sectionTight: { marginTop: 12 },
  sectionBadge: {
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  sectionBadgeText: { fontSize: 10, fontWeight: '800' },
  sentCount: { fontSize: 11, fontWeight: '700', color: C.greenDk },
  sectionHead: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 8, marginTop: 2,
  },
  sectionHeadTitle: { fontSize: 14, fontWeight: '700', color: C.text, flex: 1 },
  countBadge: { backgroundColor: C.blueLt, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  questionAuthorName: { fontSize: 12, fontWeight: '700', color: C.blueDk, flexShrink: 1 },
  countBadgeText: { fontSize: 11, fontWeight: '700', color: C.primary },
  emptyLine: { fontSize: 13, color: C.textHint, marginTop: 4, marginBottom: 4 },
  // Pills
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderRadius: 20, paddingHorizontal: 9, paddingVertical: 4,
    backgroundColor: C.gray100,
  },
  pillOn: { backgroundColor: C.greenLt },
  pillOff: { backgroundColor: C.gray100 },
  pillDot: { width: 7, height: 7, borderRadius: 4 },
  pillText: { fontSize: 11, fontWeight: '700' },
  // See-all
  seeAllBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 2, paddingVertical: 8, marginTop: 2,
    borderTopWidth: 1, borderTopColor: C.gray100,
  },
  seeAllBtnInline: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  seeAllText: { fontSize: 12, fontWeight: '700', color: C.primary },
  // Action buttons
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, borderRadius: 10, paddingVertical: 11, marginTop: 10,
  },
  actionBtnBlue: { backgroundColor: C.primary },
  actionBtnRed: { backgroundColor: C.red },
  actionBtnGhost: { backgroundColor: C.gray100, marginTop: 6 },
  btnDisabled: { opacity: 0.5 },
  actionBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  rowGap: { gap: 6 },
  // Session picker rows
  sessionRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: C.card, marginHorizontal: 16, marginBottom: 8,
    borderRadius: 10, borderWidth: 1, borderColor: C.border, padding: 12,
  },
  sessionDotWrap: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sessionDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.green },
  sessionClass: { fontSize: 14, fontWeight: '700', color: C.text },
  sessionSub: { fontSize: 12, color: C.textSub, marginTop: 2 },
  // Pulse
  pulseRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  pulseTile: {
    flex: 1, borderRadius: 10, alignItems: 'center',
    paddingVertical: 10, paddingHorizontal: 4, gap: 2,
  },
  pulseNum: { fontSize: 20, fontWeight: '800' },
  pulseLabel: { fontSize: 10, fontWeight: '600', textAlign: 'center' },
  reactionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
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
    borderRadius: 10, padding: 10, marginBottom: 6,
    borderWidth: 1, borderColor: 'transparent',
  },
  questionItemOpen: { backgroundColor: C.blueLt, borderColor: C.primary },
  questionItemAnswered: { backgroundColor: C.gray50, borderColor: C.gray300, opacity: 0.85 },
  questionText: { fontSize: 14, color: C.text, fontWeight: '500' },
  anonPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: C.card, borderRadius: 8, paddingHorizontal: 6,
    paddingVertical: 3,
  },
  anonPillText: { fontSize: 10, fontWeight: '700', color: C.gray600 },
  questionMeta: { flexDirection: 'row', gap: 8, marginTop: 6, alignItems: 'center', flexWrap: 'wrap' },
  questionMetaText: { fontSize: 11, color: C.textHint },
  questionMetaAnswered: { color: C.green, fontWeight: '700' },
  markBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 8, paddingVertical: 4,
    backgroundColor: C.card, borderRadius: 6, borderWidth: 1, borderColor: C.green,
  },
  markBtnText: { fontSize: 11, fontWeight: '700', color: C.greenDk },
  // Live question + responses
  liveQuestionText: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 8 },
  responsesTitle: { fontSize: 12, fontWeight: '700', color: C.textSub },
  responseItem: { paddingVertical: 8, backgroundColor: C.gray50, borderRadius: 8, marginBottom: 4, paddingHorizontal: 10 },
  responseText: { fontSize: 13, color: C.text },
  sheetItemName: { fontSize: 11, fontWeight: '700', color: C.primary, marginBottom: 2 },
  // Poll bars
  pollQuestion: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 10, flexShrink: 1 },
  barCol: { marginBottom: 10 },
  barRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  barOptLabel: { fontSize: 13, color: C.text },
  barOptPct: { fontSize: 13, fontWeight: '700', color: C.primary },
  barTrack: { height: 8, backgroundColor: C.gray100, borderRadius: 4, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: C.primary, borderRadius: 4 },
  barCount: { fontSize: 12, color: C.textSub, marginTop: 2 },
  // Compose form
  input: {
    backgroundColor: C.gray100, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, color: C.text, fontSize: 14, marginBottom: 6,
  },
  textArea: { minHeight: 90, textAlignVertical: 'top' },
  optionRow: {
    flexDirection: 'row', gap: 8, alignItems: 'center',
    backgroundColor: C.gray100, borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 8, marginTop: 6,
  },
  optionInput: { flex: 1, fontSize: 14, color: C.text },
  addOption: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, paddingVertical: 4 },
  addOptionText: { fontSize: 13, color: C.primary, fontWeight: '600' },
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
    borderWidth: 1, borderColor: C.gray300,
  },
})
