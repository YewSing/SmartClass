import {
  View, Text, ScrollView, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { SESSION_PERFS } from '../data/mockData'
import { C } from '../theme'

const PILL_STYLE = {
  correct:     { bg: C.greenLt, color: C.greenDk },
  wrong:       { bg: C.redLt,   color: C.redDk },
  'poll-ans':  { bg: C.blueLt,  color: C.blueDk },
  'no-answer': { bg: C.gray100, color: C.gray500 },
}

const STAT_COLORS = {
  correct: C.green,
  wrong:   C.red,
  skipped: C.gray500,
  score:   C.primary,
}

export default function PartSessionPerf({ route, navigation }) {
  const perfKey = route.params?.perfKey ?? 'today'
  const perf = SESSION_PERFS[perfKey] ?? SESSION_PERFS.today

  return (
    <View style={styles.flex}>
      <Topbar title="Session Summary" onBack={() => navigation.goBack()} />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <Text style={styles.heroClass}>{perf.classLabel}</Text>
          <Text style={styles.heroTitle}>{perf.title}</Text>
          <View style={styles.heroDateRow}>
            <Ionicons name="calendar-outline" size={11} color="#DBEAFE" />
            <Text style={styles.heroDate}>{perf.date}</Text>
          </View>
          <View style={styles.heroStats}>
            {[['correct', 'Correct'], ['wrong', 'Wrong'], ['skipped', 'Skipped'], ['score', 'Score']].map(([k, l]) => (
              <View key={k} style={styles.heroStatChip}>
                <Text style={styles.heroStatNum}>{perf.stats[k]}</Text>
                <Text style={styles.heroStatLbl}>{l}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Score card */}
        <View style={styles.scoreCard}>
          <Text style={styles.scoreTitle}>Your score this session</Text>
          <View style={styles.scoreRow}>
            <Text style={[styles.scoreValue, { color: perf.scoreColor }]}>{perf.scoreValue}</Text>
            <Text style={styles.classAvg}>Class avg: {perf.classAvg}</Text>
          </View>
          <View style={styles.scoreTrack}>
            <View style={[styles.scoreFill, { width: perf.scoreWidth, backgroundColor: perf.scoreColor }]} />
          </View>
          <View style={styles.scoreAxis}>
            <Text style={styles.axisText}>0%</Text>
            <Text style={styles.axisText}>Class avg {perf.classAvg}</Text>
            <Text style={styles.axisText}>100%</Text>
          </View>
        </View>

        {perf.warning && (
          <View style={styles.warnBanner}>
            <Ionicons name="warning-outline" size={15} color={C.yellow} style={{ marginTop: 1 }} />
            <Text style={styles.warnText}>{perf.warning}</Text>
          </View>
        )}

        <Text style={styles.sectionTitle}>Questions & Responses</Text>

        {perf.questions.map((q, i) => {
          const pill = PILL_STYLE[q.answerPill.cls] ?? { bg: C.gray100, color: C.gray600 }
          return (
            <View key={i} style={styles.qRow}>
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
                {q.correctRef && (
                  <>
                    <Ionicons name="arrow-forward" size={10} color={C.gray400} />
                    <View style={[styles.ansPill, { backgroundColor: C.greenLt }]}>
                      <Text style={[styles.ansPillText, { color: C.greenDk }]}>{q.correctRef}</Text>
                    </View>
                  </>
                )}
                <View style={styles.timeBadge}>
                  {q.timeBadgeIcon && (
                    <Ionicons name={q.timeBadgeIcon} size={10} color={q.timeBadgeColor ?? C.textSub} />
                  )}
                  <Text style={[styles.timeBadgeText, q.timeBadgeColor && { color: q.timeBadgeColor }]}>
                    {q.timeBadge}
                  </Text>
                </View>
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
    fontSize: 10,
    color: '#DBEAFE',
    marginTop: 2,
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
  warnBanner: {
    flexDirection: 'row',
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 4,
    backgroundColor: C.yellowLt,
    borderWidth: 1,
    borderColor: C.yellow,
    borderRadius: 10,
    padding: 12,
  },
  warnText: {
    flex: 1,
    fontSize: 12,
    color: C.yellowDk,
    lineHeight: 18,
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
