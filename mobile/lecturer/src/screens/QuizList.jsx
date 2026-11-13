// Module 6 — assessment hub for lecturers.
// Tabs: Published quizzes (FR-605/606 view) · Grading (FR-609/610) ·
// Results (FR-612/613 with class average and frequently-missed questions).
// Frontend-only with module2 mock fixtures and local state.
import { useState } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { ASSESSMENT_ACTIVITY, SHORT_ANSWERS, QUIZ_RESULTS } from '../data/module2'
import { C } from '../theme'

const TABS = [['published', 'Published'], ['grading', 'Grading'], ['results', 'Results']]

function MiniBars({ values, color = C.primary }) {
  const max = Math.max(...values, 1)
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 3, height: 64, marginTop: 8 }}>
      {values.map((v, i) => (
        <View key={i} style={{ flex: 1, justifyContent: 'flex-end' }}>
          <View style={{ height: Math.max(4, Math.round((v / max) * 56)), backgroundColor: color, borderRadius: 3 }} />
          <Text style={{ fontSize: 8, color: C.textHint, textAlign: 'center', marginTop: 2 }}>{i + 1}</Text>
        </View>
      ))}
    </View>
  )
}

export default function QuizList({ navigation }) {
  const [tab, setTab] = useState('published')
  const [scores, setScores] = useState({})       // FR-609 accepted/edited scores

  const pending = SHORT_ANSWERS.length
  return (
    <View style={styles.flex}>
      <Topbar
        title="Assessments"
        sub="AI-generated quizzes & grading"
        right={
          <TouchableOpacity style={styles.createBtn} onPress={() => navigation.navigate('CreateQuiz')}>
            <Ionicons name="sparkles" size={14} color="#fff" />
            <Text style={styles.createBtnText}>Generate</Text>
          </TouchableOpacity>
        }
      />

      <View style={styles.tabsRow}>
        {TABS.map(([id, label]) => (
          <TouchableOpacity
            key={id}
            style={[styles.tab, tab === id && styles.tabActive]}
            onPress={() => setTab(id)}
          >
            <Text style={[styles.tabText, tab === id && styles.tabTextActive]}>{label}</Text>
            {id === 'grading' && pending > 0 && (
              <View style={styles.tabBadge}><Text style={styles.tabBadgeText}>{pending}</Text></View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>

        {/* ── Published ── */}
        {tab === 'published' && ASSESSMENT_ACTIVITY.map(a => (
          <View key={a.id} style={styles.card}>
            <View style={styles.cardTop}>
              <View style={styles.courseTag}><Text style={styles.courseTagText}>{a.course}</Text></View>
              <Badge variant={a.status === 'open' ? 'green' : a.status === 'needs-grading' ? 'orange' : 'gray'}>
                {a.status === 'open' ? 'Open' : a.status === 'needs-grading' ? 'Needs grading' : 'Closed'}
              </Badge>
            </View>
            <Text style={styles.cardTitle}>{a.title}</Text>
            <Text style={styles.cardMeta}>{a.meta}</Text>
            {a.status === 'open' && (
              <>
                <View style={styles.subRow}>
                  <Text style={styles.subLbl}>{a.submitted}/{a.enrolled} submitted</Text>
                  <Text style={styles.subDue}>closes {a.closes}</Text>
                </View>
                <View style={styles.track}>
                  <View style={[styles.fill, { width: `${Math.round((a.submitted / a.enrolled) * 100)}%` }]} />
                </View>
              </>
            )}
            {a.status === 'needs-grading' && (
              <TouchableOpacity style={styles.gradeLink} onPress={() => setTab('grading')}>
                <Ionicons name="pencil" size={13} color={C.orangeDk} />
                <Text style={styles.gradeLinkText}>{a.meta2 ?? 'Short answers await scoring'}</Text>
                <Ionicons name="chevron-forward" size={13} color={C.orangeDk} />
              </TouchableOpacity>
            )}
            {a.status === 'closed' && (
              <View style={styles.avgRow}>
                <Ionicons name="stats-chart" size={13} color={C.green} />
                <Text style={styles.avgText}>Class average included in {a.meta}</Text>
              </View>
            )}
          </View>
        ))}

        {/* ── Grading (FR-609/610) ── */}
        {tab === 'grading' && (
          <>
            <View style={styles.infoBanner}>
              <Ionicons name="sparkles" size={14} color={C.primary} />
              <Text style={styles.infoText}>
                AI suggests a score for each short-answer response. Accept it or type your own (FR-610).
              </Text>
            </View>
            {SHORT_ANSWERS.map(sa => {
              const val = scores[sa.id] ?? sa.aiScore
              return (
                <View key={sa.id} style={styles.card}>
                  <View style={styles.cardTop}>
                    <Text style={styles.cardTitle} numberOfLines={1}>{sa.student}</Text>
                    <Badge variant="yellow">Awaiting score</Badge>
                  </View>
                  <Text style={styles.qPrompt}>{sa.question}</Text>
                  <View style={styles.responseText}>
                    <Text style={styles.responseTextBody}>“{sa.response}”</Text>
                  </View>
                  <View style={styles.aiScoreRow}>
                    <Ionicons name="sparkles" size={12} color={C.primary} />
                    <Text style={styles.aiScoreText}>AI suggested {sa.aiScore}/{sa.aiMax} — {sa.aiNote}</Text>
                  </View>
                  <View style={styles.scoreRow}>
                    <TouchableOpacity style={styles.scoreStepper} onPress={() => setScores(s => ({ ...s, [sa.id]: Math.max(0, val - 1) }))}>
                      <Ionicons name="remove" size={16} color={C.text} />
                    </TouchableOpacity>
                    <View style={styles.scoreBox}>
                      <Text style={styles.scoreVal}>{val}</Text>
                      <Text style={styles.scoreMax}>/{sa.aiMax}</Text>
                    </View>
                    <TouchableOpacity style={styles.scoreStepper} onPress={() => setScores(s => ({ ...s, [sa.id]: Math.min(sa.aiMax, val + 1) }))}>
                      <Ionicons name="add" size={16} color={C.text} />
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.acceptBtn, scores[sa.id] != null && scores[sa.id] !== sa.aiScore && styles.acceptEdited]}
                      onPress={() => setScores(s => ({ ...s, [sa.id]: sa.aiScore }))}
                    >
                      <Text style={styles.acceptBtnText}>
                        {scores[sa.id] != null && scores[sa.id] !== sa.aiScore ? 'Save my score' : 'Accept AI score'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )
            })}
          </>
        )}

        {/* ── Results (FR-612/613) ── */}
        {tab === 'results' && (
          <>
            <View style={styles.resultHero}>
              <Text style={styles.heroCourse}>{QUIZ_RESULTS.course} · {QUIZ_RESULTS.title}</Text>
              <View style={styles.heroStatsRow}>
                <View style={styles.heroStat}>
                  <Text style={styles.heroNum}>{QUIZ_RESULTS.avg}%</Text>
                  <Text style={styles.heroLbl}>Class average</Text>
                </View>
                <View style={styles.heroStat}>
                  <Text style={styles.heroNum}>{QUIZ_RESULTS.submitted}/{QUIZ_RESULTS.enrolled}</Text>
                  <Text style={styles.heroLbl}>Submitted</Text>
                </View>
                <View style={styles.heroStat}>
                  <Text style={styles.heroNum}>{QUIZ_RESULTS.highest}%</Text>
                  <Text style={styles.heroLbl}>Highest</Text>
                </View>
              </View>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>Score distribution</Text>
              <MiniBars values={QUIZ_RESULTS.grades} />
              <View style={styles.axisRow}>
                <Text style={styles.axisText}>Lowest {QUIZ_RESULTS.lowest}%</Text>
                <Text style={styles.axisText}>student #1 → #{QUIZ_RESULTS.grades.length}</Text>
              </View>
            </View>

            {/* FR-613 — frequently missed */}
            <View style={[styles.card, styles.missCard]}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>Frequently missed (&gt;50% wrong)</Text>
                <Ionicons name="alert-circle" size={15} color={C.red} />
              </View>
              {QUIZ_RESULTS.frequentlyMissed.map((q, i) => (
                <View key={i} style={styles.missRow}>
                  <View style={styles.missPct}>
                    <Text style={styles.missPctText}>{q.wrongPct}%</Text>
                    <Text style={styles.missPctLbl}>wrong</Text>
                  </View>
                  <View style={styles.missBody}>
                    <Text style={styles.missQ}>{q.text}</Text>
                    <View style={styles.tagRow}>
                      <View style={styles.tagChip}>
                        <Ionicons name="pricetag" size={9} color={C.purple} />
                        <Text style={styles.tagChipText}>{q.topic}</Text>
                      </View>
                      <View style={[styles.tagChip, { backgroundColor: C.blueLt }]}>
                        <Ionicons name="document" size={9} color={C.primary} />
                        <Text style={[styles.tagChipText, { color: C.primary }]}>{q.source}</Text>
                      </View>
                    </View>
                  </View>
                </View>
              ))}
              <Text style={styles.missNote}>
                These topics and questions are shared with the AI Learning Assistant (FR-614 / FR-824) so it can point students to the right material.
              </Text>
            </View>
          </>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  createBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: C.primary, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6,
  },
  createBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  tabsRow: {
    flexDirection: 'row', backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  tab: {
    flex: 1, paddingVertical: 12, alignItems: 'center',
    flexDirection: 'row', justifyContent: 'center', gap: 5,
    borderBottomWidth: 2, borderBottomColor: 'transparent',
  },
  tabActive: { borderBottomColor: C.primary },
  tabText: { fontSize: 14, fontWeight: '600', color: C.textSub },
  tabTextActive: { color: C.primary },
  tabBadge: {
    backgroundColor: C.red, minWidth: 16, height: 16, borderRadius: 8,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4,
  },
  tabBadgeText: { fontSize: 9, fontWeight: '800', color: '#fff' },
  card: {
    backgroundColor: C.card, marginHorizontal: 16, marginTop: 10,
    borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  cardTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  courseTag: { backgroundColor: C.blueLt, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6 },
  courseTagText: { fontSize: 10, fontWeight: '800', color: C.primary },
  cardTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  cardMeta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  subRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  subLbl: { fontSize: 12, fontWeight: '700', color: C.text },
  subDue: { fontSize: 11, color: C.textHint },
  track: { height: 6, borderRadius: 3, backgroundColor: C.gray100, overflow: 'hidden', marginTop: 6 },
  fill: { height: 6, backgroundColor: C.primary },
  gradeLink: {
    flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 12,
    backgroundColor: C.orangeLt, borderRadius: 9, paddingHorizontal: 10, paddingVertical: 9,
  },
  gradeLinkText: { flex: 1, fontSize: 12, fontWeight: '700', color: C.orangeDk },
  avgRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 12 },
  avgText: { fontSize: 12, color: C.greenDk, fontWeight: '600' },
  infoBanner: {
    flexDirection: 'row', gap: 8, marginHorizontal: 16, marginTop: 12,
    backgroundColor: C.blueLt, borderWidth: 1, borderColor: C.primary,
    borderRadius: 10, padding: 10, alignItems: 'flex-start',
  },
  infoText: { flex: 1, fontSize: 12, color: C.blueDk, lineHeight: 17 },
  qPrompt: { fontSize: 12, color: C.textSub, marginTop: 2, marginBottom: 8, lineHeight: 17 },
  responseText: {
    backgroundColor: C.gray50, borderWidth: 1, borderColor: C.border, borderRadius: 9, padding: 10,
  },
  responseTextBody: { fontSize: 12, color: C.text, lineHeight: 18, fontStyle: 'italic' },
  aiScoreRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 },
  aiScoreText: { flex: 1, fontSize: 11, color: C.textSub },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 },
  scoreStepper: {
    width: 34, height: 34, borderRadius: 9, borderWidth: 1.5, borderColor: C.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.bg,
  },
  scoreBox: {
    alignItems: 'center', backgroundColor: C.blueLt,
    borderRadius: 9, paddingHorizontal: 12, paddingVertical: 5,
  },
  scoreVal: { fontSize: 17, fontWeight: '800', color: C.primary },
  scoreMax: { fontSize: 10, color: C.textSub },
  acceptBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 9, borderRadius: 9, backgroundColor: C.green,
  },
  acceptEdited: { backgroundColor: C.primary },
  acceptBtnText: { fontSize: 12, fontWeight: '700', color: '#fff' },
  resultHero: {
    backgroundColor: C.primary, margin: 16, marginBottom: 4, borderRadius: 14, padding: 16,
  },
  heroCourse: { fontSize: 13, fontWeight: '700', color: '#DBEAFE' },
  heroStatsRow: { flexDirection: 'row', marginTop: 12, gap: 8 },
  heroStat: {
    flex: 1, alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 10, paddingVertical: 10,
  },
  heroNum: { fontSize: 17, fontWeight: '800', color: '#fff' },
  heroLbl: { fontSize: 10, color: '#BFDBFE', marginTop: 2 },
  axisRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 2 },
  axisText: { fontSize: 10, color: C.textHint },
  missCard: { borderColor: C.red },
  missRow: { flexDirection: 'row', gap: 10, borderTopWidth: 1, borderTopColor: C.border, paddingTop: 10, marginTop: 8 },
  missPct: { alignItems: 'center', backgroundColor: C.redLt, borderRadius: 9, padding: 7, minWidth: 52 },
  missPctText: { fontSize: 15, fontWeight: '800', color: C.red },
  missPctLbl: { fontSize: 9, color: C.redDk },
  missBody: { flex: 1 },
  missQ: { fontSize: 13, fontWeight: '600', color: C.text, lineHeight: 18, marginBottom: 6 },
  tagRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  tagChip: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: C.purpleLt, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6,
  },
  tagChipText: { fontSize: 9, fontWeight: '700', color: C.purple },
  missNote: { fontSize: 11, color: C.textHint, lineHeight: 16, marginTop: 10 },
})
