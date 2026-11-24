// Student live class for one class session (Module 5, plan-shino.md S38, S38c; FR-503–FR-516).
// One scrolling page of section cards, latest only (Shino's layout 2026-11-23): status banner, the
// lecturer's latest quick question, the latest poll, React (reactions + "I don't understand"), Ask
// a question, and the newest questions (the rest in a "See all" sheet). The quick question and poll
// cards only appear once the lecturer has published one; after voting the result sits on each option
// (S38f). Reactions and "I don't understand" are on until tapped again (S38g). Earlier polls and quick questions aren't listed. Kept live by WS /interaction/{id}/ws: each
// `changed` re-reads its topic, and `closed` turns the screen read-only. Opened from Home's Today card.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  View, Text, ScrollView, TextInput, TouchableOpacity, StyleSheet, RefreshControl, AppState,
  Keyboard, KeyboardAvoidingView,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  Card, Muted, Loading, LoadError, Btn, Toggle, OptionPick, PollResults, IxSheet, SectionHead, Avatar,
  ixStyles,
} from '../components/InteractionParts'
import { useStudent } from '../context/StudentContext'
import * as api from '../services/api'
import { BASE, getToken, refreshAccessToken } from '../services/client'
import { hhmm } from '../services/attendance'
import {
  TOPICS, topicsFor, interactionState, validateQuestion, askerLabel, questionTags, canUpvote,
  toggleChoice, voteAction, pollMode, pollResultsVisible, validateQuickAnswer, charsLeft,
  REACTIONS, CONFUSION_TOPIC_MAX_CHARS, NO_SIGNALS, afterReactionTap, afterConfusionTap,
  connectInteractionLive, QUESTION_MAX_CHARS, latestPoll, latestQuick, newestQuestions, QUESTIONS_ON_PAGE,
} from '../services/interaction'
import { C, TONES, reactionTone } from '../interactionTheme'

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

// ─── Status banner ───────────────────────────────────────────────────────────

function StatusBanner({ st, onMyQuestions }) {
  if (st.ended) {
    return (
      <Card style={styles.banner} testID="live-ended">
        <View style={ixStyles.row}>
          <Badge variant={st.variant} style={styles.onTint}>{st.label}</Badge>
          <Text style={[ixStyles.title, styles.flex1]}>The class has ended</Text>
        </View>
        <Muted>Interaction is closed. You can still read everything below.</Muted>
        <View style={[ixStyles.wrap, styles.gapAboveSm]}>
          <Btn kind="primary" icon="chatbubbles-outline" label="My questions" onPress={onMyQuestions} testID="live-ended-my-questions" />
        </View>
      </Card>
    )
  }
  const t = TONES[st.variant] ?? TONES.gray
  return (
    <Card style={[styles.status, { backgroundColor: t.lt, borderColor: t.bd }]} testID="live-status">
      <View style={[styles.statusDot, { backgroundColor: t.solid }]} />
      <Text style={[styles.statusText, { color: t.dk }]} testID="live-state-text">{st.text}</Text>
      <Btn icon="chatbubbles-outline" label="My questions" onPress={onMyQuestions} testID="live-my-questions" />
    </Card>
  )
}

// A card the lecturer published: tinted while it is open, plain once it is closed
function PublishedCard({ tone, live, children, testID }) {
  const t = TONES[tone]
  return (
    <Card style={live ? { backgroundColor: t.lt, borderColor: t.solid } : { borderColor: t.bd }} testID={testID}>
      {children}
    </Card>
  )
}

// ─── Quick question (FR-510, FR-511): the latest one only ───────────────────

function QuickSection({ sessionId, qq, open, act, onTyping }) {
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)

  if (!qq) return null   // nothing published yet

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
    <PublishedCard tone="purple" live={showBox} testID="live-quick">
      <SectionHead
        icon="flash" title="Quick question" tone="purple"
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
            <Ionicons name="checkmark-circle" size={16} color={C.green} />
            <Text style={[styles.answerLabel, styles.flex1]}>Your answer</Text>
            {canAnswer ? (
              <Btn kind="link" tone="green" icon="create-outline" label="Change" onPress={() => { setText(mine); setEditing(true) }}
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
            onChangeText={t => { setText(t); setError(null) }} onFocus={onTyping} testID="live-quick-input"
          />
          <View style={[ixStyles.row, styles.gapAboveSm]}>
            <Text style={[ixStyles.meta, styles.flex1]}>
              {charsLeft(text, qq.max_chars)} characters left · only the lecturer sees answers, without names
            </Text>
            {editing ? <Btn kind="subtle" label="Cancel" onPress={() => { setEditing(false); setError(null) }} testID="live-quick-cancel" /> : null}
            <Btn kind="primary" tone="purple" icon="send" label={mine ? 'Update' : 'Answer'} busy={busy} onPress={send} testID="live-quick-send" />
          </View>
        </>
      ) : null}
      {error ? <Text style={[ixStyles.formError, styles.gapAboveSm]} testID="live-quick-error">{error}</Text> : null}
    </PublishedCard>
  )
}

// ─── Poll (FR-507–FR-509): the latest one only ──────────────────────────────

function PollSection({ sessionId, poll, open, act }) {
  const mine = poll?.my_option_ids ?? []
  const [selected, setSelected] = useState(mine)
  const [busy, setBusy] = useState(false)
  const [changing, setChanging] = useState(false)
  const mineKey = mine.join(',')
  // A vote saved here or on another device resets the choice to what the server has
  useEffect(() => { setSelected(mineKey ? mineKey.split(',').map(Number) : []) }, [mineKey])

  if (!poll) return null   // nothing published yet

  const action = voteAction(poll, selected, open)
  const pollOpen = open && poll.status === 'open'
  const mode = pollMode(poll, open, changing)
  const counted = pollResultsVisible(poll)
  const vote = async () => {
    setBusy(true)
    const ok = await act(() => api.votePoll(sessionId, poll.id, selected), 'polls', mine.length ? 'Vote changed' : 'Vote sent')
    setBusy(false)
    if (ok) setChanging(false)
  }
  const cancelChange = () => { setSelected(mine); setChanging(false) }

  return (
    <PublishedCard tone="blue" live={mode === 'pick'} testID="live-poll">
      <SectionHead
        icon="stats-chart" title="Poll" tone="blue"
        right={(
          <Badge variant={poll.status === 'open' ? 'green' : 'gray'} dot={poll.status === 'open'}>
            {poll.status === 'open' ? 'Live' : 'Closed'}
          </Badge>
        )}
      />
      <Text style={styles.prompt}>{poll.question}</Text>
      {mode === 'pick' ? (
        <>
          <Text style={[ixStyles.meta, styles.gapAboveSm]}>
            {poll.multiple ? 'Pick one or more' : 'Pick one'}
            {poll.show_results && !mine.length ? ' · results show after you vote' : ''}
          </Text>
          {poll.options.map((o, i) => (
            <OptionPick
              key={o.id} text={o.text} multiple={poll.multiple} selected={selected.includes(o.id)}
              onPress={() => setSelected(sel => toggleChoice(sel, o.id, poll.multiple))}
              testID={`live-poll-option-${i}`}
            />
          ))}
          <View style={styles.gapAbove}>
            <Btn kind="primary" wide icon="checkmark" label={action.label} disabled={!action.enabled} busy={busy}
              onPress={vote} testID="live-poll-vote" />
          </View>
          {changing ? (
            <View style={styles.gapAboveSm}>
              <Btn kind="link" wide label="Cancel" onPress={cancelChange} testID="live-poll-cancel" />
            </View>
          ) : null}
        </>
      ) : (
        <>
          <PollResults poll={poll} />
          <View style={[ixStyles.row, styles.gapAbove]}>
            {counted ? (
              <Text style={[ixStyles.meta, styles.flex1]} testID="live-poll-total">{poll.total_voters} voted</Text>
            ) : (
              <Text style={[ixStyles.meta, styles.flex1]} testID="live-poll-closed-note">
                {!mine.length ? "You didn't vote in this poll."
                  : pollOpen ? "Your vote is in. The lecturer isn't showing results yet."
                    : "Your vote was counted. The lecturer isn't showing results."}
              </Text>
            )}
            {pollOpen ? (
              <Btn kind="link" icon="create-outline" label="Change vote" onPress={() => setChanging(true)} testID="live-poll-change" />
            ) : null}
          </View>
        </>
      )}
    </PublishedCard>
  )
}

// ─── React: reactions and "I don't understand" (FR-512, FR-514) ─────────────

function ReactSection({ sessionId, open, signals, setSignals, reload, showToast, onTyping }) {
  const [topicOpen, setTopicOpen] = useState(false)
  const [topic, setTopic] = useState('')
  const [busy, setBusy] = useState(false)
  const on = signals ?? NO_SIGNALS

  // Shown at once; a refused tap goes back to what the server has
  const tap = async (next, fn, done) => {
    setBusy(true)
    setSignals(next)
    try {
      await fn()
      if (done) showToast(done, 'success')
      return true
    } catch (e) {
      showToast(e.message, 'error')
      reload('session').catch(() => {})
      return false
    } finally {
      await reload('signals').catch(() => {})
      setBusy(false)
    }
  }

  const react = (r) => {
    const next = afterReactionTap(on, r.kind)
    return tap(next, () => (next.reaction ? api.sendReaction(sessionId, r.kind) : api.cancelReaction(sessionId)),
      next.reaction ? `Sent: ${r.label}` : 'Reaction taken back')
  }
  const confused = async () => {
    const next = afterConfusionTap(on, topic)
    const ok = await tap(next, () => (next.confused ? api.pressConfusion(sessionId, next.topic) : api.cancelConfusion(sessionId)),
      next.confused ? "The lecturer can see the class is unsure (your name isn't shown)" : 'Taken back')
    if (ok) { setTopic(''); setTopicOpen(false) }
  }
  const off = !open || busy

  return (
    <Card testID="live-signals">
      <SectionHead
        icon="happy" title="React" tone="orange"
        right={on.reaction ? <Text style={ixStyles.meta} testID="live-react-hint">Tap again to take back</Text> : null}
      />
      <View style={styles.reactions}>
        {REACTIONS.map(r => {
          const t = TONES[reactionTone(r.kind)]
          const mine = on.reaction === r.kind
          return (
            <TouchableOpacity
              key={r.kind} disabled={off} onPress={() => react(r)} testID={`live-react-${r.kind}`}
              style={[styles.reaction, { backgroundColor: t.lt, borderColor: t.bd },
                mine && { borderColor: t.solid, borderWidth: 2.5 }, !open && styles.off]}
              accessibilityRole="button" accessibilityLabel={mine ? `${r.label}, on` : r.label}
              accessibilityState={{ disabled: off, selected: mine }}
            >
              <Text style={styles.emoji}>{r.emoji}</Text>
              <Text style={[styles.reactionText, { color: t.dk }]}>{r.label}</Text>
              {mine ? <Ionicons name="checkmark-circle" size={18} color={t.dk} /> : null}
            </TouchableOpacity>
          )
        })}
      </View>

      {topicOpen && !on.confused ? (
        <TextInput
          style={[ixStyles.input, styles.gapAbove]} value={topic} maxLength={CONFUSION_TOPIC_MAX_CHARS}
          placeholder="What about? (optional, e.g. recursion)" placeholderTextColor={C.textHint}
          onChangeText={setTopic} onFocus={onTyping} testID="live-confused-topic"
        />
      ) : null}
      <TouchableOpacity
        style={[styles.lost, on.confused && styles.lostOn, !open && styles.off]}
        disabled={off} onPress={confused} testID="live-confused" accessibilityRole="button"
        accessibilityLabel={on.confused ? "I don't understand, on" : "I don't understand"}
        accessibilityState={{ disabled: off, selected: on.confused }}
      >
        <Text style={styles.emojiLg}>😕</Text>
        <View style={styles.flex1}>
          <Text style={[styles.lostTitle, on.confused && styles.lostTextOn]}>I don't understand</Text>
          <Text style={[styles.lostSub, on.confused && styles.lostTextOn]} testID="live-confused-state">
            {on.confused
              ? `Sent without your name${on.topic ? ` · ${on.topic}` : ''} · tap again to take back`
              : 'Tap to tell the lecturer, without your name'}
          </Text>
        </View>
        {on.confused ? <Ionicons name="checkmark-circle" size={22} color="#fff" /> : null}
      </TouchableOpacity>
      {!topicOpen && !on.confused ? (
        <View style={[ixStyles.row, styles.gapAboveSm]}>
          <Btn kind="link" tone="orange" icon="pricetag-outline" label="Add a topic" disabled={off}
            onPress={() => setTopicOpen(true)} testID="live-confused-add-topic" />
        </View>
      ) : null}
    </Card>
  )
}

// ─── Ask a question (FR-503, FR-504) ─────────────────────────────────────────

function AskSection({ sessionId, open, act, onTyping }) {
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
      <SectionHead icon="create" title="Ask a question" tone="teal" />
      <TextInput
        style={[ixStyles.input, styles.multiline]} value={text} maxLength={QUESTION_MAX_CHARS} multiline
        placeholder="Ask the lecturer a question" placeholderTextColor={C.textHint} editable={open}
        onChangeText={t => { setText(t); setError(null) }} onFocus={onTyping} testID="live-ask-input"
      />
      <View style={[ixStyles.row, styles.gapAbove]}>
        <Toggle label="Ask anonymously" value={anonymous} onChange={setAnonymous} disabled={!open} testID="live-ask-anon" />
        <View style={styles.flex1} />
        <Btn kind="primary" tone="teal" icon="send" label="Send" disabled={!open || !text.trim()} busy={busy}
          onPress={send} testID="live-ask-send" />
      </View>
      {anonymous ? <Muted style={styles.small}>Your name isn't shown to the lecturer or the class.</Muted> : null}
      {error ? <Text style={[ixStyles.formError, styles.gapAboveSm]} testID="live-ask-error">{error}</Text> : null}
    </Card>
  )
}

// ─── Questions (FR-505, FR-506): newest 3, the rest in a sheet ───────────────

function QuestionRow({ sessionId, q, open, act }) {
  return (
    <View style={[styles.q, q.answered && styles.qAnswered, q.mine && styles.qMine]} testID="live-question">
      <View style={styles.qHead}>
        <Avatar name={q.anonymous ? null : q.mine ? 'You' : q.author_name} />
        <View style={styles.qWho}>
          <Text style={styles.qAuthor} numberOfLines={1}>{askerLabel(q)}</Text>
          <Text style={ixStyles.meta}>{hhmm(q.created_at)}</Text>
        </View>
        {questionTags(q).map(b => <Badge key={b.label} variant={b.variant} style={styles.onTint}>{b.label}</Badge>)}
      </View>
      <Text style={styles.qText}>{q.text}</Text>
      <View style={styles.qFoot}>
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
        icon="chatbubbles" tone="teal" title={`Questions${questions.length ? ` (${questions.length})` : ''}`}
        right={more ? (
          <Btn kind="soft" tone="teal" label={`See all ${questions.length}`} onPress={() => setAll(true)} testID="live-questions-all" />
        ) : null}
      />
      {!questions.length ? <Muted testID="live-questions-empty">No questions yet. Be the first to ask.</Muted> : null}
      {onPage.map(q => <QuestionRow key={q.id} sessionId={sessionId} q={q} open={open} act={act} />)}
      <IxSheet visible={all} title={`All questions (${questions.length})`} onClose={() => setAll(false)} testID="live-questions-sheet">
        {questions.map(q => <QuestionRow key={q.id} sessionId={sessionId} q={q} open={open} act={act} />)}
      </IxSheet>
    </Card>
  )
}

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function LiveClass({ route, navigation }) {
  const sessionId = route.params?.sessionId
  const { showToast } = useStudent()
  const [session, setSession] = useState(null)
  const [data, setData] = useState({ questions: [], polls: [], quick_questions: [], signals: NO_SIGNALS })
  const [loadError, setLoadError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const put = (key) => (value) => setData(d => ({ ...d, [key]: value }))
  const loaders = useRef(null)
  loaders.current = {
    session: async () => setSession(await api.getInteraction(sessionId)),
    questions: async () => put('questions')((await api.getInteractionQuestions(sessionId)).questions),
    polls: async () => put('polls')((await api.getInteractionPolls(sessionId)).polls),
    quick_questions: async () => put('quick_questions')((await api.getQuickQuestions(sessionId)).quick_questions),
    signals: async () => put('signals')(await api.getMySignals(sessionId)),
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
    // S38e: after the end, re-check the class every few seconds; a reopen in the same slot (S38a)
    // shows Live again here and the socket reconnects (its `connected` re-reads every topic)
    const checkStatus = async () => {
      const s = await api.getInteraction(sessionId)
      if (active) setSession(s)
      return s
    }
    const onReopen = () => { if (active) showToast('The class is live again', 'info') }
    const connect = () => connectInteractionLive({
      baseUrl: BASE, sessionId, getToken, refreshToken: refreshAccessToken, onMessage, checkStatus, onReopen,
    })
    let live = connect()
    const sub = AppState.addEventListener('change', (next) => {
      // After the end the client's own status re-check covers a reopen (S38e)
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

  // The card being typed in (its box and its button) is scrolled to the top, clear of the keyboard. A
  // little after the keyboard shows: Android first scrolls only the text box into view by itself.
  const scroll = useRef(null)
  const cardY = useRef({})
  const typingIn = useRef(null)
  const showTyping = useCallback(() => {
    const y = cardY.current[typingIn.current]
    if (y != null) setTimeout(() => scroll.current?.scrollTo({ y: Math.max(0, y - 8), animated: true }), 250)
  }, [])
  useEffect(() => {
    const shown = Keyboard.addListener('keyboardDidShow', showTyping)
    return () => shown.remove()
  }, [showTyping])
  const place = (key) => (e) => { cardY.current[key] = e.nativeEvent.layout.y }
  // Moving to another box while the keyboard stays open fires no keyboardDidShow
  const typing = (key) => () => { typingIn.current = key; if (Keyboard.isVisible?.()) showTyping() }

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
    <KeyboardAvoidingView style={styles.screen} behavior="padding">
      {header}
      <ScrollView
        ref={scroll}
        style={styles.screen}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {loadError ? <LoadError message={loadError} onRetry={loadAll} /> : null}
        <StatusBanner st={st} onMyQuestions={openMyQuestions} />
        {/* Both appear only once the lecturer has published one. Keyed by id: a new quick question or
            poll starts with an empty answer box / choice */}
        <View onLayout={place('quick')}>
          <QuickSection key={`qq-${qq?.id ?? 'none'}`} sessionId={sessionId} qq={qq} open={st.open} act={act}
            onTyping={typing('quick')} />
        </View>
        <PollSection key={`poll-${poll?.id ?? 'none'}`} sessionId={sessionId} poll={poll} open={st.open} act={act} />
        {!st.ended ? (
          <>
            <View onLayout={place('react')}>
              <ReactSection sessionId={sessionId} open={st.open} signals={data.signals} setSignals={put('signals')}
                reload={reload} showToast={showToast} onTyping={typing('react')} />
            </View>
            <View onLayout={place('ask')}>
              <AskSection sessionId={sessionId} open={st.open} act={act} onTyping={typing('ask')} />
            </View>
          </>
        ) : null}
        <QuestionsSection sessionId={sessionId} questions={data.questions} open={st.open} act={act} />
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  banner: { backgroundColor: C.gray100, borderColor: C.border },
  onTint: { backgroundColor: C.card },
  status: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8, paddingVertical: 10 },
  statusDot: { width: 9, height: 9, borderRadius: 5 },
  statusText: { flexGrow: 1, flexShrink: 1, flexBasis: 150, fontSize: 13, fontWeight: '600' },
  multiline: { minHeight: 80, textAlignVertical: 'top' },
  prompt: { fontSize: 17, fontWeight: '600', color: C.text, lineHeight: 23 },
  reactions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  reaction: {
    flexGrow: 1, flexBasis: '45%', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1.5, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 8,
  },
  reactionText: { fontSize: 14, fontWeight: '600' },
  emoji: { fontSize: 22, lineHeight: 29 },
  emojiLg: { fontSize: 28, lineHeight: 37 },
  off: { opacity: 0.45 },
  lost: {
    flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 12, borderWidth: 1.5, borderColor: C.orange,
    borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, backgroundColor: C.orangeLt,
  },
  lostOn: { backgroundColor: C.orangeDk, borderColor: C.orangeDk },
  lostTextOn: { color: '#fff' },
  lostTitle: { fontSize: 15, fontWeight: '700', color: C.orangeDk },
  lostSub: { fontSize: 12, color: C.orangeDk, marginTop: 1 },
  q: {
    borderWidth: 1, borderColor: C.tealBd, backgroundColor: C.tealLt, borderRadius: 12, padding: 12, marginTop: 8,
  },
  qAnswered: { backgroundColor: C.gray50, borderColor: C.border },
  qMine: { backgroundColor: C.blueLt, borderColor: C.primary },
  qHead: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  qWho: { flexGrow: 1, flexShrink: 1, minWidth: 90 },
  qAuthor: { fontSize: 13, fontWeight: '600', color: C.text },
  qText: { fontSize: 15, color: C.text, lineHeight: 21 },
  qFoot: { flexDirection: 'row', justifyContent: 'flex-end', marginTop: 6 },
  gapAbove: { marginTop: 10 },
  gapAboveSm: { marginTop: 6 },
  small: { fontSize: 12 },
  answer: {
    backgroundColor: C.greenLt, borderWidth: 1, borderColor: C.greenBd, borderRadius: 10, paddingHorizontal: 12,
    paddingVertical: 10, marginTop: 10, gap: 4,
  },
  answerLabel: { fontSize: 12, fontWeight: '700', color: C.greenDk },
  answerText: { fontSize: 15, color: C.text },
})
