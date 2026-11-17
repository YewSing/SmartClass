import { useState, useEffect, useCallback, useRef } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl, ActivityIndicator, Modal, FlatList,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  getInteraction, getPolls, getLiveQuestion, getQuestions, getReactions, getIduCount,
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

export default function InteractionDetail({ route, navigation }) {
  const { showToast } = useLecturer()
  const insets = useSafeAreaInsets()
  const wsRef = useRef(null)
  const reloadTimer = useRef(null)

  const interactionId = route.params?.interactionId
  const occurrenceId = route.params?.occurrence_id

  const [interaction, setInteraction] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const [polls, setPolls] = useState([])
  const [liveQuestion, setLiveQuestion] = useState(null)
  const [questions, setQuestions] = useState([])
  const [reactionCounts, setReactionCounts] = useState({})
  const [iduCount, setIDUCount] = useState(0)

  const isOpen = interaction ? interaction.status === 'open' : true

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        const found = await getInteraction(interactionId)
        if (!cancelled) setInteraction(found)
        await loadLive()
      } catch (e) {
        if (!cancelled) showToast(e.message, 'error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [interactionId, showToast])

  const loadLive = useCallback(async () => {
    if (!interactionId) return
    const results = await Promise.allSettled([
      getPolls(interactionId), getLiveQuestion(interactionId), getQuestions(interactionId),
      getReactions(interactionId), getIduCount(interactionId),
    ])
    const value = (i) => (results[i].status === 'fulfilled' ? results[i].value : null)
    setPolls(value(0) ?? [])
    setLiveQuestion(value(1))
    setQuestions(value(2) ?? [])
    const counts = {}
    ;(value(3) ?? []).forEach(r => { counts[r.reaction] = r.count })
    setReactionCounts(counts)
    setIDUCount(value(4)?.distinct_students ?? 0)
  }, [interactionId, showToast])

  const scheduleReload = useCallback(() => {
    clearTimeout(reloadTimer.current)
    reloadTimer.current = setTimeout(() => loadLive(), 250)
  }, [loadLive])

  useEffect(() => {
    wsRef.current?.close()
    wsRef.current = null
    if (!interactionId) return
    loadLive()
    const ws = connectInteractionLive({
      interactionId,
      baseUrl: null,
      getToken: () => null,
      refreshToken: () => Promise.resolve(false),
      onEvent: () => scheduleReload(),
    })
    wsRef.current = ws
    return () => {
      clearTimeout(reloadTimer.current)
      ws.close()
    }
  }, [interactionId, loadLive, scheduleReload])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadLive()
    setRefreshing(false)
  }, [loadLive])

  const openQuestions = questions.filter(q => !q.answered)
  const answeredQuestions = questions.filter(q => q.answered)
  const sortedQuestions = [...openQuestions, ...answeredQuestions]
  const totalResponses = liveQuestion?.responses?.length ?? 0
  const totalReactions = Object.values(reactionCounts).reduce((s, v) => s + (v ?? 0), 0)
  const topReaction = REACTIONS.reduce(
    (best, r) => ((reactionCounts[r] ?? 0) > (reactionCounts[best] ?? 0) ? r : best), null,
  )

  const summaryItems = [
    { icon: 'chatbubbles', label: 'Questions asked', value: questions.length },
    { icon: 'checkmark', label: 'Answered', value: answeredQuestions.length },
    { icon: 'create-outline', label: 'Polls', value: polls.length },
    { icon: 'hand-left-outline', label: "Don't understand", value: iduCount },
    { icon: 'heart', label: 'Reactions', value: totalReactions },
  ]

  if (loading) {
    return (
      <View style={styles.flex}>
        <Topbar title="Interaction" onBack={() => navigation.goBack()} />
        <View style={styles.center}><ActivityIndicator color={C.primary} /></View>
      </View>
    )
  }

  const sub = interaction
    ? `${interaction.class_code} · ${isOpen ? 'Open' : 'Closed'}`
    : ''

  return (
    <View style={styles.flex}>
      <Topbar
        title={interaction ? `${interaction.class_code} — ${interaction.class_name}` : 'Interaction'}
        sub={sub}
        onBack={() => navigation.goBack()}
      />
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} />}
        contentContainerStyle={styles.content}
      >
        {/* Header — summary for ended sessions, live pulse for open ones */}
        {isOpen ? (
          <Section tint="yellow" badge="Live status" style={styles.sectionTight}>
            <View style={styles.pulseRow}>
              <View style={[styles.pulseTile, { backgroundColor: C.orangeLt }]}>
                <Ionicons name="hand-left-outline" size={15} color={C.orangeDk} />
                <Text style={[styles.pulseNum, { color: C.orangeDk }]}>{iduCount}</Text>
                <Text style={[styles.pulseLabel, { color: C.orangeDk }]}>don't understand</Text>
              </View>
              <View style={[styles.pulseTile, { backgroundColor: C.blueLt }]}>
                <Ionicons name="chatbubbles" size={15} color={C.blueDk} />
                <Text style={[styles.pulseNum, { color: C.blueDk }]}>{openQuestions.length}</Text>
                <Text style={[styles.pulseLabel, { color: C.blueDk }]}>open question{openQuestions.length !== 1 ? 's' : ''}</Text>
              </View>
              <View style={[styles.pulseTile, { backgroundColor: C.greenLt }]}>
                <Ionicons
                  name={topReaction ? REACTION_ICON[topReaction] : 'happy-outline'}
                  size={15} color={C.greenDk}
                />
                <Text style={[styles.pulseNum, { color: C.greenDk }]}>
                  {topReaction ? (reactionCounts[topReaction] ?? 0) : totalReactions}
                </Text>
                <Text style={[styles.pulseLabel, { color: C.greenDk }]}>
                  {topReaction ? REACTION_LABEL[topReaction].toLowerCase() : 'reactions'}
                </Text>
              </View>
            </View>
            <View style={styles.reactionsRow}>
              {REACTIONS.map(r => (
                <View key={r} style={[styles.reactionChip, (reactionCounts[r] ?? 0) > 0 && styles.reactionChipActive]}>
                  <Ionicons name={REACTION_ICON[r]} size={14} color={C.textSub} />
                  <Text style={styles.reactionLabel}>{REACTION_LABEL[r]}</Text>
                  <Text style={styles.reactionCount}>{reactionCounts[r] ?? 0}</Text>
                </View>
              ))}
            </View>
          </Section>
        ) : (
          <Section tint="gray" badge="Session summary" style={styles.sectionTight}>
        {summaryItems.length > 0 ? (
          <View style={styles.summaryRow}>
            {summaryItems.map(item => (
              <View key={item.label} style={styles.summaryItem}>
                <Ionicons name={item.icon} size={15} color={C.primary} />
                <View style={styles.summaryText}>
                  <Text style={styles.summaryValue}>{item.value}</Text>
                  <Text style={styles.summaryLabel}>{item.label}</Text>
                </View>
              </View>
            ))}
          </View>
        ) : null}
      </Section>
        )}

        {/* Student questions */}
        <Section tint="gray" badge="Student questions" right={<Badge variant="gray" dot>{openQuestions.length} open</Badge>}>
          {sortedQuestions.length > 0 ? (
            sortedQuestions.map(q => (
              <View key={q.id} style={[styles.questionItem, q.answered ? styles.questionItemAnswered : styles.questionItemOpen]}>
                <Text style={styles.questionText}>{q.text}</Text>
                <View style={styles.questionMeta}>
                  {q.anonymous ? (
                    <View style={styles.anonPill}>
                      <Ionicons name="eye-off-outline" size={10} color={C.gray600} />
                      <Text style={styles.anonPillText}>Anonymous</Text>
                    </View>
                  ) : (
                    <Text style={styles.questionAuthorName}>{q.student_name ?? 'Student'}</Text>
                  )}
                  <Text style={[styles.questionMetaText, q.answered && styles.questionMetaAnswered]}>
                    {q.answered ? 'Answered' : 'Needs an answer'}
                  </Text>
                </View>
              </View>
            ))
          ) : (
            <Text style={styles.emptyLine}>No questions yet.</Text>
          )}
        </Section>

        {/* Live question */}
        <Section tint="purple" badge="Live question">
          {liveQuestion ? (
            <>
              <Text style={styles.liveQuestionText}>{liveQuestion.question}</Text>
              <View style={styles.sectionHead}>
                <Text style={styles.responsesTitle}>{totalResponses} response{totalResponses === 1 ? '' : 's'}</Text>
              </View>
              {liveQuestion.responses?.length > 0 && (
                liveQuestion.responses.map(r => (
                  <View key={r.id} style={styles.responseItem}>
                    <Text style={styles.responseText}>{r.response}</Text>
                  </View>
                ))
              )}
            </>
          ) : (
            <Text style={styles.emptyLine}>Nothing asked to the class yet.</Text>
          )}
        </Section>

        {/* Polls */}
        <Section tint="blue" badge="Polls">
          {polls.length > 0 ? (
            polls.map(p => {
              const total = p.options.reduce((s, o2) => s + (o2.votes ?? 0), 0)
              return (
                <View key={p.id} style={styles.pollCard}>
                  <View style={styles.pollHead}>
                    <Text style={styles.pollQuestion}>{p.question}</Text>
                    <Badge variant="gray" dot>{p.is_open ? 'Open' : 'Closed'}</Badge>
                  </View>
                  {p.options.map(o => {
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
                </View>
              )
            })
          ) : (
            <Text style={styles.emptyLine}>No polls yet.</Text>
          )}
        </Section>

        <View style={{ height: 24 }} />
      </ScrollView>

      <View style={{ height: insets.bottom }} />
    </View>
  )

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
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  flex1: { flex: 1 },
  content: { paddingHorizontal: 16, paddingBottom: 24 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyLine: { fontSize: 13, color: C.textHint, marginTop: 4, marginBottom: 4 },
  section: {
    borderRadius: 14, marginHorizontal: 16, marginTop: 12, padding: 14,
    backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
  },
  sectionTight: { marginTop: 12 },
  sectionBadge: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  sectionBadgeText: { fontSize: 10, fontWeight: '800' },
  sectionHead: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8,
  },
  summaryRow: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'space-between',
  },
  summaryItem: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.gray50, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 10, flex: 1, minWidth: 90,
  },
  summaryValue: { fontSize: 16, fontWeight: '800', color: C.text },
  summaryLabel: { fontSize: 11, color: C.textSub },
  pulseRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  pulseTile: {
    flex: 1, borderRadius: 10, alignItems: 'center', paddingVertical: 10, paddingHorizontal: 4, gap: 2,
  },
  pulseNum: { fontSize: 20, fontWeight: '800' },
  pulseLabel: { fontSize: 10, fontWeight: '600', textAlign: 'center' },
  reactionsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  reactionChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: C.gray100,
    borderRadius: 20, paddingHorizontal: 10, paddingVertical: 6,
  },
  reactionChipActive: { backgroundColor: C.blueLt, borderWidth: 1, borderColor: C.primary },
  reactionLabel: { fontSize: 11, color: C.textSub },
  reactionCount: { fontSize: 12, fontWeight: '700', color: C.primary },
  questionItem: { borderRadius: 10, padding: 10, marginBottom: 6, borderWidth: 1, borderColor: 'transparent' },
  questionItemOpen: { backgroundColor: C.blueLt, borderColor: C.primary },
  questionItemAnswered: { backgroundColor: C.gray50, borderColor: C.gray300, opacity: 0.85 },
  questionText: { fontSize: 14, color: C.text, fontWeight: '500' },
  anonPill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: C.card, borderRadius: 8, paddingHorizontal: 6, paddingVertical: 3 },
  anonPillText: { fontSize: 10, fontWeight: '700', color: C.gray600 },
  questionMeta: { flexDirection: 'row', gap: 8, marginTop: 6, alignItems: 'center', flexWrap: 'wrap' },
  questionMetaText: { fontSize: 11, color: C.textHint },
  questionMetaAnswered: { color: C.green, fontWeight: '700' },
  questionAuthorName: { fontSize: 12, fontWeight: '700', color: C.blueDk, flexShrink: 1 },
  liveQuestionText: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 8 },
  responsesTitle: { fontSize: 12, fontWeight: '700', color: C.textSub },
  responseItem: { paddingVertical: 8, backgroundColor: C.gray50, borderRadius: 8, marginBottom: 4, paddingHorizontal: 10 },
  responseText: { fontSize: 13, color: C.text },
  pollCard: { marginBottom: 10 },
  pollHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  pollQuestion: { fontSize: 14, fontWeight: '600', color: C.text, flexShrink: 1 },
  barCol: { marginBottom: 10 },
  barRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  barOptLabel: { fontSize: 13, color: C.text },
  barOptPct: { fontSize: 13, fontWeight: '700', color: C.primary },
  barTrack: { height: 8, backgroundColor: C.gray100, borderRadius: 4, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: C.primary, borderRadius: 4 },
  barCount: { fontSize: 12, color: C.textSub, marginTop: 2 },
})
