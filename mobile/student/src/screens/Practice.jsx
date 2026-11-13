// Full-screen practice from a chat message (FR-811): one question at a time, then a score that
// is saved on the message ("Last score 4 / 5"). Not graded: nothing goes to the lecturer.
import { useState } from 'react'
import { View, Text, TouchableOpacity, ScrollView, StyleSheet } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import { savePracticeScore } from '../services/api'
import { countCorrect } from '../services/assistantView'
import { openAtLabel } from '../services/openSource'
import { C } from '../theme'

export default function Practice({ route, navigation }) {
  const { messageId, questions = [], topic, courseCode } = route.params
  const { showToast } = useStudent()
  const insets = useSafeAreaInsets()
  const [i, setI] = useState(0)
  const [picks, setPicks] = useState({})        // question index -> option index
  const [done, setDone] = useState(false)
  const q = questions[i]
  const picked = picks[i]
  const answered = picked !== undefined
  const correct = countCorrect(questions, picks)

  const finish = async () => {
    setDone(true)
    try {
      await savePracticeScore(messageId, countCorrect(questions, picks), questions.length)
    } catch (e) {
      showToast(e.message, 'error')
    }
  }

  const restart = () => {
    setPicks({})
    setI(0)
    setDone(false)
  }

  if (done) {
    return (
      <View style={[styles.screen, styles.center, { paddingTop: insets.top }]}>
        <Ionicons name="trophy-outline" size={44} color={C.primary} />
        <Text style={styles.scoreBig} testID="practice-score">{correct} / {questions.length}</Text>
        <Text style={styles.scoreText}>
          {correct === questions.length ? 'All correct.' : 'Go through the explanations, then try again.'}
        </Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={restart} testID="practice-again">
          <Text style={styles.primaryText}>Try again</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryBtn} onPress={() => navigation.goBack()} testID="practice-back">
          <Text style={styles.secondaryText}>Back to chat</Text>
        </TouchableOpacity>
      </View>
    )
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + 6 }]}>
      <View style={styles.top}>
        <TouchableOpacity onPress={() => navigation.goBack()} accessibilityLabel="Close" testID="practice-close">
          <Ionicons name="close" size={26} color={C.text} />
        </TouchableOpacity>
        <Text style={styles.count}>Question {questions.length ? i + 1 : 0} of {questions.length}</Text>
        <View style={{ width: 26 }} />
      </View>
      <View style={styles.progress}>
        <View style={[styles.progressFill, { width: `${questions.length ? ((i + (answered ? 1 : 0)) / questions.length) * 100 : 0}%` }]} />
      </View>
      {topic ? <Text style={styles.topic} numberOfLines={1}>{topic}</Text> : null}

      {q ? (
        <ScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + 24 }]}>
          <Text style={styles.stem}>{q.stem}</Text>
          {q.options.map((opt, k) => {
            const isAnswer = opt === q.answer
            const isPicked = picked === k
            const tone = answered && isAnswer ? styles.optRight : answered && isPicked ? styles.optWrong : null
            return (
              <TouchableOpacity
                key={k}
                style={[styles.opt, tone]}
                disabled={answered}
                onPress={() => setPicks(p => ({ ...p, [i]: k }))}
                testID={`study-option-${k}`}
              >
                <Text style={[styles.optText, answered && isAnswer && { color: C.greenDk }]}>{opt}</Text>
                {answered && isAnswer ? <Ionicons name="checkmark-circle" size={18} color={C.green} /> : null}
                {answered && isPicked && !isAnswer ? <Ionicons name="close-circle" size={18} color={C.red} /> : null}
              </TouchableOpacity>
            )
          })}
          {answered ? (
            <View style={styles.explain}>
              <Text style={styles.explainHead}>{q.options[picked] === q.answer ? 'Correct' : 'Not quite'}</Text>
              <Text style={styles.explainText}>{q.explanation}</Text>
              {q.citation ? (
                <TouchableOpacity onPress={() => navigation.navigate('AssistantSource', { citation: q.citation, courseCode })}>
                  <Text style={styles.source}>{q.citation.title} · {openAtLabel(q.citation)}</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          ) : null}
          {answered ? (
            <TouchableOpacity
              style={styles.primaryBtn}
              onPress={() => (i < questions.length - 1 ? setI(i + 1) : finish())}
              testID="practice-next"
            >
              <Text style={styles.primaryText}>{i < questions.length - 1 ? 'Next' : 'See score'}</Text>
            </TouchableOpacity>
          ) : null}
        </ScrollView>
      ) : <Text style={styles.scoreText}>No questions.</Text>}
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg, paddingHorizontal: 16 },
  center: { alignItems: 'center', justifyContent: 'center', gap: 10 },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', height: 40 },
  count: { fontSize: 14, fontWeight: '600', color: C.textSub },
  progress: { height: 4, borderRadius: 2, backgroundColor: C.gray100, marginTop: 6, overflow: 'hidden' },
  progressFill: { height: 4, backgroundColor: C.primary },
  topic: { fontSize: 13, color: C.textHint, textAlign: 'center', marginTop: 8 },
  body: { paddingTop: 16 },
  stem: { fontSize: 18, lineHeight: 26, fontWeight: '600', color: C.text, marginBottom: 14 },
  opt: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8,
    borderWidth: 1, borderColor: C.border, backgroundColor: C.card, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 13, marginBottom: 10,
  },
  optRight: { borderColor: C.green, backgroundColor: C.greenLt },
  optWrong: { borderColor: C.red, backgroundColor: C.redLt },
  optText: { flex: 1, fontSize: 15, color: C.text },
  explain: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, marginTop: 4 },
  explainHead: { fontSize: 14, fontWeight: '700', color: C.text, marginBottom: 4 },
  explainText: { fontSize: 14, lineHeight: 20, color: C.textSub },
  source: { fontSize: 12, color: C.primary, marginTop: 8 },
  primaryBtn: {
    marginTop: 16, backgroundColor: C.primary, borderRadius: 12, paddingVertical: 13,
    alignItems: 'center', alignSelf: 'stretch',
  },
  primaryText: { color: '#fff', fontSize: 15, fontWeight: '600' },
  secondaryBtn: { paddingVertical: 12, alignSelf: 'stretch', alignItems: 'center' },
  secondaryText: { color: C.primary, fontSize: 15, fontWeight: '600' },
  scoreBig: { fontSize: 40, fontWeight: '800', color: C.text },
  scoreText: { fontSize: 14, color: C.textSub, textAlign: 'center' },
})
