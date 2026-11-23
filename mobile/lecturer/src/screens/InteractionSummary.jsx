// Interaction summary of one class session (Module 5, plan-shino.md S37; pills S38d; FR-518, FR-519):
// one category at a time — Questions, Polls, Quick questions, Reactions, Confusion — chosen with pill
// buttons instead of one long page, plus the CSV export. Opened from Home (latest-class card), the
// live screen and the Interaction tab. No student identity beyond the names of non-anonymous
// questions (S36).
import { useCallback, useEffect, useState } from 'react'
import { View, Text, ScrollView, StyleSheet, RefreshControl } from 'react-native'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  Card, Heading, Muted, Loading, LoadError, Btn, QuestionRow, PollResults, ReactionGrid,
  ConfusionTimeline, TopicList, Stat, Pills, ixStyles,
} from '../components/InteractionParts'
import { useLecturer } from '../context/LecturerContext'
import * as api from '../services/api'
import { interactionState, summaryCsvName, summaryPills } from '../services/interaction'
import { C } from '../theme'

function QuestionsPart({ summary }) {
  const qc = summary.question_counts
  return (
    <View testID="ix-summary-part-questions">
      <View style={[ixStyles.wrap, styles.gapBelow]}>
        <Stat label="Questions" value={qc.asked} testID="ix-summary-asked" />
        <Stat label="Answered" value={qc.answered} testID="ix-summary-answered" />
        <Stat label="Anonymous" value={qc.anonymous} testID="ix-summary-anonymous" />
        <Stat label="Upvotes" value={qc.upvotes} testID="ix-summary-upvotes" />
      </View>
      {!summary.questions.length ? <Card><Muted>No questions this class.</Muted></Card> : null}
      {summary.questions.map(q => <QuestionRow key={q.id} q={q} testID="ix-summary-question" />)}
    </View>
  )
}

function PollsPart({ summary }) {
  return (
    <View testID="ix-summary-part-polls">
      {!summary.polls.length ? <Card><Muted>No polls this class.</Muted></Card> : null}
      {summary.polls.map(p => (
        <Card key={p.id} testID="ix-summary-poll">
          <Text style={ixStyles.title}>{p.question}</Text>
          <Text style={styles.meta}>{p.total_voters ?? 0} voted · {p.multiple ? 'multiple choice' : 'single choice'}</Text>
          <PollResults poll={p} testID="ix-summary-poll-option" />
        </Card>
      ))}
    </View>
  )
}

function QuickPart({ summary }) {
  return (
    <View testID="ix-summary-part-quick">
      {!summary.quick_questions.length ? <Card><Muted>No quick questions this class.</Muted></Card> : null}
      {summary.quick_questions.map(qq => (
        <Card key={qq.id} testID="ix-summary-quick">
          <Text style={ixStyles.title}>{qq.prompt}</Text>
          <Text style={styles.meta}>{qq.answer_count} {qq.answer_count === 1 ? 'answer' : 'answers'}</Text>
          {qq.answers.map(a => (
            <View key={a.id} style={styles.answer} testID="ix-summary-quick-answer">
              <Text style={styles.answerText}>{a.text}</Text>
            </View>
          ))}
        </Card>
      ))}
    </View>
  )
}

function ReactionsPart({ summary }) {
  return (
    <View testID="ix-summary-part-reactions">
      <Heading right={<Text style={styles.meta} testID="ix-summary-reactions-total">{summary.reactions_total} in total</Text>}>
        Reactions
      </Heading>
      <Card><ReactionGrid counts={summary.reactions} testIDPrefix="ix-summary-reaction" /></Card>
    </View>
  )
}

function ConfusionPart({ summary }) {
  const c = summary.confusion
  return (
    <View testID="ix-summary-part-confusion">
      <Heading>"I don't understand"</Heading>
      <Card testID="ix-summary-confusion">
        <Text style={ixStyles.title}>
          <Text testID="ix-summary-confusion-total">{c.total}</Text> presses ·{' '}
          <Text testID="ix-summary-spikes">{c.spikes}</Text>{' '}
          {c.spikes === 1 ? 'spike' : 'spikes'}
        </Text>
        <ConfusionTimeline timeline={c.timeline} testID="ix-summary-confusion-bar" />
        <TopicList topics={c.topics} testID="ix-summary-topic" />
      </Card>
    </View>
  )
}

const PARTS = {
  questions: QuestionsPart, polls: PollsPart, quick: QuickPart, reactions: ReactionsPart, confusion: ConfusionPart,
}

export default function InteractionSummary({ route, navigation }) {
  const sessionId = route.params?.sessionId
  const { showToast } = useLecturer()
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [part, setPart] = useState('questions')

  const load = useCallback(async () => {
    try {
      setSummary(await api.getInteractionSummary(sessionId))
      setError(null)
    } catch (e) { setError(e.message) }
  }, [sessionId])

  useEffect(() => { setSummary(null); setPart('questions'); load() }, [load])

  const exportCsv = async () => {
    setExporting(true)
    try {
      const msg = await api.exportInteractionCsv(sessionId, summaryCsvName(summary))
      if (msg) showToast(msg, 'success')
    } catch (e) { showToast(e.message ?? 'Export failed', 'error') } finally { setExporting(false) }
  }

  const st = interactionState(summary)
  const header = (
    <Topbar
      title="Interaction summary"
      sub={summary ? `${summary.course_code} · ${summary.class_date ?? ''}` : ''}
      onBack={() => navigation.goBack()}
      right={summary ? <Badge variant={st.ended ? 'gray' : st.variant} dot={st.open}>{st.ended ? 'Ended' : st.label}</Badge> : null}
    />
  )

  if (!summary) {
    return (
      <View style={styles.screen}>
        {header}
        <View style={styles.content}>
          {error ? <LoadError message={error} onRetry={load} testID="ix-summary-error" /> : <Loading text="Loading the summary…" />}
        </View>
      </View>
    )
  }

  const Part = PARTS[part] ?? QuestionsPart
  return (
    <View style={styles.screen}>
      {header}
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} tintColor={C.primary} colors={[C.primary]}
          onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false) }} />}
      >
        {error ? <LoadError message={error} onRetry={load} testID="ix-summary-error" /> : null}
        <View style={[ixStyles.row, styles.toolbar]}>
          <Text style={[styles.meta, styles.flex1]}>
            {summary.course_name}{st.ended ? '' : ' · class still running, numbers so far'}
          </Text>
          <Btn kind="primary" icon="download-outline" label="Export CSV" busy={exporting} onPress={exportCsv}
            testID="ix-summary-csv" />
        </View>
        <Pills items={summaryPills(summary)} value={part} onChange={setPart} />
        <Part summary={summary} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { padding: 16, paddingBottom: 32, width: '100%', maxWidth: 880, alignSelf: 'center' },
  toolbar: { marginBottom: 12 },
  gapBelow: { marginBottom: 8 },
  meta: { fontSize: 12, color: C.textSub, marginTop: 4 },
  answer: { borderTopWidth: 1, borderTopColor: C.border, paddingVertical: 8, marginTop: 4 },
  answerText: { fontSize: 13, color: C.text },
})
