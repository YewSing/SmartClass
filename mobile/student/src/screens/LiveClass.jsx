// Student live class for one class session (Module 5, plan-shino.md S38, S38c; FR-503–FR-516).
// One scrolling page of section cards, latest only (Shino's layout 2026-11-23): status banner, the
// lecturer's latest quick question, the latest poll, React (reactions + "I don't understand"), Ask
// a question, and the newest questions (the rest in a "See all" sheet). Earlier polls and quick
// questions aren't listed. Kept live by WS /interaction/{id}/ws: each `changed` re-reads its topic,
// and `closed` turns the screen read-only. Opened from Home's Today card.
import { useCallback, useEffect, useRef, useState } from 'react'
import { View, Text, ScrollView, TextInput, StyleSheet, RefreshControl, AppState } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  Card, Muted, Loading, LoadError, Btn, Toggle, OptionPick, PollResults, IxSheet, SectionHead, ixStyles,
} from '../components/InteractionParts'
import { useStudent } from '../context/StudentContext'
import * as api from '../services/api'
import { BASE, getToken, refreshAccessToken } from '../services/client'
import { hhmm } from '../services/attendance'
import {
  TOPICS, topicsFor, interactionState, validateQuestion, askerLabel, questionTags, canUpvote,
  toggleChoice, voteAction, pollResultsVisible, validateQuickAnswer, charsLeft,
  REACTIONS, CONFUSION_TOPIC_MAX_CHARS, nextAllowedAt, secondsLeft, cooldownLabel,
  connectInteractionLive, QUESTION_MAX_CHARS, latestPoll, latestQuick, newestQuestions, QUESTIONS_ON_PAGE,
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

// ─── Status banner ───────────────────────────────────────────────────────────

function StatusBanner({ st, onMyQuestions }) {
  if (st.ended) {
    return (
      <Card style={styles.banner} testID="live-ended">
        <View style={ixStyles.row}>
          <Badge variant={st.variant}>{st.label}</Badge>
          <Text style={[ixStyles.title, styles.flex1]}>The class has ended</Text>
        </View>
        <Muted>Interaction is closed. You can still read everything below.</Muted>
        <View style={[ixStyles.wrap, styles.gapAboveSm]}>
          <Btn kind="primary" icon="chatbubbles-outline" label="My questions" onPress={onMyQuestions} testID="live-ended-my-questions" />
        </View>
      </Card>
    )
  }
  return (
    <Card style={[styles.banner, !st.open && styles.bannerPaused]} testID="live-status">
      <View style={ixStyles.row}>
        <Badge variant={st.variant} dot={st.open}>{st.label}</Badge>
        <Text style={[ixStyles.meta, styles.flex1]} testID="live-state-text">{st.text}</Text>
      </View>
      <View style={[ixStyles.wrap, styles.gapAboveSm]}>
        <Btn kind="subtle" icon="chatbubbles-outline" label="My questions" onPress={onMyQuestions} testID="live-my-questions" />
      </View>
    </Card>
  )
}

// ─── Quick question (FR-510, FR-511): the latest one only ───────────────────

function QuickSection({ sessionId, qq, open, act }) {
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)

  if (!qq) {
    return (
      <Card testID="live-quick-section">
        <SectionHead icon="flash-outline" title="Quick question" />
        <Muted testID="live-quick-empty">No quick question right now. It appears here when the lecturer asks one.</Muted>
      </Card>
    )
  }

  const canAnswer = open && qq.status === 'open'
  const mine = qq.my_answer
  const showBox = canAnswer && (!mine || editing)

  const send = async () => {
    const v = validateQuickAnswer(text, qq.max_chars)
    if (v.error) { setError(v.error); return }
    setBusy(true)
    const ok = await act(() => api.answerQuickQuestion(sessionId, qq.id, v.text), 'quick_questions',
      mine ? 'Answer updated' : 'Answer sent')
    setBusy(false)
    if (ok) { setText(''); setError(null); setEditing(false) }
  }

  return (
    <Card testID="live-quick">
      <SectionHead
        icon="flash-outline" title="Quick question"
        right={(
          <Badge variant={qq.status === 'open' ? 'green' : 'gray'} dot={qq.status === 'open'}>
            {qq.status === 'open' ? 'Open' : 'Closed'}
          </Badge>
        )}
      />
      <Text style={styles.prompt}>{qq.prompt}</Text>
      {mine && !showBox ? (
        <View style={styles.answer}>
          <View style={ixStyles.row}>
            <Text style={[ixStyles.label, styles.flex1]}>Your answer</Text>
            {canAnswer ? (
              <Btn kind="subtle" icon="create-outline" label="Change" onPress={() => { setText(mine); setEditing(true) }}
                testID="live-quick-change" />
            ) : null}
          </View>
          <Text style={styles.answerText} testID="live-quick-mine">{mine}</Text>
        </View>
      ) : !canAnswer ? <Muted>You didn't answer this one.</Muted> : null}
      {showBox ? (
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
            {editing ? <Btn kind="subtle" label="Cancel" onPress={() => { setEditing(false); setError(null) }} testID="live-quick-cancel" /> : null}
            <Btn kind="primary" icon="send" label={mine ? 'Update' : 'Answer'} busy={busy} onPress={send} testID="live-quick-send" />
          </View>
        </>
      ) : null}
      {error ? <Text style={[ixStyles.formError, styles.gapAboveSm]} testID="live-quick-error">{error}</Text> : null}
    </Card>
  )
}

// ─── Poll (FR-507–FR-509): the latest one only ──────────────────────────────

function PollSection({ sessionId, poll, open, act }) {
  const mine = poll?.my_option_ids ?? []
  const [selected, setSelected] = useState(mine)
  const [busy, setBusy] = useState(false)
  const mineKey = mine.join(',')
  // A vote saved here or on another device resets the choice to what the server has
  useEffect(() => { setSelected(mineKey ? mineKey.split(',').map(Number) : []) }, [mineKey])

  if (!poll) {
    return (
      <Card testID="live-poll-section">
        <SectionHead icon="stats-chart-outline" title="Poll" />
        <Muted testID="live-polls-empty">No poll right now. It appears here when the lecturer starts one.</Muted>
      </Card>
    )
  }

  const action = voteAction(poll, selected, open)
  const pollOpen = open && poll.status === 'open'
  const vote = async () => {
    setBusy(true)
    await act(() => api.votePoll(sessionId, poll.id, selected), 'polls', mine.length ? 'Vote changed' : 'Vote sent')
    setBusy(false)
  }

  return (
    <Card testID="live-poll">
      <SectionHead
        icon="stats-chart-outline" title="Poll"
        right={(
          <Badge variant={poll.status === 'open' ? 'green' : 'gray'} dot={poll.status === 'open'}>
            {poll.status === 'open' ? 'Live' : 'Closed'}
          </Badge>
        )}
      />
      <Text style={styles.prompt}>{poll.question}</Text>
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

// ─── React: reactions and "I don't understand" (FR-512, FR-514) ─────────────

function ReactSection({ sessionId, open, showToast }) {
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
      <SectionHead
        icon="happy-outline" title="React"
        right={reactLeft ? <Text style={ixStyles.meta} testID="live-react-cooldown">{cooldownLabel(reactLeft)}</Text> : null}
      />
      <View style={ixStyles.wrap}>
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

// ─── Ask a question (FR-503, FR-504) ─────────────────────────────────────────

function AskSection({ sessionId, open, act }) {
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
      <SectionHead icon="create-outline" title="Ask a question" />
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

// ─── Questions (FR-505, FR-506): newest 3, the rest in a sheet ───────────────

function QuestionRow({ sessionId, q, open, act, first }) {
  return (
    <View style={[styles.qRow, !first && styles.qRowBorder]} testID="live-question">
      <Text style={styles.qText}>{q.text}</Text>
      <View style={styles.metaRow}>
        <Text style={ixStyles.meta}>{askerLabel(q)} · {hhmm(q.created_at)}</Text>
        {questionTags(q).map(b => <Badge key={b.label} variant={b.variant}>{b.label}</Badge>)}
        <View style={styles.flex1} />
        <Btn
          icon={q.upvoted_by_me ? 'arrow-up-circle' : 'arrow-up'} label={String(q.upvotes)}
          kind={q.upvoted_by_me ? 'primary' : 'outline'} disabled={!canUpvote(q, open)}
          accessibilityLabel={`Upvote, ${q.upvotes} so far`} testID="live-q-upvote"
          onPress={() => act(() => api.upvoteQuestion(sessionId, q.id), 'questions')}
        />
      </View>
    </View>
  )
}

function QuestionsSection({ sessionId, questions, open, act }) {
  const [all, setAll] = useState(false)
  const onPage = newestQuestions(questions)
  const more = questions.length > QUESTIONS_ON_PAGE
  return (
    <Card testID="live-questions">
      <SectionHead
        icon="chatbubbles-outline" title={`Questions${questions.length ? ` (${questions.length})` : ''}`}
        right={more ? (
          <Btn kind="subtle" label={`See all ${questions.length}`} onPress={() => setAll(true)} testID="live-questions-all" />
        ) : null}
      />
      {!questions.length ? <Muted testID="live-questions-empty">No questions yet. Be the first to ask.</Muted> : null}
      {onPage.map((q, i) => <QuestionRow key={q.id} sessionId={sessionId} q={q} open={open} act={act} first={i === 0} />)}
      <IxSheet visible={all} title={`All questions (${questions.length})`} onClose={() => setAll(false)} testID="live-questions-sheet">
        <Card>
          {questions.map((q, i) => <QuestionRow key={q.id} sessionId={sessionId} q={q} open={open} act={act} first={i === 0} />)}
        </Card>
      </IxSheet>
    </Card>
  )
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function LiveClass({ route, navigation }) {
  const sessionId = route.params?.sessionId
  const { showToast } = useStudent()
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

  const qq = latestQuick(data.quick_questions)
  const poll = latestPoll(data.polls)

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
        <StatusBanner st={st} onMyQuestions={openMyQuestions} />
        {/* Keyed by id: a new quick question or poll starts with an empty answer box / choice */}
        <QuickSection key={`qq-${qq?.id ?? 'none'}`} sessionId={sessionId} qq={qq} open={st.open} act={act} />
        <PollSection key={`poll-${poll?.id ?? 'none'}`} sessionId={sessionId} poll={poll} open={st.open} act={act} />
        {!st.ended ? (
          <>
            <ReactSection sessionId={sessionId} open={st.open} showToast={showToast} />
            <AskSection sessionId={sessionId} open={st.open} act={act} />
          </>
        ) : null}
        <QuestionsSection sessionId={sessionId} questions={data.questions} open={st.open} act={act} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  banner: { backgroundColor: C.blueLt, borderColor: C.blueLt },
  bannerPaused: { backgroundColor: C.card, borderColor: C.border },
  multiline: { minHeight: 64, textAlignVertical: 'top' },
  prompt: { fontSize: 15, fontWeight: '500', color: C.text, lineHeight: 21 },
  qRow: { paddingVertical: 10 },
  qRowBorder: { borderTopWidth: 1, borderTopColor: C.border },
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
