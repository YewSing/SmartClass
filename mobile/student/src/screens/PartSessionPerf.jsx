import { useState, useEffect } from 'react'
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { getSessionPerf } from '../services/api'
import { C } from '../theme'

const PILL_STYLE = {
  correct:  { bg: C.greenLt, color: C.greenDk },
  wrong:    { bg: C.redLt,   color: C.redDk },
  'poll-ans': { bg: C.blueLt, color: C.primary },
  'no-answer': { bg: C.gray100, color: C.gray600 },
}

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const fmtDate = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
    + ' · ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function PartSessionPerf({ route, navigation }) {
  const interactionId = route.params?.interactionId ?? null
  const [perf, setPerf] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    if (interactionId == null) {
      setError('No session selected.')
      setLoading(false)
      return
    }
    getSessionPerf(interactionId)
      .then((data) => { if (alive) setPerf(data) })
      .catch((e) => { if (alive) setError(e.message ?? 'Failed to load session') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [interactionId])

  if (loading) {
    return (
      <View style={[styles.flex, styles.centered]}>
        <ActivityIndicator color={C.primary} />
        <Text style={styles.hintText}>Loading session…</Text>
      </View>
    )
  }

  if (error || !perf) {
    return (
      <View style={[styles.flex, styles.centered]}>
        <Topbar title="Session Summary" onBack={() => navigation.goBack()} />
        <Text style={styles.hintText}>{error ?? 'Session not found'}</Text>
      </View>
    )
  }

  const stats = perf.stats
  const heroStats = [
    ['votes', 'Poll Votes'],
    ['responses', 'Responses'],
    ['questions', 'Questions'],
    ['idu_signals', 'IDU'],
  ]
  const available = perf.polls.length + perf.live_questions.length
  const engaged = stats.votes + stats.responses
  const ratePct = available ? Math.round((engaged / available) * 100) : 0
  const rateColor = ratePct >= 60 ? C.green : ratePct > 0 ? C.orange : C.red

  // Real activity items, newest activity first per category then interleaved.
  const questions = [
    ...perf.polls.map((p) => ({
      key: `poll-${p.id}`,
      type: 'poll',
      typeLabel: 'Poll',
      meta: `Poll · ${fmtTime(p.my_option ? perf.opened_at : perf.opened_at)}`,
      question: p.question,
      answerPill: p.my_option
        ? { label: p.my_option, cls: 'poll-ans' }
        : { label: '— No vote', cls: 'no-answer' },
      timeBadge: p.is_open ? 'Poll open' : 'Poll closed',
      timeBadgeIcon: p.is_open ? 'flash' : 'time-outline',
      distribution: p.options,
    })),
    ...perf.live_questions.map((lq) => ({
      key: `live-${lq.id}`,
      type: 'quiz',
      typeLabel: 'Live Q',
      meta: `Live question · ${fmtTime(perf.opened_at)}`,
      question: lq.question,
      answerPill: lq.my_response
        ? { label: lq.my_response, cls: 'correct' }
        : { label: '— No response', cls: 'no-answer' },
      timeBadge: lq.my_response ? 'Responded' : 'Not answered',
      timeBadgeIcon: lq.my_response ? 'checkmark-circle' : 'close-circle',
    })),
    ...perf.my_questions.map((q) => ({
      key: `q-${q.id}`,
      type: 'quiz',
      typeLabel: 'Question',
      meta: `You asked${q.anonymous ? ' · anonymous' : ''}`,
      question: q.text,
      answerPill: { label: q.answered ? 'Answered' : 'Waiting', cls: q.answered ? 'correct' : 'no-answer' },
      timeBadge: null,
      timeBadgeIcon: null,
    })),
  ]

  return (
    <View style={styles.flex}>
      <Topbar title="Session Summary" onBack={() => navigation.goBack()} />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <Text style={styles.heroClass}>{perf.class_code} · {perf.class_name}</Text>
          <Text style={styles.heroTitle}>Interaction Session #{perf.id}</Text>
          <View style={styles.heroDateRow}>
            <Ionicons name="calendar-outline" size={11} color="#DBEAFE" />
            <Text style={styles.heroDate}>{fmtDate(perf.opened_at)}{perf.status === 'open' ? ' · Live' : ''}</Text>
          </View>
          <View style={styles.heroStats}>
            {heroStats.map(([k, l]) => (
              <View key={k} style={styles.heroStatChip}>
                <Text style={styles.heroStatNum}>{stats[k]}</Text>
                <Text style={styles.heroStatLbl}>{l}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Participation score card */}
        <View style={styles.scoreCard}>
          <Text style={styles.scoreTitle}>Your participation this session</Text>
          <View style={styles.scoreRow}>
            <Text style={[styles.scoreValue, { color: rateColor }]}>{ratePct}%</Text>
            <Text style={styles.classAvg}>{perf.class_participants} classmate{perf.class_participants === 1 ? '' : 's'} participated</Text>
          </View>
          <View style={styles.scoreTrack}>
            <View style={[styles.scoreFill, { width: `${ratePct}%`, backgroundColor: rateColor }]} />
          </View>
          <View style={styles.scoreAxis}>
            <Text style={styles.axisText}>0%</Text>
            <Text style={styles.axisText}>{engaged} of {available} items</Text>
            <Text style={styles.axisText}>100%</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Questions & Responses</Text>

        {questions.length === 0 && (
          <Text style={styles.hintText}>No activity recorded in this session.</Text>
        )}

        {questions.map((q) => {
          const pill = PILL_STYLE[q.answerPill.cls] ?? { bg: C.gray100, color: C.gray600 }
          return (
            <View key={q.key} style={styles.qRow}>
              <View style={styles.qTopRow}>
                <View style={[styles.typeChip, { backgroundColor: q.type === 'quiz' ? C.blueLt : C.purpleLt }]}>
                  <Ionicons
                    name={q.type === 'quiz' ? 'help-circle' : 'bar-chart'}
                    size={9}
                    color={q.type === 'quiz' ? C.primary : C.purple}
                  />
                  <Text style={[styles.typeChipText, { color: q.type === 'quiz' ? C.primary : C.purple }]}>
                    {q.typeLabel}
                  </Text>
                </View>
                <Text style={styles.qMeta}>{q.meta}</Text>
              </View>

              <Text style={styles.qText}>{q.question}</Text>

              <View style={styles.resultRow}>
                <View style={[styles.ansPill, { backgroundColor: pill.bg }]}>
                  <Text style={[styles.ansPillText, { color: pill.color }]}>{q.answerPill.label}</Text>
                </View>
                {q.distribution && (
                  <Text style={styles.timeBadgeText}>
                    {q.distribution.map((o) => `${o.option_text}: ${o.votes}`).join(' · ')}
                  </Text>
                )}
                {q.timeBadge && (
                  <View style={styles.timeBadge}>
                    {q.timeBadgeIcon && (
                      <Ionicons name={q.timeBadgeIcon} size={10} color={C.textSub} />
                    )}
                    <Text style={styles.timeBadgeText}>
                      {q.timeBadge}
                    </Text>
                  </View>
                )}
              </View>
            </View>
          )
        })}

        <View style={{ height: 28 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  centered: { alignItems: 'center', justifyContent: 'center', gap: 8 },
  hintText: { fontSize: 13, color: C.textSub, padding: 16 },
  hero: {
    backgroundColor: C.primary,
    padding: 18,
  },
  heroClass: {
    fontSize: 12,
    fontWeight: '600',
    color: '#DBEAFE',
  },
  heroTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#fff',
    marginTop: 2,
  },
  heroDateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 6,
  },
  heroDate: {
    fontSize: 12,
    color: '#DBEAFE',
  },
  heroStats: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 16,
  },
  heroStatChip: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 10,
    paddingVertical: 10,
  },
  heroStatNum: {
    fontSize: 18,
    fontWeight: '800',
    color: '#fff',
  },
  heroStatLbl: {
    fontSize: 9,
    color: '#DBEAFE',
    marginTop: 2,
    textAlign: 'center',
  },
  scoreCard: {
    backgroundColor: C.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    margin: 16,
    padding: 16,
  },
  scoreTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: C.textSub,
    marginBottom: 8,
  },
  scoreRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 8,
  },
  scoreValue: {
    fontSize: 26,
    fontWeight: '800',
  },
  classAvg: {
    fontSize: 12,
    color: C.textSub,
  },
  scoreTrack: {
    height: 8,
    borderRadius: 4,
    backgroundColor: C.gray100,
    overflow: 'hidden',
  },
  scoreFill: {
    height: 8,
    borderRadius: 4,
  },
  scoreAxis: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  axisText: {
    fontSize: 10,
    color: C.textHint,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
  },
  qRow: {
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 12,
  },
  qTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },
  typeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
  },
  typeChipText: {
    fontSize: 10,
    fontWeight: '700',
  },
  qMeta: {
    fontSize: 11,
    color: C.textHint,
  },
  qText: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
    lineHeight: 19,
    marginBottom: 8,
  },
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flexWrap: 'wrap',
  },
  ansPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  ansPillText: {
    fontSize: 11,
    fontWeight: '600',
  },
  timeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginLeft: 'auto',
  },
  timeBadgeText: {
    fontSize: 11,
    color: C.textSub,
  },
})
