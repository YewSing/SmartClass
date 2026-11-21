import { useCallback, useRef, useState } from 'react'
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import Topbar from '../components/Topbar'
import { Sheet, ModalTitle } from '../components/Modals'
import { C } from '../theme'
import { interactionRequest, interactionSocket } from '../services/interaction'

const reactionLabels = {
  thumbs_up: ['Thumbs up', '👍'],
  clear: ['Clear', '💡'],
  too_fast: ['Too fast', '⚡'],
  too_slow: ['Too slow', '🐢'],
}

// Small section header: icon + medium-weight title + optional trailing action
function Section({ icon, title, action, children, tint = 'blue' }) {
  const accent = tint === 'purple' ? '#7C3AED' : tint === 'green' ? C.greenDk : tint === 'orange' ? C.orangeDk : C.blueDk
  const iconBackground = tint === 'purple' ? '#F3E8FF' : tint === 'green' ? C.greenLt : tint === 'orange' ? C.orangeLt : C.blueLt
  return (
    <View style={[styles.section, styles[`section_${tint}`]]}>
      <View style={styles.sectionHead}>
        <View style={[styles.sectionIcon, { backgroundColor: iconBackground }]}>
          <Ionicons name={icon} size={16} color={accent} />
        </View>
        <Text style={styles.sectionTitle}>{title}</Text>
        {action}
      </View>
      {children}
    </View>
  )
}

function Chip({ tone, children }) {
  return <Text style={[styles.chip, tone === 'green' && styles.chipGreen, tone === 'amber' && styles.chipAmber]}>{children}</Text>
}

function Empty({ children }) {
  return <Text style={styles.empty}>{children}</Text>
}

function QuestionCard({ item, blocked, onModerate }) {
  return (
    <View style={styles.item}>
      <Text style={styles.body}>{item.text}</Text>
      <View style={styles.row}>
        <Text style={styles.meta} numberOfLines={1}>
          {item.anonymous ? 'Anonymous' : item.author_name} · {item.created_at?.slice(11, 16)}
        </Text>
        <Ionicons name="arrow-up" size={13} color={C.textSub} />
        <Text style={styles.meta}>{item.votes}</Text>
        {item.pinned ? <Chip tone="amber">Pinned</Chip> : null}
        {item.answered ? <Chip tone="green">Answered</Chip> : null}
        {item.hidden ? <Chip>Hidden</Chip> : null}
        <View style={styles.grow} />
        <Pressable accessibilityRole="button" disabled={blocked} onPress={() => onModerate('pinned', !item.pinned)}>
          <Ionicons name="bookmark-outline" size={17} color={item.pinned ? C.blueDk : C.textSub} />
        </Pressable>
        <Pressable accessibilityRole="button" disabled={blocked} onPress={() => onModerate('answered', !item.answered)}>
          <Ionicons name="checkmark-circle-outline" size={17} color={item.answered ? C.greenDk : C.textSub} />
        </Pressable>
        <Pressable accessibilityRole="button" disabled={blocked} onPress={() => onModerate('hidden', !item.hidden)}>
          <Ionicons name="eye-off-outline" size={17} color={item.hidden ? C.redDk : C.textSub} />
        </Pressable>
      </View>
    </View>
  )
}

function PollResults({ poll }) {
  const results = poll.results
  if (!results) return null
  return (
    <View style={styles.stack}>
      <Text style={styles.meta}>{results.respondent_count} responses</Text>
      {poll.options.map((option, index) => {
        const votes = results.option_counts[index] ?? 0
        const share = results.respondent_count ? Math.min(100, votes / results.respondent_count * 100) : 0
        return (
          <View key={index} style={styles.stack}>
            <Text style={styles.body}>{option} · {votes}</Text>
            <View style={styles.track}><View style={[styles.bar, { width: `${share}%` }]} /></View>
          </View>
        )
      })}
    </View>
  )
}

function PollCard({ poll, blocked, act, live }) {
  return (
    <View style={styles.item}>
      <View style={styles.row}>
        <Text style={[styles.body, styles.grow]}>{poll.prompt}</Text>
        <Chip tone={poll.status === 'open' ? 'green' : undefined}>
          {poll.status === 'open' ? 'Active' : poll.status === 'draft' ? 'Draft' : 'Closed'}
        </Chip>
      </View>
      <PollResults poll={poll} />
      {live ? (
        <View style={styles.row}>
          {poll.status === 'draft' ? (
            <Pressable accessibilityRole="button" disabled={blocked} style={[styles.primaryBtn, styles.compact, blocked && styles.disabled]}
              onPress={() => act('POST', `/polls/${poll.id}/start`)}>
              <Text style={styles.primaryText}>Start poll</Text>
            </Pressable>
          ) : null}
          {poll.status === 'open' ? (
            <Pressable accessibilityRole="button" disabled={blocked} style={[styles.outlineBtn, styles.compact, blocked && styles.disabled]}
              onPress={() => act('POST', `/polls/${poll.id}/close`)}>
              <Text style={styles.outlineText}>Close poll</Text>
            </Pressable>
          ) : null}
          {poll.status !== 'draft' ? (
            <Pressable accessibilityRole="button" disabled={blocked} style={[styles.outlineBtn, styles.compact, blocked && styles.disabled]}
              onPress={() => act('PATCH', `/polls/${poll.id}`, { show_results: !poll.show_results })}>
              <Text style={styles.outlineText}>{poll.show_results ? 'Hide results from students' : 'Share results with students'}</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
    </View>
  )
}

function Interaction({ sessionId, className, navigation }) {
  const [snapshot, setSnapshot] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const [showAllQuestions, setShowAllQuestions] = useState(false)
  const [showPollHistory, setShowPollHistory] = useState(false)
  const [showResponses, setShowResponses] = useState(false)
  const [showCreatePoll, setShowCreatePoll] = useState(false)
  const [pollPrompt, setPollPrompt] = useState('')
  const [options, setOptions] = useState(['', ''])
  const [multiple, setMultiple] = useState(false)
  const [quickPrompt, setQuickPrompt] = useState('')
  const requestSequence = useRef(0)
  const mutation = useRef(false)
  const refresh = useRef(null)
  const focused = useRef(false)
  const selectedPrompt = useRef(null)
  const request = useCallback((method, path, body) => interactionRequest(sessionId, method, path, body), [sessionId])

  const load = useCallback(async () => {
    const sequence = ++requestSequence.current
    try {
      const state = await request('GET')
      const activePrompt = selectedPrompt.current
      const [signals, summary, answers] = await Promise.all([
        state.can_participate ? request('GET', '/signals') : null,
        state.status === 'closed' ? request('GET', '/summary') : null,
        state.can_participate && activePrompt ? request('GET', `/quick-prompts/${activePrompt}/answers`) : null,
      ])
      if (focused.current && sequence === requestSequence.current) {
        setSnapshot({ state, signals, summary, answers, activePrompt })
        setLoadError('')
      }
      return true
    } catch (error) {
      if (focused.current && sequence === requestSequence.current) {
        if ([401, 403, 404].includes(error.status)) setSnapshot(null)
        setLoadError('Classroom activity could not be refreshed.')
      }
      return false
    }
  }, [request])

  useFocusEffect(useCallback(() => {
    let active = true
    let socket
    let connected = false
    let lastSync = 0
    let pending = false
    let timer
    focused.current = true

    let invalidation = 0
    async function sync() {
      if (pending) return
      pending = true
      do {
        const revision = invalidation
        const ok = await load()
        if (!active || !ok || revision === invalidation) break
      } while (active)
      pending = false
    }
    function invalidate() {
      invalidation += 1
      if (!timer) timer = setTimeout(() => { timer = null; void sync() }, 80)
    }
    function connect() {
      try {
        socket = interactionSocket(sessionId)
        if (!socket) return
        socket.onopen = () => { connected = true; invalidate() }
        socket.onmessage = ({ data }) => {
          try {
            const message = JSON.parse(data)
            if (message.attendance_session_id !== sessionId || !message.event?.startsWith('interaction.')) return
            const hasSessionStatus = message.event === 'interaction.session_status' || message.event === 'interaction.state'
            if (hasSessionStatus && message.status !== 'open') {
              requestSequence.current += 1
              setSnapshot(current => current && {
                ...current,
                state: { ...current.state, status: message.status, can_participate: false },
              })
            }
            invalidate()
          } catch { /* Ignore invalid messages. */ }
        }
        socket.onclose = () => { socket = null; connected = false }
      } catch { socket = null; connected = false }
    }
    refresh.current = invalidate
    void sync()
    connect()
    const interval = setInterval(() => {
      if (!connected || Date.now() - lastSync >= 30000) {
        lastSync = Date.now()
        invalidate()
      }
      if (!socket) connect()
    }, 5000)
    return () => {
      active = false
      focused.current = false
      requestSequence.current += 1
      refresh.current = null
      clearTimeout(timer)
      clearInterval(interval)
      if (socket) {
        socket.onopen = socket.onmessage = socket.onclose = null
        socket.close()
      }
    }
  }, [sessionId, load]))

  async function act(method, path, body, done) {
    if (mutation.current || !snapshot?.state.can_participate || loadError) return
    mutation.current = true
    setBusy(true)
    setActionError('')
    try {
      await request(method, path, body)
      done?.()
    } catch (error) {
      const message = error.message && !error.message.includes('[object Object]') ? error.message : ''
      setActionError(message || 'Could not save this change. Please try again.')
    } finally {
      refresh.current?.()
      mutation.current = false
      setBusy(false)
    }
  }

  const state = snapshot?.state
  const live = Boolean(state?.can_participate)
  const blocked = busy || Boolean(loadError)
  const summary = snapshot?.summary
  const signals = summary ?? snapshot?.signals
  const activePoll = state?.polls.find(poll => poll.status === 'open') ?? null
  const otherPolls = state ? state.polls.filter(poll => poll.id !== activePoll?.id && poll.status !== 'draft') : []
  const draftPolls = state?.polls.filter(poll => poll.status === 'draft') ?? []
  const activePrompt = state?.quick_prompts.find(prompt => prompt.status === 'open') ?? null
  const closedPrompts = state?.quick_prompts.filter(prompt => prompt.id !== activePrompt?.id) ?? []
  const visibleQuestions = state?.questions.filter(question => !question.hidden) ?? []

  const savePoll = () => act('POST', '/polls', { prompt: pollPrompt.trim(), options: options.map(value => value.trim()), multiple }, () => {
    setPollPrompt('')
    setOptions(['', ''])
    setMultiple(false)
    setShowCreatePoll(false)
  })

  function viewResponses(id) {
    selectedPrompt.current = showResponses && selectedPrompt.current === id ? null : id
    setShowResponses(selectedPrompt.current !== null)
    refresh.current?.()
  }

  return (
    <View style={styles.page}>
      <Topbar title="Classroom interaction" sub={className} onBack={() => navigation.goBack()} />
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={false} onRefresh={() => refresh.current?.()} />}>
        {loadError ? (
          <View style={styles.notice} accessibilityLiveRegion="polite">
            <Text style={styles.warning}>{loadError}</Text>
            <Pressable accessibilityRole="button" onPress={() => refresh.current?.()}><Text style={styles.link}>Retry</Text></Pressable>
          </View>
        ) : null}
        {!state && !loadError ? <ActivityIndicator color={C.primary} /> : null}
        {state ? (
          live || summary ? null : (
            <Empty>{state.status === 'scheduled' ? 'Activity opens with the shared class session.' : 'This session is unavailable.'}</Empty>
          )
        ) : null}
        {actionError && live ? <Text accessibilityLiveRegion="polite" style={styles.warning}>{actionError}</Text> : null}
        {state ? (
          <View style={styles.liveOverview} testID="interaction-overview">
            <View style={styles.overviewTop}>
              <View style={styles.overviewIcon}><Ionicons name="school-outline" size={20} color="#fff" /></View>
              <View style={styles.grow}>
                <Text style={styles.overviewEyebrow}>{live ? 'CLASSROOM CONTROL' : 'SESSION RECAP'}</Text>
                <Text style={styles.overviewTitle} numberOfLines={1}>{className || 'Live class'}</Text>
              </View>
              <Chip tone={live ? 'green' : undefined}>{live ? 'Live' : state.status === 'scheduled' ? 'Upcoming' : 'Ended'}</Chip>
            </View>
            <Text style={styles.overviewCopy}>{live
              ? 'Your class activity, questions and feedback — together in one live view.'
              : 'A quick overview of the interaction from this class session.'}</Text>
            <View style={styles.overviewStats}>
              <View style={styles.overviewStat}><Text style={styles.overviewNumber}>{state.questions.length}</Text><Text style={styles.overviewLabel}>Questions</Text></View>
              <View style={styles.overviewDivider} />
              <View style={styles.overviewStat}><Text style={styles.overviewNumber}>{state.polls.filter(poll => poll.status === 'open').length}</Text><Text style={styles.overviewLabel}>Active polls</Text></View>
              <View style={styles.overviewDivider} />
              <View style={styles.overviewStat}><Text style={styles.overviewNumber}>{state.quick_prompts.filter(prompt => prompt.status === 'open').length}</Text><Text style={styles.overviewLabel}>Quick prompts</Text></View>
            </View>
          </View>
        ) : null}

        {/* Post-class summary (read-only) */}
        {summary ? (
          <>
            <Section icon="document-text-outline" title="Session summary" tint="purple">
              <Text style={styles.meta}>{summary.questions_asked} questions · {summary.questions_answered} answered</Text>
              {summary.polls.filter(poll => poll.started_at).map(poll => <PollCard key={poll.id} poll={poll} blocked act={act} live={false} />)}
            </Section>
            {signals ? <SignalSection data={signals} /> : null}
          </>
        ) : null}

        {live && state ? <>
          {/* ── Live Questions ── */}
          <Section icon="chatbubbles-outline" title="Live Questions" tint="blue"
            action={visibleQuestions.length
              ? <Pressable accessibilityRole="button" onPress={() => setShowAllQuestions(true)} testID="view-all-questions">
                  <Text style={styles.link}>View all ({state.questions.length})</Text>
                </Pressable>
              : null}>
            {visibleQuestions.length ? visibleQuestions.slice(0, 3).map(question => (
              <QuestionCard key={question.id} item={question} blocked={blocked}
                onModerate={(field, value) => act('PATCH', `/questions/${question.id}`, { [field]: value })} />
            )) : <Empty>Student questions will appear here.</Empty>}
          </Section>

          {/* ── Live Poll ── */}
          <Section icon="stats-chart-outline" title="Live Poll" tint="purple"
            action={<>
              {otherPolls.length
                ? <Pressable accessibilityRole="button" onPress={() => setShowPollHistory(true)} testID="view-poll-history">
                    <Text style={styles.link}>View history</Text>
                  </Pressable>
                : null}
              <Pressable accessibilityRole="button" onPress={() => setShowCreatePoll(true)} testID="create-poll">
                <Text style={styles.link}>Create poll</Text>
              </Pressable>
            </>}>
            {activePoll
              ? <PollCard poll={activePoll} blocked={blocked} act={act} live />
              : <Empty>No active poll.</Empty>}
            {draftPolls.length ? <Text style={styles.meta}>{draftPolls.length} draft poll{draftPolls.length > 1 ? 's' : ''} ready to start — open “View history”.</Text> : null}
          </Section>

          {/* ── Quick Answers ── */}
          <Section icon="create-outline" title="Quick Answers" tint="green">
            <View style={styles.item}>
              <TextInput accessibilityLabel="Quick question" placeholder="Ask a quick question…" style={styles.input}
                value={quickPrompt} onChangeText={setQuickPrompt} maxLength={500} />
              <Pressable accessibilityRole="button" disabled={blocked || !quickPrompt.trim()}
                style={[styles.primaryBtn, styles.compact, (blocked || !quickPrompt.trim()) && styles.disabled]}
                onPress={() => act('POST', '/quick-prompts', { prompt: quickPrompt.trim() }, () => setQuickPrompt(''))}>
                <Text style={styles.primaryText}>Send question</Text>
              </Pressable>
            </View>
            {state.quick_prompts.length ? state.quick_prompts.slice(0, 1).map(prompt => (
              <View key={prompt.id} style={styles.item}>
                <View style={styles.row}>
                  <Text style={[styles.body, styles.grow]}>{prompt.prompt}</Text>
                  <Chip tone={prompt.status === 'open' ? 'green' : undefined}>{prompt.status === 'open' ? 'Active' : 'Closed'}</Chip>
                </View>
                <Text style={styles.meta}>{prompt.answer_count ?? 0} responses received</Text>
                <View style={styles.row}>
                  <Pressable accessibilityRole="button" style={[styles.outlineBtn, styles.compact]}
                    onPress={() => viewResponses(prompt.id)} testID="view-answers">
                    <Text style={styles.outlineText}>{showResponses && selectedPrompt.current === prompt.id ? 'Hide responses' : 'View all responses'}</Text>
                  </Pressable>
                  {prompt.status === 'open' ? (
                    <Pressable accessibilityRole="button" disabled={blocked} style={[styles.outlineBtn, styles.compact, blocked && styles.disabled]}
                      onPress={() => act('POST', `/quick-prompts/${prompt.id}/close`)}>
                      <Text style={styles.outlineText}>Close question</Text>
                    </Pressable>
                  ) : null}
                </View>
                {selectedPrompt.current === prompt.id ? (
                  snapshot.activePrompt !== prompt.id ? <ActivityIndicator color={C.primary} />
                    : snapshot.answers?.length ? snapshot.answers.map(answer => (
                      <View key={answer.id} style={styles.answer}>
                        <Text style={styles.meta}>{answer.student_name}</Text>
                        <Text style={styles.body}>{answer.text}</Text>
                      </View>
                    )) : <Text style={styles.meta}>No answers yet.</Text>
                ) : null}
              </View>
            )) : <Empty>Ask the class a short question above.</Empty>}
            {closedPrompts.length ? <Text style={styles.meta}>{closedPrompts.length} earlier prompt{closedPrompts.length > 1 ? 's' : ''} below the fold.</Text> : null}
          </Section>

          {/* ── Reactions & confusion aggregates (lecturer) ── */}
          {signals ? <SignalSection data={signals} /> : null}
        </> : null}
      </ScrollView>

      {/* All questions modal */}
      <Sheet visible={showAllQuestions} onClose={() => setShowAllQuestions(false)}>
        <ModalTitle>All questions</ModalTitle>
        {state?.questions.length ? state.questions.map(question => (
          <QuestionCard key={question.id} item={question} blocked={blocked}
            onModerate={(field, value) => act('PATCH', `/questions/${question.id}`, { [field]: value })} />
        )) : <Empty>No questions yet.</Empty>}
      </Sheet>

      {/* Poll history modal */}
      <Sheet visible={showPollHistory} onClose={() => setShowPollHistory(false)}>
        <ModalTitle>Poll history</ModalTitle>
        {[...state?.polls ?? []].reverse().map(poll => <PollCard key={poll.id} poll={poll} blocked={blocked} act={act} live />)}
      </Sheet>

      {/* Create poll modal */}
      <Sheet visible={showCreatePoll} onClose={() => setShowCreatePoll(false)}>
        <ModalTitle>Create a poll</ModalTitle>
        <TextInput accessibilityLabel="Poll question" placeholder="Poll question" style={styles.input}
          value={pollPrompt} onChangeText={setPollPrompt} maxLength={500} />
        {options.map((option, index) => (
          <TextInput key={index} accessibilityLabel={`Option ${index + 1}`} placeholder={`Option ${index + 1}`}
            value={option} onChangeText={value => setOptions(current => current.map((item, i) => i === index ? value : item))}
            maxLength={255} style={styles.input} />
        ))}
        <View style={styles.row}>
          {options.length < 6 ? (
            <Pressable accessibilityRole="button" onPress={() => setOptions(current => [...current, ''])}>
              <Text style={styles.link}>+ Add option</Text>
            </Pressable>
          ) : null}
          {options.length > 2 ? (
            <Pressable accessibilityRole="button" onPress={() => setOptions(current => current.slice(0, -1))}>
              <Text style={styles.link}>− Remove last</Text>
            </Pressable>
          ) : null}
        </View>
        <View style={styles.row}>
          <Text style={styles.body}>Allow multiple choices</Text>
          <Switch accessibilityLabel="Allow multiple choices" value={multiple} onValueChange={setMultiple} />
        </View>
        <Pressable accessibilityRole="button" disabled={blocked || !pollPrompt.trim() || options.some(value => !value.trim())}
          style={[styles.primaryBtn, (blocked || !pollPrompt.trim() || options.some(value => !value.trim())) && styles.disabled]}
          onPress={savePoll} testID="save-poll">
          <Text style={styles.primaryText}>Save draft</Text>
        </Pressable>
      </Sheet>
    </View>
  )
}

export default function ClassInteraction({ route, navigation }) {
  const sessionId = route.params?.sessionId
  return <Interaction key={sessionId} sessionId={sessionId} className={route.params?.className} navigation={navigation} />
}

// Aggregate-only signals: reaction counts and the confusion timeline (FR-511/512/515)
function SignalSection({ data }) {
  return (
    <Section icon="pulse-outline" title="Signals & feedback" tint="orange">
      <View style={styles.item}>
        <View style={styles.reactionRow}>
          {Object.entries(reactionLabels).map(([key, [label, emoji]]) => (
            <View key={key} style={styles.reactionCount}>
              <Text style={styles.reactionEmoji}>{emoji}</Text>
              <View>
                <Text style={styles.reactionValue}>{data.reactions[key] ?? 0}</Text>
                <Text style={styles.meta}>{label}</Text>
              </View>
            </View>
          ))}
        </View>
      </View>
      <View style={styles.item}>
        <Text style={styles.body}>Confusion timeline</Text>
        <Text style={styles.meta}>{data.confusion_total} reports · aggregate only, never per student</Text>
        {data.confusion_timeline.length === 0
          ? <Text style={styles.meta}>No confusion reports for this session.</Text>
          : data.confusion_timeline.map(({ minute, count }) => (
            <View key={minute} style={styles.row}>
              <Text style={styles.meta}>{minute.replace('T', ' ').slice(0, 16)}</Text>
              <View style={styles.track}><View style={[styles.bar, { width: `${Math.min(100, count * 20)}%` }]} /></View>
              <Text style={styles.meta}>{count}</Text>
            </View>
          ))}
      </View>
    </Section>
  )
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 36, gap: 16, width: '100%', maxWidth: 900, alignSelf: 'center' },
  liveOverview: { backgroundColor: '#173B68', borderRadius: 18, padding: 18, gap: 12, overflow: 'hidden' },
  overviewTop: { flexDirection: 'row', alignItems: 'center', gap: 11 },
  overviewIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.16)', justifyContent: 'center', alignItems: 'center' },
  overviewEyebrow: { color: '#B9D9FF', fontSize: 10, fontWeight: '800', letterSpacing: 1.1 },
  overviewTitle: { color: '#fff', fontSize: 19, fontWeight: '800', marginTop: 2 },
  overviewCopy: { color: '#D9E8F8', fontSize: 13, lineHeight: 19 },
  overviewStats: { flexDirection: 'row', alignItems: 'center', paddingTop: 10, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.18)' },
  overviewStat: { flex: 1, alignItems: 'center', gap: 2 },
  overviewNumber: { color: '#fff', fontSize: 20, fontWeight: '800' },
  overviewLabel: { color: '#C6D8EB', fontSize: 11, fontWeight: '600' },
  overviewDivider: { width: 1, height: 30, backgroundColor: 'rgba(255,255,255,0.2)' },
  section: { gap: 12, padding: 14, borderRadius: 16, borderWidth: 1, borderColor: C.border, backgroundColor: C.card },
  section_blue: { borderTopWidth: 3, borderTopColor: C.primary },
  section_purple: { borderTopWidth: 3, borderTopColor: '#7C3AED' },
  section_green: { borderTopWidth: 3, borderTopColor: C.green },
  section_orange: { borderTopWidth: 3, borderTopColor: C.orange },
  sectionIcon: { width: 30, height: 30, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sectionTitle: { fontSize: 15, fontWeight: '600', color: C.text, flex: 1 },
  link: { color: C.blueDk, fontSize: 13, fontWeight: '500' },
  item: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: 12, gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  grow: { flex: 1 },
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  meta: { color: C.gray600, fontSize: 12, lineHeight: 17 },
  empty: { color: C.gray600, fontSize: 13, paddingVertical: 2 },
  chip: { color: C.textSub, fontSize: 11, backgroundColor: C.gray100, borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, overflow: 'hidden', alignSelf: 'flex-start' },
  chipGreen: { color: C.greenDk, backgroundColor: C.greenLt },
  chipAmber: { color: C.yellowDk, backgroundColor: C.yellowLt },
  primaryBtn: { minHeight: 40, paddingHorizontal: 14, borderRadius: 8, justifyContent: 'center', alignItems: 'center', backgroundColor: C.blueDk, alignSelf: 'flex-start' },
  compact: { minHeight: 36, paddingHorizontal: 12 },
  primaryText: { color: '#fff', fontSize: 13, fontWeight: '500' },
  outlineBtn: { minHeight: 36, paddingHorizontal: 12, borderRadius: 8, justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: C.border, backgroundColor: C.card, alignSelf: 'flex-start' },
  outlineText: { color: C.blueDk, fontSize: 13, fontWeight: '500' },
  disabled: { opacity: 0.5 },
  input: { minHeight: 44, borderWidth: 1, borderColor: C.gray300, borderRadius: 8, paddingHorizontal: 12, color: C.text, fontSize: 14, backgroundColor: C.card },
  answer: { paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border, gap: 4 },
  notice: { padding: 12, borderRadius: 8, backgroundColor: C.redLt, alignItems: 'flex-start', gap: 8 },
  warning: { color: C.redDk, fontSize: 13 },
  reactionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  reactionCount: { flexDirection: 'row', alignItems: 'center', gap: 8, minWidth: 100 },
  reactionEmoji: { fontSize: 20 },
  reactionValue: { color: C.blueDk, fontSize: 16, fontWeight: '600' },
  track: { backgroundColor: C.gray100, borderRadius: 3, height: 5, overflow: 'hidden', flex: 1, marginHorizontal: 8 },
  bar: { height: '100%', backgroundColor: C.primary },
})
