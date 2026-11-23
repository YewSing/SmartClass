// Lecturer live interaction for one class session (Module 5, plan-shino.md S37; FR-501–FR-516).
// Questions to moderate, polls, quick questions, reactions and the confusion timeline, kept live by
// WS /interaction/{id}/ws (each `changed` re-reads its topic). Opened from the dashboard's session card.
import { useCallback, useEffect, useRef, useState } from 'react'
import { View, Text, ScrollView, TextInput, StyleSheet, RefreshControl } from 'react-native'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  Card, Heading, Muted, Loading, LoadError, Btn, Toggle, Segments, QuestionRow, PollResults,
  ReactionGrid, ConfusionTimeline, TopicList, ixStyles,
} from '../components/InteractionParts'
import { useLecturer } from '../context/LecturerContext'
import { useWideLayout } from '../hooks/useWideLayout'
import * as api from '../services/api'
import { BASE, getToken } from '../services/client'
import {
  TOPICS, topicsFor, interactionState, validatePoll, validateQuick, confusionRecentLabel,
  connectInteractionLive, POLL_MAX_OPTIONS, POLL_MIN_OPTIONS,
} from '../services/interaction'
import { C } from '../theme'

async function refreshViaApi() {
  try { await api.getLecturer(); return true } catch { return false }
}

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
    // A caller that arrives during a read waits for (and sees the failure of) that same run
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

// ─── Questions (FR-503–FR-506) ───────────────────────────────────────────────

function QuestionsPanel({ questions, open, act }) {
  if (!questions.length) return <Card><Muted testID="ix-questions-empty">No questions yet.</Muted></Card>
  return questions.map(q => (
    <QuestionRow key={q.id} q={q} actions={(
      <>
        <Btn testID="ix-q-answer" icon={q.answered ? 'refresh-outline' : 'checkmark-outline'}
          label={q.answered ? 'Mark unanswered' : 'Mark answered'} disabled={!open}
          onPress={() => act(() => api.moderateQuestion(q.sessionId, q.id, { answered: !q.answered }), 'questions')} />
        <Btn testID="ix-q-pin" icon="pin-outline" label={q.pinned ? 'Unpin' : 'Pin'} disabled={!open}
          onPress={() => act(() => api.moderateQuestion(q.sessionId, q.id, { pinned: !q.pinned }), 'questions')} />
        <Btn testID="ix-q-hide" kind="subtle" icon={q.hidden ? 'eye-outline' : 'eye-off-outline'}
          label={q.hidden ? 'Show' : 'Hide'} disabled={!open}
          onPress={() => act(() => api.moderateQuestion(q.sessionId, q.id, { hidden: !q.hidden }), 'questions')} />
      </>
    )} />
  ))
}

// ─── Polls (FR-507–FR-509) ───────────────────────────────────────────────────

const emptyPoll = () => ({ question: '', options: ['', ''], multiple: false, showResults: true })

function PollForm({ sessionId, onDone, act }) {
  const [form, setForm] = useState(emptyPoll)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // A draft made by a "Start now" whose start then failed: a retry only starts it, never makes a second
  const created = useRef(null)
  const set = (patch) => { setForm(f => ({ ...f, ...patch })); setError(null); created.current = null }
  const setOption = (i, text) => set({ options: form.options.map((o, j) => (j === i ? text : o)) })

  const save = async (start) => {
    const v = validatePoll(form)
    if (v.error) { setError(v.error); return }
    setBusy(true)
    const ok = await act(async () => {
      if (!created.current) {
        const poll = await api.createPoll(sessionId, {
          question: v.question, options: v.options, multiple: form.multiple, show_results: form.showResults,
        })
        created.current = poll.id
      }
      if (start) await api.startPoll(sessionId, created.current)
    }, 'polls', start ? 'Poll started' : 'Poll saved as a draft')
    setBusy(false)
    if (ok) { created.current = null; setForm(emptyPoll()); onDone() } else if (created.current) {
      setError('The poll was saved as a draft; start it from the list or press Start now again.')
    }
  }

  return (
    <Card testID="ix-poll-form">
      <Text style={ixStyles.label}>Question</Text>
      <TextInput style={[ixStyles.input, styles.gapBelow]} value={form.question} maxLength={300}
        placeholder="e.g. Which sorting algorithm is stable?" placeholderTextColor={C.textHint}
        onChangeText={t => set({ question: t })} testID="ix-poll-question" />
      <Text style={ixStyles.label}>Options</Text>
      {form.options.map((o, i) => (
        <View key={i} style={[ixStyles.row, styles.gapBelow]}>
          <TextInput style={[ixStyles.input, styles.flex1]} value={o} maxLength={120}
            placeholder={`Option ${i + 1}`} placeholderTextColor={C.textHint}
            onChangeText={t => setOption(i, t)} testID={`ix-poll-option-input-${i}`} />
          {form.options.length > POLL_MIN_OPTIONS ? (
            <Btn kind="subtle" icon="close" label="" testID={`ix-poll-remove-${i}`}
              onPress={() => set({ options: form.options.filter((_, j) => j !== i) })} />
          ) : null}
        </View>
      ))}
      {form.options.length < POLL_MAX_OPTIONS ? (
        <View style={styles.gapBelow}>
          <Btn kind="subtle" icon="add" label="Add option" testID="ix-poll-add-option"
            onPress={() => set({ options: [...form.options, ''] })} />
        </View>
      ) : null}
      <Toggle label="Students can pick more than one" value={form.multiple}
        onChange={v => set({ multiple: v })} testID="ix-poll-multiple" />
      <Toggle label="Show results to students" value={form.showResults}
        onChange={v => set({ showResults: v })} testID="ix-poll-show" />
      {error ? <Text style={[ixStyles.formError, styles.gapAbove]} testID="ix-poll-error">{error}</Text> : null}
      <View style={[ixStyles.wrap, styles.gapAbove]}>
        <Btn label="Cancel" onPress={onDone} testID="ix-poll-cancel" />
        <Btn label="Save draft" onPress={() => save(false)} busy={busy} testID="ix-poll-create" />
        <Btn kind="primary" icon="play" label="Start now" onPress={() => save(true)} busy={busy} testID="ix-poll-create-start" />
      </View>
    </Card>
  )
}

const POLL_BADGE = { draft: ['Draft', 'gray'], open: ['Live', 'green'], closed: ['Closed', 'gray'] }

function PollsPanel({ sessionId, polls, open, act }) {
  const [creating, setCreating] = useState(false)
  return (
    <>
      {creating
        ? <PollForm sessionId={sessionId} act={act} onDone={() => setCreating(false)} />
        : (
          <View style={styles.gapBelow}>
            <Btn kind="primary" icon="add" label="New poll" disabled={!open} onPress={() => setCreating(true)} testID="ix-poll-new" />
          </View>
        )}
      {!polls.length ? <Card><Muted testID="ix-polls-empty">No polls yet.</Muted></Card> : null}
      {polls.map(p => {
        const [label, variant] = POLL_BADGE[p.status] ?? POLL_BADGE.closed
        return (
          <Card key={p.id} testID="ix-poll">
            <View style={ixStyles.row}>
              <Text style={[ixStyles.title, styles.flex1]}>{p.question}</Text>
              <Badge variant={variant} dot={p.status === 'open'}>{label}</Badge>
            </View>
            <Text style={styles.meta} testID="ix-poll-total">
              {p.multiple ? 'Multiple choice' : 'Single choice'} · {p.total_voters ?? 0} voted
            </Text>
            <PollResults poll={p} />
            <View style={[ixStyles.wrap, styles.gapAbove]}>
              {p.status === 'draft' ? (
                <Btn kind="primary" icon="play" label="Start" disabled={!open} testID="ix-poll-start"
                  onPress={() => act(() => api.startPoll(sessionId, p.id), 'polls', 'Poll started')} />
              ) : null}
              {p.status === 'open' ? (
                <Btn icon="stop-outline" label="Close poll" disabled={!open} testID="ix-poll-close"
                  onPress={() => act(() => api.closePoll(sessionId, p.id), 'polls', 'Poll closed')} />
              ) : null}
              <Toggle label="Students see results" value={p.show_results} disabled={!open}
                testID="ix-poll-results-toggle"
                onChange={v => act(() => api.setPollShowResults(sessionId, p.id, v), 'polls')} />
            </View>
          </Card>
        )
      })}
    </>
  )
}

// ─── Quick questions (FR-510, FR-511) ────────────────────────────────────────

function QuickPanel({ sessionId, quick, open, act }) {
  const [prompt, setPrompt] = useState('')
  const [maxChars, setMaxChars] = useState('140')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const ask = async () => {
    const v = validateQuick({ prompt, maxChars })
    if (v.error) { setError(v.error); return }
    setBusy(true)
    const ok = await act(() => api.createQuickQuestion(sessionId, v), 'quick_questions', 'Quick question sent')
    setBusy(false)
    if (ok) { setPrompt(''); setError(null) }
  }

  return (
    <>
      <Card testID="ix-quick-form">
        <Text style={ixStyles.label}>Ask the class a short question</Text>
        <TextInput style={[ixStyles.input, styles.gapBelow, styles.gapAboveSm]} value={prompt} maxLength={300}
          placeholder="e.g. In one word, what does a hash map trade for speed?" placeholderTextColor={C.textHint}
          onChangeText={t => { setPrompt(t); setError(null) }} editable={open} testID="ix-quick-prompt" />
        <View style={[ixStyles.row, ixStyles.wrap]}>
          <Text style={ixStyles.label}>Answer up to</Text>
          <TextInput style={[ixStyles.input, styles.small]} value={maxChars} keyboardType="number-pad"
            onChangeText={t => { setMaxChars(t.replace(/\D/g, '')); setError(null) }} testID="ix-quick-max" />
          <Text style={ixStyles.label}>characters</Text>
          <View style={styles.flex1} />
          <Btn kind="primary" icon="send" label="Ask" disabled={!open} busy={busy} onPress={ask} testID="ix-quick-create" />
        </View>
        {error ? <Text style={[ixStyles.formError, styles.gapAbove]} testID="ix-quick-error">{error}</Text> : null}
      </Card>
      {!quick.length ? <Card><Muted testID="ix-quick-empty">No quick questions yet.</Muted></Card> : null}
      {quick.map(qq => (
        <Card key={qq.id} testID="ix-quick">
          <View style={ixStyles.row}>
            <Text style={[ixStyles.title, styles.flex1]}>{qq.prompt}</Text>
            <Badge variant={qq.status === 'open' ? 'green' : 'gray'} dot={qq.status === 'open'}>
              {qq.status === 'open' ? 'Open' : 'Closed'}
            </Badge>
          </View>
          <Text style={styles.meta} testID="ix-quick-count">
            {qq.answer_count ?? 0} {qq.answer_count === 1 ? 'answer' : 'answers'} · up to {qq.max_chars} characters
          </Text>
          {(qq.answers ?? []).map(a => (
            <View key={a.id} style={styles.answer} testID="ix-quick-answer">
              <Text style={styles.answerText}>{a.text}</Text>
            </View>
          ))}
          {qq.status === 'open' ? (
            <View style={[ixStyles.wrap, styles.gapAbove]}>
              <Btn icon="stop-outline" label="Close" disabled={!open} testID="ix-quick-close"
                onPress={() => act(() => api.closeQuickQuestion(sessionId, qq.id), 'quick_questions')} />
            </View>
          ) : null}
        </Card>
      ))}
    </>
  )
}

// ─── Reactions and confusion (FR-512, FR-514, FR-515) ────────────────────────

function SignalsPanel({ reactions, confusion }) {
  return (
    <>
      <Heading right={<Text style={styles.meta} testID="ix-reactions-total">{reactions?.total ?? 0} in total</Text>}>
        Reactions
      </Heading>
      <Card><ReactionGrid counts={reactions?.counts} /></Card>
      <Heading right={confusion?.spike_active
        ? <Badge variant="red" dot>Many confused now</Badge> : null}>
        "I don't understand"
      </Heading>
      <Card testID="ix-confusion">
        <View style={ixStyles.row}>
          <Text style={styles.big} testID="ix-confusion-total">{confusion?.total ?? 0}</Text>
          <View style={styles.flex1}>
            <Text style={ixStyles.title}>presses this class</Text>
            <Text style={styles.meta} testID="ix-confusion-recent">{confusionRecentLabel(confusion)}</Text>
          </View>
        </View>
        <ConfusionTimeline timeline={confusion?.timeline} />
        <TopicList topics={confusion?.topics} />
      </Card>
    </>
  )
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function LiveInteraction({ route, navigation }) {
  const sessionId = route.params?.sessionId
  const { showToast } = useLecturer()
  const wide = useWideLayout()
  const [tab, setTab] = useState('questions')
  const [session, setSession] = useState(null)
  const [data, setData] = useState({ questions: [], polls: [], quick_questions: [], reactions: null, confusion: null })
  const [loadError, setLoadError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [busy, setBusy] = useState(false)

  const put = (key) => (value) => setData(d => ({ ...d, [key]: value }))
  const loaders = useRef(null)
  loaders.current = {
    session: async () => setSession(await api.getInteraction(sessionId)),
    questions: async () => put('questions')((await api.getInteractionQuestions(sessionId)).questions
      .map(q => ({ ...q, sessionId }))),
    polls: async () => put('polls')((await api.getInteractionPolls(sessionId)).polls),
    quick_questions: async () => put('quick_questions')((await api.getQuickQuestions(sessionId)).quick_questions),
    reactions: async () => put('reactions')(await api.getReactionCounts(sessionId)),
    confusion: async () => put('confusion')(await api.getConfusion(sessionId)),
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

  // Live updates: each message says which topic to re-read
  useEffect(() => {
    if (!sessionId) return undefined
    let active = true
    const live = connectInteractionLive({
      baseUrl: BASE, sessionId, getToken, refreshToken: refreshViaApi,
      onMessage: (m) => {
        if (!active) return
        for (const t of topicsFor(m)) reload(t).catch(() => {})
        // A lecturer pause is the echo of this screen's own (or another tab's) action: its toast is enough
        if (m.type === 'closed' && m.reason === 'class_ended') showToast('The class has ended', 'info')
      },
    })
    return () => { active = false; live.close() }
  }, [sessionId, reload, showToast])

  // One lecturer action, then re-read its topic (the websocket echo is coalesced with it)
  const act = useCallback(async (fn, topic, done) => {
    try {
      await fn()
      if (done) showToast(done, 'success')
      await reload(topic).catch(() => {})
      return true
    } catch (e) {
      showToast(e.message, 'error')
      reload('session').catch(() => {})
      return false
    }
  }, [reload, showToast])

  const st = interactionState(session)

  const togglePause = async () => {
    setBusy(true)
    try {
      setSession(st.open ? await api.pauseInteraction(sessionId) : await api.resumeInteraction(sessionId))
      showToast(st.open ? 'Interaction paused: students can\'t post until you resume' : 'Interaction resumed', 'success')
    } catch (e) { showToast(e.message, 'error') } finally { setBusy(false) }
  }

  const onRefresh = async () => { setRefreshing(true); await loadAll(); setRefreshing(false) }
  const openSummary = () => navigation.navigate('InteractionSummary', { sessionId })

  const header = (
    <Topbar
      title="Class interaction"
      sub={session ? `${session.course_code} · ${session.course_name}` : ''}
      onBack={() => navigation.goBack()}
      right={<Badge variant={st.variant} dot={st.open}>{st.label}</Badge>}
    />
  )

  if (!session) {
    return (
      <View style={styles.screen}>
        {header}
        <View style={styles.content}>
          {loadError ? <LoadError message={loadError} onRetry={loadAll} /> : <Loading text="Loading the class interaction…" />}
        </View>
      </View>
    )
  }

  const counts = {
    questions: data.questions.filter(q => !q.hidden && !q.answered).length,
    polls: data.polls.filter(p => p.status === 'open').length,
    quick: data.quick_questions.filter(q => q.status === 'open').length,
  }
  const mainTabs = [
    { key: 'questions', label: 'Questions', count: counts.questions },
    { key: 'polls', label: 'Polls', count: counts.polls },
    { key: 'quick', label: 'Quick', count: counts.quick },
    ...(wide ? [] : [{ key: 'signals', label: 'Signals' }]),
  ]
  const shownTab = wide && tab === 'signals' ? 'questions' : tab

  const panel = {
    questions: <QuestionsPanel questions={data.questions} open={st.open} act={act} />,
    polls: <PollsPanel sessionId={sessionId} polls={data.polls} open={st.open} act={act} />,
    quick: <QuickPanel sessionId={sessionId} quick={data.quick_questions} open={st.open} act={act} />,
    signals: <SignalsPanel reactions={data.reactions} confusion={data.confusion} />,
  }[shownTab]

  return (
    <View style={styles.screen}>
      {header}
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {loadError ? <LoadError message={loadError} onRetry={loadAll} /> : null}

        {st.ended ? (
          <Card style={styles.banner} testID="ix-ended">
            <Text style={ixStyles.title}>The class has ended</Text>
            <Muted>Interaction is closed. Everything students posted is in the summary.</Muted>
            <View style={styles.gapAboveSm}>
              <Btn kind="primary" icon="document-text-outline" label="View summary" onPress={openSummary} testID="ix-ended-summary" />
            </View>
          </Card>
        ) : (
          <View style={[ixStyles.wrap, styles.toolbar]}>
            <Text style={[styles.meta, styles.flex1]} testID="ix-state-text">
              {st.open ? 'Students can ask, vote, answer and react.'
                : st.canReopen ? 'Paused: students can read but not post.' : 'Interaction opens when the class starts.'}
            </Text>
            {st.open || st.canReopen ? (
              <Btn icon={st.open ? 'pause' : 'play'} label={st.open ? 'Pause' : 'Resume'} busy={busy}
                onPress={togglePause} testID={st.open ? 'ix-pause' : 'ix-resume'} />
            ) : null}
            <Btn icon="document-text-outline" label="Summary" onPress={openSummary} testID="ix-summary" />
          </View>
        )}

        {wide ? (
          <View style={styles.columns}>
            <View style={styles.mainCol}>
              <Segments items={mainTabs} value={shownTab} onChange={setTab} />
              {panel}
            </View>
            <View style={styles.sideCol} testID="ix-signals">
              <SignalsPanel reactions={data.reactions} confusion={data.confusion} />
            </View>
          </View>
        ) : (
          <>
            <Segments items={mainTabs} value={shownTab} onChange={setTab} />
            {shownTab === 'signals' ? <View testID="ix-signals">{panel}</View> : panel}
          </>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  toolbar: { alignItems: 'center', marginBottom: 12 },
  banner: { backgroundColor: C.blueLt, borderColor: C.blueLt },
  columns: { flexDirection: 'row', gap: 16, alignItems: 'flex-start' },
  mainCol: { flex: 3, minWidth: 0 },
  sideCol: { flex: 2, minWidth: 0 },
  meta: { fontSize: 12, color: C.textSub, marginTop: 4 },
  big: { fontSize: 28, fontWeight: '600', color: C.text, minWidth: 40 },
  gapBelow: { marginBottom: 8 },
  gapAbove: { marginTop: 10 },
  gapAboveSm: { marginTop: 6 },
  small: { width: 64, textAlign: 'center' },
  answer: { borderTopWidth: 1, borderTopColor: C.border, paddingVertical: 8, marginTop: 4 },
  answerText: { fontSize: 13, color: C.text },
})
