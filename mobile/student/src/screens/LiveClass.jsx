// Student live class for one class session (Module 5, plan-shino.md S38; FR-503–FR-516).
// Ask (optionally anonymous) and upvote questions, vote in polls, answer quick questions, react and
// press "I don't understand". Kept live by WS /interaction/{id}/ws: each `changed` re-reads its
// topic, and `closed` turns the screen read-only. Opened from Home's Today card.
import { useCallback, useEffect, useRef, useState } from 'react'
import { View, Text, ScrollView, TextInput, StyleSheet, RefreshControl, AppState } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  Card, Muted, Loading, LoadError, Btn, Toggle, Segments, OptionPick, PollResults, ixStyles,
} from '../components/InteractionParts'
import { useStudent } from '../context/StudentContext'
import * as api from '../services/api'
import { BASE, getToken, refreshAccessToken } from '../services/client'
import { hhmm } from '../services/attendance'
import {
  TOPICS, topicsFor, interactionState, validateQuestion, askerLabel, questionBadges, canUpvote,
  toggleChoice, voteAction, pollResultsVisible, sortPolls, validateQuickAnswer, charsLeft,
  REACTIONS, CONFUSION_TOPIC_MAX_CHARS, nextAllowedAt, secondsLeft, cooldownLabel,
  connectInteractionLive, QUESTION_MAX_CHARS,
} from '../services/interaction'
import { C } from '../theme'

// Re-reads one topic at a time; a change that arrives during a read runs it once more after
function useTopicLoader(loaders) {
  const running = useRef({})
  const again = useRef({})
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])
  return useCallback((topic) => {
    if (running.current[topic]) { again.current[topic] = true; return running.current[topic] }
    const run = (async () => {
      try {
        do {
          again.current[topic] = false
          await loaders.current[topic]()
        } while (again.current[topic] && alive.current)
      } finally {
        running.current[topic] = null
      }
    })()
    running.current[topic] = run
    return run
  }, [loaders])
}

// A clock that ticks every second while a cooldown is running
function useNow(active) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!active) return undefined
    setNow(Date.now())
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [active])
  return now
}

// ─── Questions (FR-503–FR-506) ───────────────────────────────────────────────

function AskForm({ sessionId, open, act }) {
  const [text, setText] = useState('')
  const [anonymous, setAnonymous] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const send = async () => {
    const v = validateQuestion(text)
    if (v.error) { setError(v.error); return }
    setBusy(true)
    const ok = await act(() => api.askQuestion(sessionId, v.text, anonymous), 'questions',
      anonymous ? 'Question sent anonymously' : 'Question sent')
    setBusy(false)
    if (ok) { setText(''); setError(null) }
  }

  return (
    <Card testID="live-ask">
      <TextInput
        style={[ixStyles.input, styles.multiline]} value={text} maxLength={QUESTION_MAX_CHARS} multiline
        placeholder="Ask the lecturer a question" placeholderTextColor={C.textHint} editable={open}
        onChangeText={t => { setText(t); setError(null) }} testID="live-ask-input"
      />
      <View style={[ixStyles.row, styles.gapAbove]}>
        <Toggle label="Ask anonymously" value={anonymous} onChange={setAnonymous} disabled={!open} testID="live-ask-anon" />
        <View style={styles.flex1} />
        <Btn kind="primary" icon="send" label="Send" disabled={!open} busy={busy} onPress={send} testID="live-ask-send" />
      </View>
      {anonymous ? <Muted style={styles.small}>Your name isn't shown to the lecturer or the class.</Muted> : null}
      {error ? <Text style={[ixStyles.formError, styles.gapAboveSm]} testID="live-ask-error">{error}</Text> : null}
    </Card>
  )
}

function QuestionsPanel({ sessionId, questions, open, act }) {
  return (
    <>
      <AskForm sessionId={sessionId} open={open} act={act} />
      {!questions.length ? <Card><Muted testID="live-questions-empty">No questions yet. Be the first to ask.</Muted></Card> : null}
      {questions.map(q => (
        <Card key={q.id} testID="live-question" style={q.mine && styles.mine}>
          <Text style={styles.qText}>{q.text}</Text>
          <View style={styles.metaRow}>
            <Text style={ixStyles.meta}>{askerLabel(q)} · {hhmm(q.created_at)}</Text>
            {questionBadges(q).map(b => <Badge key={b.label} variant={b.variant}>{b.label}</Badge>)}
            <View style={styles.flex1} />
            <Btn
              icon={q.upvoted_by_me ? 'arrow-up-circle' : 'arrow-up'} label={String(q.upvotes)}
              kind={q.upvoted_by_me ? 'primary' : 'outline'} disabled={!canUpvote(q, open)}
              accessibilityLabel={`Upvote, ${q.upvotes} so far`} testID="live-q-upvote"
              onPress={() => act(() => api.upvoteQuestion(sessionId, q.id), 'questions')}
            />
          </View>
        </Card>
      ))}
    </>
  )
}

// ─── Polls (FR-507–FR-509) ───────────────────────────────────────────────────

function PollCard({ sessionId, poll, open, act }) {
  const mine = poll.my_option_ids ?? []
  const [selected, setSelected] = useState(mine)
  const [busy, setBusy] = useState(false)
  const mineKey = mine.join(',')
  // A vote saved here or on another device resets the choice to what the server has
  useEffect(() => { setSelected(mineKey ? mineKey.split(',').map(Number) : []) }, [mineKey])

  const action = voteAction(poll, selected, open)
  const pollOpen = open && poll.status === 'open'
  const vote = async () => {
    setBusy(true)
    await act(() => api.votePoll(sessionId, poll.id, selected), 'polls', mine.length ? 'Vote changed' : 'Vote sent')
    setBusy(false)
  }

  return (
    <Card testID="live-poll">
      <View style={ixStyles.row}>
        <Text style={[ixStyles.title, styles.flex1]}>{poll.question}</Text>
        <Badge variant={poll.status === 'open' ? 'green' : 'gray'} dot={poll.status === 'open'}>
          {poll.status === 'open' ? 'Live' : 'Closed'}
        </Badge>
      </View>
      <Text style={[ixStyles.meta, styles.gapAboveSm]}>
        {poll.multiple ? 'Pick one or more' : 'Pick one'}
        {pollOpen && mine.length ? ' · you can change your vote until it closes' : ''}
      </Text>
      {pollOpen ? (
        <>
          {poll.options.map((o, i) => (
            <OptionPick
              key={o.id} text={o.text} multiple={poll.multiple} selected={selected.includes(o.id)}
              onPress={() => setSelected(sel => toggleChoice(sel, o.id, poll.multiple))}
              testID={`live-poll-option-${i}`}
            />
          ))}
          <View style={[ixStyles.row, styles.gapAbove]}>
            <View style={styles.flex1} />
            <Btn kind="primary" icon="checkmark" label={action.label} disabled={!action.enabled} busy={busy}
              onPress={vote} testID="live-poll-vote" />
          </View>
        </>
      ) : null}
      {pollResultsVisible(poll) ? (
        <>
          <Text style={[ixStyles.meta, styles.gapAbove]} testID="live-poll-total">{poll.total_voters} voted</Text>
          <PollResults poll={poll} />
        </>
      ) : !pollOpen ? (
        <Muted testID="live-poll-closed-note">
          {mine.length
            ? `You voted: ${poll.options.filter(o => mine.includes(o.id)).map(o => o.text).join(', ')}`
            : "You didn't vote in this poll."}
        </Muted>
      ) : null}
    </Card>
  )
}

function PollsPanel({ sessionId, polls, open, act }) {
  if (!polls.length) return <Card><Muted testID="live-polls-empty">No polls yet. They appear here when the lecturer starts one.</Muted></Card>
  return sortPolls(polls).map(p => <PollCard key={p.id} sessionId={sessionId} poll={p} open={open} act={act} />)
}

// ─── Quick questions (FR-510, FR-511) ────────────────────────────────────────

function QuickCard({ sessionId, qq, open, act }) {
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const canAnswer = open && qq.status === 'open'
  const mine = qq.my_answer

  const send = async () => {
    const v = validateQuickAnswer(text, qq.max_chars)
    if (v.error) { setError(v.error); return }
    setBusy(true)
    const ok = await act(() => api.answerQuickQuestion(sessionId, qq.id, v.text), 'quick_questions',
      mine ? 'Answer updated' : 'Answer sent')
    setBusy(false)
    if (ok) { setText(''); setError(null) }
  }

  return (
    <Card testID="live-quick">
      <View style={ixStyles.row}>
        <Text style={[ixStyles.title, styles.flex1]}>{qq.prompt}</Text>
        <Badge variant={qq.status === 'open' ? 'green' : 'gray'} dot={qq.status === 'open'}>
          {qq.status === 'open' ? 'Open' : 'Closed'}
        </Badge>
      </View>
      {mine ? (
        <View style={styles.answer}>
          <Text style={ixStyles.label}>Your answer</Text>
          <Text style={styles.answerText} testID="live-quick-mine">{mine}</Text>
        </View>
      ) : !canAnswer ? <Muted>You didn't answer this one.</Muted> : null}
      {canAnswer ? (
        <>
          <TextInput
            style={[ixStyles.input, styles.gapAbove]} value={text} maxLength={qq.max_chars}
            placeholder={mine ? 'Change your answer' : 'Your answer'} placeholderTextColor={C.textHint}
            onChangeText={t => { setText(t); setError(null) }} testID="live-quick-input"
          />
          <View style={[ixStyles.row, styles.gapAboveSm]}>
            <Text style={[ixStyles.meta, styles.flex1]}>
              {charsLeft(text, qq.max_chars)} characters left · only the lecturer sees answers, without names
            </Text>
            <Btn kind="primary" icon="send" label={mine ? 'Update' : 'Answer'} busy={busy} onPress={send} testID="live-quick-send" />
          </View>
        </>
      ) : null}
      {error ? <Text style={[ixStyles.formError, styles.gapAboveSm]} testID="live-quick-error">{error}</Text> : null}
    </Card>
  )
}

function QuickPanel({ sessionId, quick, open, act }) {
  if (!quick.length) return <Card><Muted testID="live-quick-empty">No quick questions yet.</Muted></Card>
  return quick.map(qq => <QuickCard key={qq.id} sessionId={sessionId} qq={qq} open={open} act={act} />)
}

// ─── Reactions and "I don't understand" (FR-512, FR-514) ────────────────────

function SignalsCard({ sessionId, open, showToast }) {
  const [reactUntil, setReactUntil] = useState(null)
  const [confusedUntil, setConfusedUntil] = useState(null)
  const [topicOpen, setTopicOpen] = useState(false)
  const [topic, setTopic] = useState('')
  const [busy, setBusy] = useState(null)
  const ticking = (reactUntil && reactUntil > Date.now()) || (confusedUntil && confusedUntil > Date.now())
  const now = useNow(!!ticking)
  const reactLeft = secondsLeft(reactUntil, now)
  const confusedLeft = secondsLeft(confusedUntil, now)

  const press = async (key, fn, setUntil, done) => {
    setBusy(key)
    try {
      const ack = await fn()
      setUntil(nextAllowedAt({ ack }))
      if (done) showToast(done, 'success')
      return true
    } catch (e) {
      const until = nextAllowedAt({ error: e })
      if (until) setUntil(until)
      showToast(e.message, 'error')
      return false
    } finally { setBusy(null) }
  }

  const react = (kind, label) => press(kind, () => api.sendReaction(sessionId, kind), setReactUntil, `Sent: ${label}`)
  const confused = async () => {
    const t = topic.trim()
    const ok = await press('confused', () => api.pressConfusion(sessionId, t || null), setConfusedUntil,
      'The lecturer can see the class is unsure (your name isn\'t shown)')
    if (ok) { setTopic(''); setTopicOpen(false) }
  }

  return (
    <Card testID="live-signals">
      <View style={ixStyles.row}>
        <Text style={[ixStyles.label, styles.flex1]}>How is it going?</Text>
        {reactLeft ? <Text style={ixStyles.meta} testID="live-react-cooldown">{cooldownLabel(reactLeft)}</Text> : null}
      </View>
      <View style={[ixStyles.wrap, styles.gapAboveSm]}>
        {REACTIONS.map(r => (
          <Btn key={r.kind} icon={r.icon} label={r.label} disabled={!open || reactLeft > 0} busy={busy === r.kind}
            onPress={() => react(r.kind, r.label)} testID={`live-react-${r.kind}`} />
        ))}
      </View>
      <View style={styles.divider} />
      <View style={ixStyles.row}>
        <Ionicons name="help-circle-outline" size={18} color={C.orangeDk} />
        <Text style={[ixStyles.title, styles.flex1]}>Lost? Tell the lecturer, anonymously.</Text>
      </View>
      {topicOpen ? (
        <TextInput
          style={[ixStyles.input, styles.gapAbove]} value={topic} maxLength={CONFUSION_TOPIC_MAX_CHARS}
          placeholder="What about? (optional, e.g. recursion)" placeholderTextColor={C.textHint}
          onChangeText={setTopic} testID="live-confused-topic"
        />
      ) : null}
      <View style={[ixStyles.wrap, styles.gapAbove, styles.alignCenter]}>
        <Btn kind="primary" icon="alert-circle-outline" label="I don't understand"
          disabled={!open || confusedLeft > 0} busy={busy === 'confused'} onPress={confused} testID="live-confused" />
        {!topicOpen ? (
          <Btn kind="subtle" icon="pricetag-outline" label="Add a topic" disabled={!open || confusedLeft > 0}
            onPress={() => setTopicOpen(true)} testID="live-confused-add-topic" />
        ) : null}
        {confusedLeft ? <Text style={ixStyles.meta} testID="live-confused-cooldown">{cooldownLabel(confusedLeft)}</Text> : null}
      </View>
    </Card>
  )
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function LiveClass({ route, navigation }) {
  const sessionId = route.params?.sessionId
  const { showToast } = useStudent()
  const [tab, setTab] = useState('questions')
  const [session, setSession] = useState(null)
  const [data, setData] = useState({ questions: [], polls: [], quick_questions: [] })
  const [loadError, setLoadError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const put = (key) => (value) => setData(d => ({ ...d, [key]: value }))
  const loaders = useRef(null)
  loaders.current = {
    session: async () => setSession(await api.getInteraction(sessionId)),
    questions: async () => put('questions')((await api.getInteractionQuestions(sessionId)).questions),
    polls: async () => put('polls')((await api.getInteractionPolls(sessionId)).polls),
    quick_questions: async () => put('quick_questions')((await api.getQuickQuestions(sessionId)).quick_questions),
  }
  const reload = useTopicLoader(loaders)

  const loadAll = useCallback(async () => {
    try {
      await Promise.all(['session', ...TOPICS].map(reload))
      setLoadError(null)
      return true
    } catch (e) {
      setLoadError(e.message)
      return false
    }
  }, [reload])

  useEffect(() => { loadAll() }, [loadAll])

  const st = interactionState(session)
  const endedRef = useRef(false)
  endedRef.current = st.ended
  // Only a class seen running here gets the "has ended" toast (not one opened after it ended)
  const sawRunning = useRef(false)
  if (session?.class_status === 'open') sawRunning.current = true

  // Live updates: each message says which topic to re-read. Phones drop sockets in the background,
  // so a return to the app reconnects (and `connected` re-reads everything) while the class runs.
  useEffect(() => {
    if (!sessionId) return undefined
    let active = true
    const onMessage = (m) => {
      if (!active) return
      for (const t of topicsFor(m)) reload(t).catch(() => {})
      if (m.type === 'closed' && m.reason === 'class_ended') {
        if (sawRunning.current) showToast('The class has ended', 'info')
      } else if (m.type === 'closed') showToast('The lecturer paused interaction', 'info')
      else if (m.type === 'opened') showToast('Interaction is open again', 'info')
    }
    const connect = () => connectInteractionLive({
      baseUrl: BASE, sessionId, getToken, refreshToken: refreshAccessToken, onMessage,
    })
    let live = connect()
    const sub = AppState.addEventListener('change', (next) => {
      if (next !== 'active' || endedRef.current) return
      live.close()
      live = connect()
    })
    return () => { active = false; sub?.remove?.(); live.close() }
  }, [sessionId, reload, showToast])

  // One student action, then re-read its topic (the websocket echo is coalesced with it). A 409
  // means the interaction closed meanwhile: the session re-read shows why.
  const act = useCallback(async (fn, topic, done) => {
    try {
      await fn()
      if (done) showToast(done, 'success')
      await reload(topic).catch(() => {})
      return true
    } catch (e) {
      showToast(e.message, 'error')
      reload('session').catch(() => {})
      reload(topic).catch(() => {})
      return false
    }
  }, [reload, showToast])

  const onRefresh = async () => { setRefreshing(true); await loadAll(); setRefreshing(false) }
  const openMyQuestions = () => navigation.navigate('MyQuestions')

  const header = (
    <Topbar
      title="Live class"
      sub={session ? `${session.course_code} · ${session.course_name}` : ''}
      onBack={() => navigation.goBack()}
      right={<View testID="live-state"><Badge variant={st.variant} dot={st.open}>{st.label}</Badge></View>}
    />
  )

  if (!session) {
    return (
      <View style={styles.screen}>
        {header}
        <View style={styles.content}>
          {loadError ? <LoadError message={loadError} onRetry={loadAll} /> : <Loading text="Joining the class…" />}
        </View>
      </View>
    )
  }

  const counts = {
    polls: data.polls.filter(p => p.status === 'open' && !(p.my_option_ids ?? []).length).length,
    quick: data.quick_questions.filter(q => q.status === 'open' && !q.my_answer).length,
  }
  const tabs = [
    { key: 'questions', label: 'Questions' },
    { key: 'polls', label: 'Polls', count: counts.polls },
    { key: 'quick', label: 'Quick', count: counts.quick },
  ]
  const panel = {
    questions: <QuestionsPanel sessionId={sessionId} questions={data.questions} open={st.open} act={act} />,
    polls: <PollsPanel sessionId={sessionId} polls={data.polls} open={st.open} act={act} />,
    quick: <QuickPanel sessionId={sessionId} quick={data.quick_questions} open={st.open} act={act} />,
  }[tab]

  return (
    <View style={styles.screen}>
      {header}
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {loadError ? <LoadError message={loadError} onRetry={loadAll} /> : null}

        {st.ended ? (
          <Card style={styles.banner} testID="live-ended">
            <Text style={ixStyles.title}>The class has ended</Text>
            <Muted>Interaction is closed. You can still read everything below.</Muted>
            <View style={[ixStyles.wrap, styles.gapAboveSm]}>
              <Btn kind="primary" icon="chatbubbles-outline" label="My questions" onPress={openMyQuestions} testID="live-ended-my-questions" />
            </View>
          </Card>
        ) : (
          <>
            <View style={[ixStyles.row, styles.toolbar]}>
              <Text style={[ixStyles.meta, styles.flex1]} testID="live-state-text">{st.text}</Text>
              <Btn kind="subtle" icon="chatbubbles-outline" label="My questions" onPress={openMyQuestions} testID="live-my-questions" />
            </View>
            <SignalsCard sessionId={sessionId} open={st.open} showToast={showToast} />
          </>
        )}

        <Segments items={tabs} value={tab} onChange={setTab} />
        {panel}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  toolbar: { marginBottom: 8 },
  banner: { backgroundColor: C.blueLt, borderColor: C.blueLt },
  mine: { borderColor: '#BFDBFE' },
  multiline: { minHeight: 64, textAlignVertical: 'top' },
  qText: { fontSize: 14, color: C.text, lineHeight: 20 },
  metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  gapAbove: { marginTop: 10 },
  gapAboveSm: { marginTop: 6 },
  small: { fontSize: 12 },
  alignCenter: { alignItems: 'center' },
  divider: { height: 1, backgroundColor: C.border, marginVertical: 12 },
  answer: { borderTopWidth: 1, borderTopColor: C.border, paddingTop: 8, marginTop: 8, gap: 2 },
  answerText: { fontSize: 14, color: C.text },
})
