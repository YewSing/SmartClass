import { useMemo, useRef, useState } from 'react'
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useInteraction } from '../services/useInteraction'
import { Sheet, ModalTitle } from '../components/Modals'
import { C } from '../theme'

const REACTIONS = [
  ['thumbs_up', 'Thumbs up', '👍'],
  ['clear', 'Clear', '💡'],
  ['too_slow', 'Too slow', '🐢'],
  ['too_fast', 'Too fast', '⚡'],
]
const IDU_COOLDOWN_MS = 120000

// Small section header: icon + medium-weight title + optional trailing action
function Section({ icon, title, action, children, tint = 'blue' }) {
  const accent = tint === 'purple' ? C.purple : tint === 'green' ? C.greenDk : tint === 'red' ? C.redDk : C.blueDk
  const iconBg = tint === 'purple' ? C.purpleLt : tint === 'green' ? C.greenLt : tint === 'red' ? C.redLt : C.blueLt
  return (
    <View style={[s.section, s[`section_${tint}`]]}>
      <View style={s.sectionHead}>
        <View style={[s.sectionIcon, { backgroundColor: iconBg }]}>
          <Ionicons name={icon} size={16} color={accent} />
        </View>
        <Text style={s.sectionTitle}>{title}</Text>
        {action}
      </View>
      {children}
    </View>
  )
}

function LinkButton({ label, onPress, testID }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} testID={testID} hitSlop={6}>
      <Text style={s.link}>{label}</Text>
    </Pressable>
  )
}

function Chip({ children, tone }) {
  return <Text style={[s.chip, tone === 'green' && s.chipGreen, tone === 'red' && s.chipRed]}>{children}</Text>
}

function Empty({ children }) {
  return <Text style={s.empty}>{children}</Text>
}

function QuestionCard({ item, writable, busy, onUpvote }) {
  return (
    <View style={s.item}>
      <Text style={s.body}>{item.text}</Text>
      <View style={s.row}>
        <Text style={s.meta} numberOfLines={1}>
          {item.anonymous ? 'Anonymous' : item.is_mine ? 'You' : item.author_name} · {item.created_at?.slice(11, 16)}
        </Text>
        {item.pinned ? <Chip>Pinned</Chip> : null}
        {item.answered ? <Chip tone="green">Answered</Chip> : null}
        <View style={s.grow} />
        <Pressable accessibilityRole="button" disabled={!writable || busy || item.upvoted_by_me}
          onPress={() => onUpvote(item)}
          style={[s.vote, item.upvoted_by_me && s.voted]}>
          <Ionicons name="arrow-up" size={13} color={item.upvoted_by_me ? C.blueDk : C.textSub} />
          <Text style={[s.voteText, item.upvoted_by_me && { color: C.blueDk }]}>{item.votes}</Text>
        </Pressable>
      </View>
    </View>
  )
}

function PollCard({ poll, writable, busy, run }) {
  const [draft, setDraft] = useState(null)
  const choices = draft ?? poll.my_option_indexes ?? []
  const open = writable && poll.status === 'open'
  const choose = index => {
    if (!poll.multiple) setDraft([index])
    else setDraft(choices.includes(index) ? choices.filter(value => value !== index) : [...choices, index])
  }
  return (
    <View style={s.item}>
      <View style={s.row}>
        <Text style={[s.body, s.grow]}>{poll.prompt}</Text>
        <Chip tone={poll.status === 'open' ? 'green' : undefined}>{poll.status === 'open' ? 'Active' : 'Closed'}</Chip>
      </View>
      <Text style={s.meta}>{poll.multiple ? 'Choose one or more' : 'Choose one'}</Text>
      {poll.options.map((option, index) => {
        const picked = choices.includes(index)
        const count = poll.results?.option_counts[index] ?? null
        const share = poll.results?.respondent_count ? Math.round(100 * count / poll.results.respondent_count) : 0
        return (
          <Pressable key={index} accessibilityRole="button" disabled={!open || busy} onPress={() => choose(index)}
            style={[s.option, picked && s.optionPicked, (!open || poll.results) && { width: '100%' }]}>
            <View style={s.row}>
              <Ionicons name={picked ? 'checkbox' : 'square-outline'} size={16}
                color={picked ? C.primary : C.gray400} style={{ marginRight: 8 }} />
              <Text style={[s.body, s.grow]}>{option}</Text>
              {count != null ? <Text style={s.meta}>{share}%</Text> : null}
            </View>
            {count != null
              ? <View style={s.track}><View style={[s.bar, { width: `${share}%` }]} /></View>
              : null}
          </Pressable>
        )
      })}
      {poll.results ? <Text style={s.meta}>{poll.results.respondent_count} responses</Text> : null}
      {poll.my_option_indexes && !draft ? <Text style={s.meta}>Your vote is saved — you can change it while the poll is open.</Text> : null}
      {open ? (
        <Pressable accessibilityRole="button" disabled={busy || !choices.length}
          style={[s.primaryBtn, (busy || !choices.length) && s.disabled]}
          onPress={async () => {
            if (await run('PUT', `/polls/${poll.id}/vote`, { option_indexes: choices }, 'Vote saved.')) setDraft(null)
          }}>
          <Text style={s.primaryText}>{poll.my_option_indexes ? 'Update vote' : 'Submit vote'}</Text>
        </Pressable>
      ) : null}
    </View>
  )
}

function QuickPromptCard({ prompt, writable, busy, run }) {
  const [text, setText] = useState('')
  const open = writable && prompt.status === 'open'
  return (
    <View style={s.item}>
      <View style={s.row}>
        <Text style={[s.body, s.grow]}>{prompt.prompt}</Text>
        <Chip tone={open ? 'green' : undefined}>{open ? 'Active' : 'Closed'}</Chip>
      </View>
      {prompt.answered_by_me ? <Text style={s.meta}>Your answer is saved — you can update it.</Text> : null}
      {open ? (
        <>
          <TextInput style={s.input} value={text} onChangeText={setText} multiline
            placeholder="Write a short answer" accessibilityLabel="Quick answer" maxLength={prompt.max_length} />
          <View style={s.row}>
            <Text style={[s.meta, s.grow]}>{text.length} / {prompt.max_length}</Text>
            <Pressable accessibilityRole="button" disabled={busy || !text.trim()}
              style={[s.primaryBtn, s.compact, (busy || !text.trim()) && s.disabled]}
              onPress={async () => {
                if (await run('POST', `/quick-prompts/${prompt.id}/answers`, { text: text.trim() }, 'Answer saved.')) setText('')
              }}>
              <Text style={s.primaryText}>{prompt.answered_by_me ? 'Update answer' : 'Submit answer'}</Text>
            </Pressable>
          </View>
        </>
      ) : <Text style={s.meta}>This question is closed.</Text>}
    </View>
  )
}

function LiveClassRoom({ navigation, sessionId, courseName, courseCode }) {
  const insets = useSafeAreaInsets()
  const { state, error, busy, connected, refresh, submit } = useInteraction(sessionId)
  const [question, setQuestion] = useState('')
  const [anonymous, setAnonymous] = useState(false)
  const [askOpen, setAskOpen] = useState(false)
  const [allQuestions, setAllQuestions] = useState(false)
  const [sortByVotes, setSortByVotes] = useState(false)
  const [pollHistory, setPollHistory] = useState(false)
  const [topicOpen, setTopicOpen] = useState(false)
  const [topicText, setTopicText] = useState('')
  const [iduAt, setIduAt] = useState(0)
  const [notice, setNotice] = useState(null)
  const writable = Boolean(state?.can_participate)
  const iduRemaining = Math.max(0, IDU_COOLDOWN_MS - (Date.now() - iduAt))
  const iduBlocked = busy || iduRemaining > 0

  async function run(method, path, body, message) {
    setNotice(null)
    try {
      if (!await submit(method, path, body)) return false
      setNotice({ message })
      return true
    } catch (err) {
      setNotice({ error: true, message: err.status === 429
        ? 'Please wait a moment before sending this again.'
        : err.message || 'Could not save your response.' })
      return false
    }
  }

  async function sendIdu() {
    if (await run('POST', '/confusion', { topic_tag: topicText.trim() || null }, 'Got it — your lecturer has been notified.')) {
      setIduAt(Date.now())
      setTopicOpen(false)
      setTopicText('')
    }
  }

  const activePoll = state?.polls.find(poll => poll.status === 'open') ?? null
  const pastPolls = state ? state.polls.filter(poll => poll.id !== activePoll?.id) : []
  const activePrompt = state?.quick_prompts.find(prompt => prompt.status === 'open')
    ?? state?.quick_prompts[0] ?? null
  const latestQuestion = state?.questions[0] ?? null
  const sortedQuestions = state
    ? [...state.questions].sort((a, b) => (sortByVotes ? b.votes - a.votes : 0))
    : []

  return <View style={s.page}>
    <View style={[s.topbar, { paddingTop: insets.top + 8 }]}>
      <Pressable onPress={navigation.goBack} accessibilityRole="button" accessibilityLabel="Back" style={s.back}>
        <Ionicons name="chevron-back" color={C.text} size={24} />
      </Pressable>
      <Text style={s.topTitle}>Classroom interaction</Text>
      {state ? <Text style={s.liveMeta} testID="interaction-status">{writable
        ? connected ? 'Live' : 'Reconnecting…'
        : state.status === 'scheduled' ? 'Not started' : 'Ended'}</Text> : null}
    </View>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={s.content}>
      {error ? <View style={s.item}><Text style={[s.meta, { color: C.redDk }]}>{error}</Text>
        <Pressable accessibilityRole="button" onPress={refresh}><Text style={s.link}>Retry</Text></Pressable></View> : null}
      {!state && !error ? <ActivityIndicator color={C.primary} /> : null}
      {notice ? <Text accessibilityLiveRegion="polite" style={[s.notice, notice.error && s.error]}>{notice.message}</Text> : null}
      {state ? <>
        <View style={s.classHero} testID="live-class-overview">
          <View style={s.heroTop}>
            <View style={s.heroIcon}><Ionicons name="people-outline" size={21} color="#fff" /></View>
            <View style={s.grow}>
              <Text style={s.heroEyebrow}>YOUR CLASSROOM</Text>
              <Text style={s.heroTitle} numberOfLines={1}>{courseName || courseCode || 'Live class'}</Text>
            </View>
            <View style={[s.livePill, !writable && s.endedPill]}>
              <View style={[s.liveDot, !writable && s.endedDot]} />
              <Text style={[s.livePillText, !writable && s.endedPillText]}>{writable ? connected ? 'LIVE' : 'RECONNECTING' : state.status === 'scheduled' ? 'UPCOMING' : 'ENDED'}</Text>
            </View>
          </View>
          <Text style={s.heroCopy}>{writable
            ? 'Join in: ask questions, share a quick answer or let your lecturer know how the lesson feels.'
            : 'Catch up on the class questions and activity from this session.'}</Text>
          <View style={s.heroStats}>
            <View style={s.heroStat}><Text style={s.heroNumber}>{state.questions.length}</Text><Text style={s.heroLabel}>Questions</Text></View>
            <View style={s.heroDivider} />
            <View style={s.heroStat}><Text style={s.heroNumber}>{state.polls.filter(poll => poll.status === 'open').length}</Text><Text style={s.heroLabel}>Live polls</Text></View>
            <View style={s.heroDivider} />
            <View style={s.heroStat}><Text style={s.heroNumber}>{state.quick_prompts.filter(prompt => prompt.status === 'open').length}</Text><Text style={s.heroLabel}>Quick answers</Text></View>
          </View>
        </View>
        {/* ── Live Questions ── */}
        <Section icon="chatbubbles-outline" title="Live Questions" tint="blue"
          action={<LinkButton label={`View all (${state.questions.length})`} onPress={() => setAllQuestions(true)} testID="view-all-questions" />}>
          {writable ? (
            askOpen ? (
              <View style={s.item}>
                <TextInput style={s.input} multiline value={question} onChangeText={setQuestion} maxLength={1000}
                  placeholder="What would you like explained?" accessibilityLabel="Question" testID="interaction-question-input" />
                <View style={s.row}>
                  <Text style={[s.meta, s.grow]}>Post anonymously</Text>
                  <Switch value={anonymous} onValueChange={setAnonymous} accessibilityLabel="Ask anonymously" testID="interaction-anonymous" />
                  <Pressable accessibilityRole="button" disabled={busy || !question.trim()}
                    style={[s.primaryBtn, s.compact, (busy || !question.trim()) && s.disabled]}
                    onPress={async () => {
                      if (await run('POST', '/questions', { text: question.trim(), anonymous }, 'Question sent.')) {
                        setQuestion('')
                        setAskOpen(false)
                      }
                    }}>
                    <Text style={s.primaryText}>Post</Text>
                  </Pressable>
                </View>
              </View>
            ) : (
              <LinkButton label="Ask a question…" onPress={() => setAskOpen(true)} testID="open-ask-question" />
            )
          ) : null}
          {latestQuestion
            ? <QuestionCard item={latestQuestion} writable={writable} busy={busy}
                onUpvote={item => run('PUT', `/questions/${item.id}/upvote`, undefined, 'Upvote saved.')} />
            : <Empty>No questions yet.</Empty>}
        </Section>

        {/* ── Live Poll ── */}
        <Section icon="stats-chart-outline" title="Live Poll" tint="purple"
          action={pastPolls.length ? <LinkButton label="View history" onPress={() => setPollHistory(true)} testID="view-poll-history" /> : null}>
          {activePoll
            ? <PollCard poll={activePoll} writable={writable} busy={busy} run={run} />
            : pastPolls.length ? <Empty>No active poll.</Empty> : <Empty>No polls have started.</Empty>}
        </Section>

        {/* ── Quick Answers ── */}
        <Section icon="create-outline" title="Quick Answers" tint="green">
          {activePrompt
            ? <QuickPromptCard prompt={activePrompt} writable={writable} busy={busy} run={run} />
            : <Empty>No quick questions yet.</Empty>}
        </Section>

        {/* ── Reactions ── */}
        <Section icon="happy-outline" title="How's the pace?" tint="purple">
          <View style={s.reactionRow}>
            {REACTIONS.map(([kind, label, emoji]) => (
              <Pressable key={kind} accessibilityRole="button" disabled={busy || !writable}
                onPress={() => run('POST', '/reactions', { kind }, 'Reaction sent.')}
                style={[s.reaction, !writable && s.disabled]}>
                <Text style={s.reactionEmoji}>{emoji}</Text>
                <Text style={s.reactionLabel}>{label}</Text>
              </Pressable>
            ))}
          </View>
        </Section>

        {/* ── I Don't Understand ── */}
        <Section icon="help-circle-outline" title="Need help?" tint="red">
          <Pressable accessibilityRole="button" disabled={iduBlocked} testID="idu-button"
            onPress={sendIdu} style={[s.idu, iduBlocked && s.disabled]}>
            <Ionicons name="alert-circle" size={26} color={iduBlocked ? C.gray400 : C.redDk} />
            <View style={{ flex: 1 }}>
              <Text style={[s.iduText, iduBlocked && { color: C.textSub }]}>I Don't Understand</Text>
              <Text style={s.iduSub}>Tell the lecturer — anonymous</Text>
            </View>
            {iduBlocked && iduRemaining > 0
              ? <Text style={s.iduCooldown}>{Math.ceil(iduRemaining / 1000)}s</Text> : null}
          </Pressable>
          {topicOpen ? (
            <View style={s.row}>
              <TextInput style={[s.input, s.compactInput]} value={topicText} onChangeText={setTopicText} maxLength={100}
                placeholder="Optional topic (e.g. recursion)" accessibilityLabel="Topic (optional)" />
              <LinkButton label="Hide" onPress={() => setTopicOpen(false)} />
            </View>
          ) : (
            <LinkButton label="Add topic (optional)" onPress={() => setTopicOpen(true)} />
          )}
        </Section>
      </> : null}
    </ScrollView>

    {/* All questions modal */}
    <Sheet visible={allQuestions} onClose={() => setAllQuestions(false)}>
      <ModalTitle>All questions</ModalTitle>
      <View style={s.row}>
        <LinkButton label={sortByVotes ? 'Sort: most upvoted' : 'Sort: newest'} onPress={() => setSortByVotes(value => !value)} />
      </View>
      {sortedQuestions.length
        ? sortedQuestions.map(item => (
          <QuestionCard key={item.id} item={item} writable={writable} busy={busy}
            onUpvote={item => run('PUT', `/questions/${item.id}/upvote`, undefined, 'Upvote saved.')} />
        ))
        : <Empty>No questions yet.</Empty>}
    </Sheet>

    {/* Poll history modal */}
    <Sheet visible={pollHistory} onClose={() => setPollHistory(false)}>
      <ModalTitle>Poll history</ModalTitle>
      {pastPolls.length ? pastPolls.map(poll => <PollCard key={poll.id} poll={poll} writable={false} busy={busy} run={run} />)
        : <Empty>No past polls.</Empty>}
    </Sheet>
  </View>
}

export default function LiveClass({ route, navigation }) {
  const { sessionId, courseName, courseCode } = route.params ?? {}
  return <LiveClassRoom key={sessionId} {...{ sessionId, courseName, courseCode, navigation }} />
}

const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: C.bg },
  topbar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingBottom: 8, gap: 8, backgroundColor: C.card, borderBottomWidth: 1, borderColor: C.border },
  back: { width: 44, height: 44, justifyContent: 'center', alignItems: 'center' },
  topTitle: { fontSize: 17, fontWeight: '600', color: C.text, flex: 1 },
  liveMeta: { color: C.greenDk, fontSize: 13 },
  content: { width: '100%', maxWidth: 720, alignSelf: 'center', padding: 16, gap: 14, paddingBottom: 40 },
  classHero: { backgroundColor: '#173B68', borderRadius: 18, padding: 17, gap: 12 },
  heroTop: { flexDirection: 'row', alignItems: 'center', gap: 11 },
  heroIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.16)', justifyContent: 'center', alignItems: 'center' },
  heroEyebrow: { color: '#B9D9FF', fontSize: 10, fontWeight: '800', letterSpacing: 1.1 },
  heroTitle: { color: '#fff', fontSize: 18, fontWeight: '800', marginTop: 2 },
  heroCopy: { color: '#D9E8F8', fontSize: 13, lineHeight: 19 },
  livePill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 9, paddingVertical: 6, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.16)' },
  liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#86EFAC' },
  livePillText: { color: '#fff', fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },
  endedPill: { backgroundColor: 'rgba(255,255,255,0.12)' },
  endedDot: { backgroundColor: '#CBD5E1' },
  endedPillText: { color: '#D5E1EF' },
  heroStats: { flexDirection: 'row', alignItems: 'center', paddingTop: 10, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.18)' },
  heroStat: { flex: 1, alignItems: 'center', gap: 2 },
  heroNumber: { color: '#fff', fontSize: 19, fontWeight: '800' },
  heroLabel: { color: '#C6D8EB', fontSize: 10, fontWeight: '600', textAlign: 'center' },
  heroDivider: { width: 1, height: 28, backgroundColor: 'rgba(255,255,255,0.2)' },
  section: { gap: 12, padding: 14, borderRadius: 16, borderWidth: 1, borderColor: C.border, backgroundColor: C.card },
  section_blue: { borderTopWidth: 3, borderTopColor: C.primary },
  section_purple: { borderTopWidth: 3, borderTopColor: C.purple },
  section_green: { borderTopWidth: 3, borderTopColor: C.green },
  section_red: { borderTopWidth: 3, borderTopColor: C.red },
  sectionIcon: { width: 30, height: 30, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: C.text, flex: 1 },
  link: { color: C.blueDk, fontSize: 13, fontWeight: '500' },
  item: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: 12, gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  grow: { flex: 1 },
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  meta: { color: C.textSub, fontSize: 12, lineHeight: 17 },
  empty: { color: C.textSub, fontSize: 13, paddingVertical: 2 },
  chip: { color: C.textSub, fontSize: 11, backgroundColor: C.gray100, borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, overflow: 'hidden', alignSelf: 'flex-start' },
  chipGreen: { color: C.greenDk, backgroundColor: C.greenLt },
  chipRed: { color: C.redDk, backgroundColor: C.redLt },
  vote: { flexDirection: 'row', alignItems: 'center', gap: 3, borderWidth: 1, borderColor: C.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5, backgroundColor: C.card },
  voted: { backgroundColor: C.blueLt, borderColor: C.primary },
  voteText: { fontSize: 12, color: C.textSub, fontWeight: '500' },
  option: { borderWidth: 1, borderColor: C.border, borderRadius: 8, padding: 10, gap: 6, backgroundColor: C.gray50 },
  optionPicked: { borderColor: C.primary, backgroundColor: C.blueLt },
  track: { backgroundColor: C.gray100, borderRadius: 3, height: 5, overflow: 'hidden' },
  bar: { height: '100%', backgroundColor: C.primary },
  input: { minHeight: 44, padding: 10, borderWidth: 1, borderColor: C.border, borderRadius: 8, color: C.text, fontSize: 14, backgroundColor: C.card },
  compactInput: { minHeight: 40, flex: 1 },
  primaryBtn: { minHeight: 40, paddingHorizontal: 14, borderRadius: 8, justifyContent: 'center', alignItems: 'center', backgroundColor: C.primary },
  compact: { minHeight: 36, paddingHorizontal: 12 },
  primaryText: { color: '#fff', fontSize: 13, fontWeight: '500' },
  disabled: { opacity: 0.55 },
  notice: { color: C.greenDk, padding: 10, borderRadius: 8, backgroundColor: C.greenLt, fontSize: 13 },
  error: { color: C.redDk, backgroundColor: C.redLt },
  reactionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  reaction: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: C.border, borderRadius: 20, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: C.card },
  reactionEmoji: { fontSize: 15 },
  reactionLabel: { fontSize: 13, color: C.text, fontWeight: '400' },
  idu: { flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1.5, borderColor: '#FCA5A5', borderRadius: 14, padding: 17, backgroundColor: C.redLt },
  iduText: { color: C.redDk, fontSize: 16, fontWeight: '700' },
  iduSub: { color: C.textSub, fontSize: 12, marginTop: 2 },
  iduCooldown: { color: C.redDk, fontSize: 13, fontWeight: '500' },
})
