// Lecturer live interaction for one class session (Module 5, plan-shino.md S37, one-page layout S38b;
// FR-501–FR-516). One scrolling page of section cards: Live status, Student questions, Quick question,
// Poll. Only the newest items sit on the page; history opens in sheets and compose forms are pop-ups, so
// the page never grows. Kept live by WS /interaction/{id}/ws (each `changed` re-reads its topic).
import { useCallback, useEffect, useRef, useState } from 'react'
import { View, Text, ScrollView, TextInput, StyleSheet, RefreshControl } from 'react-native'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  Card, Muted, Loading, LoadError, Btn, Toggle, QuestionRow, PollResults, ReactionChips,
  ConfusionTimeline, TopicList, IxSheet, ixStyles,
} from '../components/InteractionParts'
import { useLecturer } from '../context/LecturerContext'
import * as api from '../services/api'
import { BASE, getToken } from '../services/client'
import {
  TOPICS, topicsFor, interactionState, validatePoll, validateQuick, confusionRecentLabel,
  connectInteractionLive, POLL_MAX_OPTIONS, POLL_MIN_OPTIONS, openQuestions, newestUnanswered,
  latestPoll, latestQuick, newestAnswer, spikeLabel,
} from '../services/interaction'
import { C } from '../theme'

const INLINE_QUESTIONS = 3

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

// A section card with a title row (title, optional count/badge on the right)
function Section({ title, right, children, testID }) {
  return (
    <Card testID={testID}>
      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {right ?? null}
      </View>
      {children}
    </Card>
  )
}

function LinkBtn({ label, onPress, testID, disabled }) {
  return <Btn kind="subtle" label={label} onPress={onPress} testID={testID} disabled={disabled} />
}

// ─── Live status (FR-512, FR-514, FR-515) ────────────────────────────────────

function StatusCard({ st, busy, togglePause, openSummary, questions, reactions, confusion, onConfusion }) {
  const spike = spikeLabel(confusion)
  return (
    <Section title="Live status" testID="ix-status">
      <View style={[ixStyles.wrap, styles.toolbar]}>
        <Text style={[styles.meta, styles.flex1]} testID="ix-state-text">
          {st.ended ? 'The class has ended.'
            : st.open ? 'Students can ask, vote, answer and react.'
              : st.canReopen ? 'Paused: students can read but not post.' : 'Interaction opens when the class starts.'}
        </Text>
        {st.open || st.canReopen ? (
          <Btn icon={st.open ? 'pause' : 'play'} label={st.open ? 'Pause' : 'Resume'} busy={busy}
            onPress={togglePause} testID={st.open ? 'ix-pause' : 'ix-resume'} />
        ) : null}
        <Btn icon="document-text-outline" label="Summary" onPress={openSummary} testID="ix-summary" />
      </View>
      <View style={styles.stats}>
        <View style={styles.stat} testID="ix-confusion">
          <Text style={styles.big} testID="ix-confusion-total">{confusion?.total ?? 0}</Text>
          <Text style={styles.statLabel}>"I don't understand"</Text>
          <Text style={styles.meta} testID="ix-confusion-recent">{confusionRecentLabel(confusion)}</Text>
          {spike ? (
            <View style={styles.gapAboveSm}>
              <Badge variant={spike.variant} dot={spike.variant === 'red'}>{spike.text}</Badge>
            </View>
          ) : null}
          <View style={styles.gapAboveSm}>
            <LinkBtn label="Timeline and topics" onPress={onConfusion} testID="ix-confusion-details" />
          </View>
        </View>
        <View style={styles.stat}>
          <Text style={styles.big} testID="ix-open-questions">{openQuestions(questions).length}</Text>
          <Text style={styles.statLabel}>open questions</Text>
        </View>
      </View>
      <View style={styles.reactionRow}>
        <Text style={ixStyles.label}>Reactions</Text>
        <Text style={styles.meta} testID="ix-reactions-total">{reactions?.total ?? 0} in total</Text>
      </View>
      <ReactionChips counts={reactions?.counts} />
    </Section>
  )
}

function ConfusionSheet({ visible, onClose, confusion }) {
  return (
    <IxSheet visible={visible} onClose={onClose} title={'"I don\'t understand"'} testID="ix-confusion-sheet">
      <Card>
        <Text style={ixStyles.title}>{confusion?.total ?? 0} presses this class</Text>
        <Text style={styles.meta}>{confusionRecentLabel(confusion)}</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={styles.timelineWrap}><ConfusionTimeline timeline={confusion?.timeline} /></View>
        </ScrollView>
        <TopicList topics={confusion?.topics} />
      </Card>
    </IxSheet>
  )
}

// ─── Questions (FR-503–FR-506) ───────────────────────────────────────────────

function QuestionActions({ q, open, act }) {
  return (
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
  )
}

function QuestionsCard({ questions, open, act, onSeeAll }) {
  const inline = newestUnanswered(questions, INLINE_QUESTIONS)
  const waiting = openQuestions(questions).length
  return (
    <Section title="Student questions"
      right={<Text style={styles.meta} testID="ix-questions-count">{waiting} waiting</Text>} testID="ix-questions">
      {!questions.length ? <Muted testID="ix-questions-empty">No questions yet.</Muted> : null}
      {questions.length > 0 && !inline.length ?<Muted testID="ix-questions-clear">Every question is answered or hidden.</Muted> : null}
      {inline.map(q => (
        <QuestionRow key={q.id} q={q} actions={<QuestionActions q={q} open={open} act={act} />} />
      ))}
      {questions.length ? (
        <LinkBtn label={`See all ${questions.length}`} onPress={onSeeAll} testID="ix-questions-all" />
      ) : null}
    </Section>
  )
}

function QuestionsSheet({ visible, onClose, questions, open, act }) {
  return (
    <IxSheet visible={visible} onClose={onClose} title={`All questions (${questions.length})`} testID="ix-questions-sheet">
      {!questions.length ? <Muted>No questions yet.</Muted> : null}
      {questions.map(q => (
        <QuestionRow key={q.id} q={q} testID="ix-sheet-question" actions={<QuestionActions q={q} open={open} act={act} />} />
      ))}
    </IxSheet>
  )
}

// ─── Quick questions (FR-510, FR-511) ────────────────────────────────────────

function QuickItem({ qq, sessionId, open, act, testID, full }) {
  const newest = newestAnswer(qq)
  return (
    <View testID={testID} style={full ? styles.sheetItem : null}>
      <View style={ixStyles.row}>
        <Text style={[ixStyles.title, styles.flex1]}>{qq.prompt}</Text>
        <Badge variant={qq.status === 'open' ? 'green' : 'gray'} dot={qq.status === 'open'}>
          {qq.status === 'open' ? 'Open' : 'Closed'}
        </Badge>
      </View>
      <Text style={styles.meta} testID="ix-quick-count">
        {qq.answer_count ?? 0} {qq.answer_count === 1 ? 'answer' : 'answers'} · up to {qq.max_chars} characters
      </Text>
      {full ? (qq.answers ?? []).map(a => (
        <View key={a.id} style={styles.answer} testID="ix-quick-answer">
          <Text style={styles.answerText}>{a.text}</Text>
        </View>
      )) : newest ? (
        <View style={styles.answer} testID="ix-quick-newest">
          <Text style={styles.metaSm}>Newest answer</Text>
          <Text style={styles.answerText} numberOfLines={2}>{newest.text}</Text>
        </View>
      ) : null}
      {qq.status === 'open' ? (
        <View style={[ixStyles.wrap, styles.gapAbove]}>
          <Btn icon="stop-outline" label="Close" disabled={!open} testID="ix-quick-close"
            onPress={() => act(() => api.closeQuickQuestion(sessionId, qq.id), 'quick_questions')} />
        </View>
      ) : null}
    </View>
  )
}

function QuickCard({ sessionId, quick, open, act, onSeeAll, onAsk }) {
  const latest = latestQuick(quick)
  return (
    <Section title="Quick question" testID="ix-quick-section"
      right={<Btn kind="primary" icon="add" label="Ask the class" disabled={!open} onPress={onAsk} testID="ix-quick-new" />}>
      {latest
        ? <QuickItem qq={latest} sessionId={sessionId} open={open} act={act} testID="ix-quick-latest" />
        : <Muted testID="ix-quick-empty">No quick questions yet.</Muted>}
      {quick.length ? <LinkBtn label={`See all ${quick.length}`} onPress={onSeeAll} testID="ix-quick-all" /> : null}
    </Section>
  )
}

function QuickSheet({ visible, onClose, sessionId, quick, open, act }) {
  return (
    <IxSheet visible={visible} onClose={onClose} title={`Quick questions (${quick.length})`} testID="ix-quick-sheet">
      {quick.map(qq => (
        <Card key={qq.id}><QuickItem qq={qq} sessionId={sessionId} open={open} act={act} testID="ix-quick" full /></Card>
      ))}
    </IxSheet>
  )
}

function QuickCompose({ visible, onClose, sessionId, open, act }) {
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
    if (ok) { setPrompt(''); setError(null); onClose() }
  }

  return (
    <IxSheet visible={visible} onClose={onClose} title="Ask the class" testID="ix-quick-form">
      <Card>
        <Text style={ixStyles.label}>A short question; students answer in a few words, without names</Text>
        <TextInput style={[ixStyles.input, styles.gapBelow, styles.gapAboveSm]} value={prompt} maxLength={300}
          placeholder="e.g. In one word, what does a hash map trade for speed?" placeholderTextColor={C.textHint}
          onChangeText={t => { setPrompt(t); setError(null) }} editable={open} testID="ix-quick-prompt" />
        <View style={[ixStyles.row, ixStyles.wrap]}>
          <Text style={ixStyles.label}>Answer up to</Text>
          <TextInput style={[ixStyles.input, styles.small]} value={maxChars} keyboardType="number-pad"
            onChangeText={t => { setMaxChars(t.replace(/\D/g, '')); setError(null) }} testID="ix-quick-max" />
          <Text style={ixStyles.label}>characters</Text>
        </View>
        {error ? <Text style={[ixStyles.formError, styles.gapAbove]} testID="ix-quick-error">{error}</Text> : null}
        <View style={[ixStyles.wrap, styles.gapAbove]}>
          <Btn label="Cancel" onPress={onClose} testID="ix-quick-cancel" />
          <Btn kind="primary" icon="send" label="Ask" disabled={!open} busy={busy} onPress={ask} testID="ix-quick-create" />
        </View>
      </Card>
    </IxSheet>
  )
}

// ─── Polls (FR-507–FR-509) ───────────────────────────────────────────────────

const emptyPoll = () => ({ question: '', options: ['', ''], multiple: false, showResults: true })

function PollCompose({ visible, onClose, sessionId, act }) {
  const [form, setForm] = useState(emptyPoll)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // A draft made by a "Start now" whose start then failed: a retry only starts it, never makes a second
  const created = useRef(null)
  const set = (patch) => { setForm(f => ({ ...f, ...patch })); setError(null); created.current = null }
  const setOption = (i, text) => set({ options: form.options.map((o, j) => (j === i ? text : o)) })
  const cancel = () => { setForm(emptyPoll()); setError(null); created.current = null; onClose() }

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
    if (ok) { created.current = null; setForm(emptyPoll()); onClose() } else if (created.current) {
      setError('The poll was saved as a draft; start it from the list or press Start now again.')
    }
  }

  return (
    <IxSheet visible={visible} onClose={cancel} title="Create a poll" testID="ix-poll-form">
      <Card>
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
          <Btn label="Cancel" onPress={cancel} testID="ix-poll-cancel" />
          <Btn label="Save draft" onPress={() => save(false)} busy={busy} testID="ix-poll-create" />
          <Btn kind="primary" icon="play" label="Start now" onPress={() => save(true)} busy={busy} testID="ix-poll-create-start" />
        </View>
      </Card>
    </IxSheet>
  )
}

const POLL_BADGE = { draft: ['Draft', 'gray'], open: ['Live', 'green'], closed: ['Closed', 'gray'] }

function PollItem({ p, sessionId, open, act, testID }) {
  const [label, variant] = POLL_BADGE[p.status] ?? POLL_BADGE.closed
  return (
    <View testID={testID}>
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
    </View>
  )
}

function PollCard({ sessionId, polls, open, act, onSeeAll, onCreate }) {
  const latest = latestPoll(polls)
  return (
    <Section title="Poll" testID="ix-poll-section"
      right={<Btn kind="primary" icon="add" label="Create a poll" disabled={!open} onPress={onCreate} testID="ix-poll-new" />}>
      {latest
        ? <PollItem p={latest} sessionId={sessionId} open={open} act={act} testID="ix-poll-latest" />
        : <Muted testID="ix-polls-empty">No polls yet.</Muted>}
      {polls.length ? (
        <LinkBtn label={`See all ${polls.length} ${polls.length === 1 ? 'poll' : 'polls'}`} onPress={onSeeAll} testID="ix-polls-all" />
      ) : null}
    </Section>
  )
}

function PollsSheet({ visible, onClose, sessionId, polls, open, act }) {
  return (
    <IxSheet visible={visible} onClose={onClose} title={`Polls (${polls.length})`} testID="ix-polls-sheet">
      {polls.map(p => (
        <Card key={p.id}><PollItem p={p} sessionId={sessionId} open={open} act={act} testID="ix-poll" /></Card>
      ))}
    </IxSheet>
  )
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function LiveInteraction({ route, navigation }) {
  const sessionId = route.params?.sessionId
  const { showToast } = useLecturer()
  const [sheet, setSheet] = useState(null)   // which pop-up is open
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

  // A pause or the class end closes an open compose form for good (it doesn't pop up again on resume)
  useEffect(() => {
    if (!st.open) setSheet(s => (s === 'quick-new' || s === 'poll-new' ? null : s))
  }, [st.open])

  const togglePause = async () => {
    setBusy(true)
    try {
      setSession(st.open ? await api.pauseInteraction(sessionId) : await api.resumeInteraction(sessionId))
      showToast(st.open ? 'Interaction paused: students can\'t post until you resume' : 'Interaction resumed', 'success')
    } catch (e) { showToast(e.message, 'error') } finally { setBusy(false) }
  }

  const onRefresh = async () => { setRefreshing(true); await loadAll(); setRefreshing(false) }
  const openSummary = () => { setSheet(null); navigation.navigate('InteractionSummary', { sessionId }) }
  const closeSheet = () => setSheet(null)

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

  const shared = { sessionId, open: st.open, act }

  return (
    <View style={styles.screen}>
      {header}
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        <View style={styles.page}>
          {loadError ? <LoadError message={loadError} onRetry={loadAll} /> : null}

          {st.ended ? (
            <Card style={styles.banner} testID="ix-ended">
              <Text style={ixStyles.title}>The class has ended</Text>
              <Muted>Interaction is closed. Everything students posted is in the summary.</Muted>
              <View style={styles.gapAboveSm}>
                <Btn kind="primary" icon="document-text-outline" label="View summary" onPress={openSummary} testID="ix-ended-summary" />
              </View>
            </Card>
          ) : null}

          <StatusCard st={st} busy={busy} togglePause={togglePause} openSummary={openSummary}
            questions={data.questions} reactions={data.reactions} confusion={data.confusion}
            onConfusion={() => setSheet('confusion')} />
          <QuestionsCard questions={data.questions} open={st.open} act={act} onSeeAll={() => setSheet('questions')} />
          <QuickCard {...shared} quick={data.quick_questions}
            onSeeAll={() => setSheet('quick')} onAsk={() => setSheet('quick-new')} />
          <PollCard {...shared} polls={data.polls}
            onSeeAll={() => setSheet('polls')} onCreate={() => setSheet('poll-new')} />
        </View>
      </ScrollView>

      <ConfusionSheet visible={sheet === 'confusion'} onClose={closeSheet} confusion={data.confusion} />
      <QuestionsSheet visible={sheet === 'questions'} onClose={closeSheet} questions={data.questions} open={st.open} act={act} />
      <QuickSheet visible={sheet === 'quick'} onClose={closeSheet} {...shared} quick={data.quick_questions} />
      <QuickCompose visible={sheet === 'quick-new' && st.open} onClose={closeSheet} {...shared} />
      <PollsSheet visible={sheet === 'polls'} onClose={closeSheet} {...shared} polls={data.polls} />
      <PollCompose visible={sheet === 'poll-new' && st.open} onClose={closeSheet} sessionId={sessionId} act={act} />
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  page: { width: '100%', maxWidth: 880, alignSelf: 'center' },
  toolbar: { alignItems: 'center', marginBottom: 10 },
  banner: { backgroundColor: C.blueLt, borderColor: C.blueLt },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 },
  sectionTitle: { fontSize: 15, fontWeight: '600', color: C.text },
  stats: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  stat: {
    flexGrow: 1, flexBasis: 200, borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: 10,
    backgroundColor: C.card,
  },
  statLabel: { fontSize: 13, color: C.text, fontWeight: '500' },
  reactionRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 12, marginBottom: 6 },
  meta: { fontSize: 12, color: C.textSub, marginTop: 4 },
  metaSm: { fontSize: 11, color: C.textHint },
  big: { fontSize: 26, fontWeight: '600', color: C.text },
  gapBelow: { marginBottom: 8 },
  gapAbove: { marginTop: 10 },
  gapAboveSm: { marginTop: 6 },
  small: { width: 64, textAlign: 'center' },
  sheetItem: { paddingBottom: 2 },
  timelineWrap: { minWidth: 280 },
  answer: { borderTopWidth: 1, borderTopColor: C.border, paddingVertical: 8, marginTop: 6 },
  answerText: { fontSize: 13, color: C.text },
})
