import { useState } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { PART_SUMMARY, PARTICIPATION_GROUPS } from '../data/mockData'
import { C } from '../theme'

const PILL_STYLE = {
  correct:    { bg: C.greenLt,  color: C.greenDk },
  wrong:      { bg: C.redLt,    color: C.redDk },
  'poll-ans': { bg: C.blueLt,   color: C.blueDk },
}

function AnswerPill({ label, cls }) {
  if (!label) {
    return (
      <View style={[styles.ansPill, { backgroundColor: C.gray100, borderWidth: 1, borderColor: C.border }]}>
        <Text style={[styles.ansPillText, { color: C.gray500 }]}>— No answer</Text>
      </View>
    )
  }
  const s = PILL_STYLE[cls] ?? { bg: C.gray100, color: C.gray600 }
  return (
    <View style={[styles.ansPill, { backgroundColor: s.bg }]}>
      <Text style={[styles.ansPillText, { color: s.color }]}>{label}</Text>
    </View>
  )
}

export default function Participation({ navigation }) {
  const insets = useSafeAreaInsets()
  const [collapsed, setCollapsed] = useState({})
  const [activeFilter, setActiveFilter] = useState('All Classes')

  const toggleGroup = (id) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))

  const filters = ['All Classes', ...[...new Set(
    PARTICIPATION_GROUPS.map(g => {
      const parts = g.label.split(' — ')
      return parts.length > 1 ? parts[1].split(' · ')[0] : g.label.split(' · ')[0]
    })
  )]]
  const visibleGroups = activeFilter === 'All Classes'
    ? PARTICIPATION_GROUPS
    : PARTICIPATION_GROUPS.filter(g => g.label.includes(activeFilter))

  return (
    <View style={styles.flex}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <Text style={styles.headerTitle}>My Participation</Text>
        <Text style={styles.headerSub}>Quiz & poll history · All classes</Text>
      </View>

      {/* Summary row */}
      <View style={styles.summaryBar}>
        <View style={styles.statChip}>
          <Text style={[styles.statNum, { color: C.green }]}>{PART_SUMMARY.correct}</Text>
          <Text style={styles.statLbl}>Correct</Text>
        </View>
        <View style={styles.statChip}>
          <Text style={[styles.statNum, { color: C.red }]}>{PART_SUMMARY.wrong}</Text>
          <Text style={styles.statLbl}>Wrong</Text>
        </View>
        <View style={styles.statChip}>
          <Text style={[styles.statNum, { color: C.gray500 }]}>{PART_SUMMARY.skipped}</Text>
          <Text style={styles.statLbl}>Skipped</Text>
        </View>
        <View style={styles.statChip}>
          <Text style={[styles.statNum, { color: C.primary }]}>{PART_SUMMARY.score}</Text>
          <Text style={styles.statLbl}>Score</Text>
        </View>
      </View>

      {/* Filter pills */}
      <View style={styles.filterRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterContent}>
          {filters.map(f => (
            <TouchableOpacity
              key={f}
              style={[styles.pill, activeFilter === f && styles.pillActive]}
              onPress={() => setActiveFilter(f)}
            >
              <Text style={[styles.pillText, activeFilter === f && styles.pillTextActive]}>{f}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {visibleGroups.map(group => (
          <View key={group.id}>
            <View style={styles.groupHeader}>
              <TouchableOpacity style={styles.groupLabelWrap} onPress={() => toggleGroup(group.id)}>
                <Text style={styles.groupLabel}>{group.label}</Text>
                <Ionicons
                  name={collapsed[group.id] ? 'chevron-forward' : 'chevron-down'}
                  size={12}
                  color={C.textSub}
                />
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.summaryBtn}
                onPress={() => navigation.navigate('PartSessionPerf', { perfKey: group.perfKey })}
              >
                <Ionicons name="bar-chart-outline" size={12} color={C.primary} />
                <Text style={styles.summaryBtnText}>Summary</Text>
              </TouchableOpacity>
            </View>

            {!collapsed[group.id] && group.items.map(item => (
              <View key={item.id} style={styles.responseRow}>
                <View style={[styles.typeChip, { backgroundColor: item.type === 'quiz' ? C.blueLt : C.purpleLt }]}>
                  <Ionicons
                    name={item.type === 'quiz' ? 'help-circle' : 'bar-chart'}
                    size={9}
                    color={item.type === 'quiz' ? C.primary : C.purple}
                  />
                  <Text style={[styles.typeChipText, { color: item.type === 'quiz' ? C.primary : C.purple }]}>
                    {item.typeLabel}
                  </Text>
                </View>

                <Text style={styles.question}>{item.question}</Text>

                <View style={styles.answerRow}>
                  <AnswerPill label={item.myAnswer} cls={item.myAnswerClass} />
                  {item.correctAnswer && item.type === 'quiz' && (
                    <>
                      <Ionicons name="arrow-forward" size={11} color={C.gray400} />
                      <View style={[styles.ansPill, { backgroundColor: C.greenLt }]}>
                        <Text style={[styles.ansPillText, { color: C.greenDk }]}>{item.correctAnswer}</Text>
                      </View>
                    </>
                  )}
                  {item.resultIcon && (
                    <Ionicons name={item.resultIcon} size={16} color={item.resultColor} style={{ marginLeft: 'auto' }} />
                  )}
                </View>

                {item.type === 'poll' && item.pollBars && (
                  <View style={styles.pollBars}>
                    {item.pollBars.map(bar => (
                      <View key={bar.opt} style={styles.pollBarRow}>
                        <Text style={styles.pollBarOpt}>{bar.opt}</Text>
                        <View style={styles.pollBarTrack}>
                          <View style={[
                            styles.pollBarFill,
                            { width: `${bar.pct}%`, backgroundColor: bar.isMyChoice ? C.primary : C.gray300 },
                          ]} />
                        </View>
                        <Text style={[styles.pollBarPct, bar.isMyChoice && { color: C.primary, fontWeight: '700' }]}>
                          {bar.pct}%
                        </Text>
                      </View>
                    ))}
                  </View>
                )}

                <View style={styles.metaRow}>
                  <Ionicons name="time-outline" size={10} color={item.metaColor ?? C.textHint} />
                  <Text style={[styles.metaText, item.metaColor && { color: item.metaColor }]}>{item.meta}</Text>
                </View>
              </View>
            ))}
          </View>
        ))}
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  header: {
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    paddingHorizontal: 16,
    paddingBottom: 10,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: C.text,
  },
  headerSub: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 2,
  },
  summaryBar: {
    flexDirection: 'row',
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  statChip: {
    flex: 1,
    alignItems: 'center',
  },
  statNum: {
    fontSize: 20,
    fontWeight: '800',
  },
  statLbl: {
    fontSize: 11,
    color: C.textSub,
    marginTop: 2,
  },
  filterRow: {
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  filterContent: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.bg,
  },
  pillActive: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  pillText: {
    fontSize: 12,
    fontWeight: '600',
    color: C.textSub,
  },
  pillTextActive: {
    color: '#fff',
  },
  groupHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  groupLabelWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flex: 1,
  },
  groupLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
  },
  summaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: C.blueLt,
  },
  summaryBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: C.primary,
  },
  responseRow: {
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 12,
  },
  typeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    alignSelf: 'flex-start',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
    marginBottom: 8,
  },
  typeChipText: {
    fontSize: 10,
    fontWeight: '700',
  },
  question: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
    lineHeight: 19,
    marginBottom: 8,
  },
  answerRow: {
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
  pollBars: {
    marginTop: 8,
    gap: 4,
  },
  pollBarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  pollBarOpt: {
    width: 14,
    fontSize: 11,
    fontWeight: '700',
    color: C.textSub,
  },
  pollBarTrack: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    backgroundColor: C.gray100,
    overflow: 'hidden',
  },
  pollBarFill: {
    height: 6,
    borderRadius: 3,
  },
  pollBarPct: {
    width: 34,
    fontSize: 11,
    color: C.textSub,
    textAlign: 'right',
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 8,
  },
  metaText: {
    fontSize: 11,
    color: C.textHint,
  },
})
