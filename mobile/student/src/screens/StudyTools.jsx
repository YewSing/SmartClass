import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, KeyboardAvoidingView,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import MarkdownText from '../components/MarkdownText'
import Topbar from '../components/Topbar'
import { useStudent } from '../context/StudentContext'
import { generateSummary, generateStudyTools } from '../services/api'
import { openAtLabel } from '../services/openSource'
import { C } from '../theme'

const KINDS = [
  { key: 'summary', label: 'Summarise', icon: 'document-text-outline' },
  { key: 'study_guide', label: 'Study guide', icon: 'book-outline' },
  { key: 'flashcards', label: 'Flashcards', icon: 'albums-outline' },
  { key: 'practice_questions', label: 'Practice', icon: 'help-circle-outline' },
]

function CitationChips({ citations, onOpen }) {
  if (!citations?.length) return null
  return (
    <View style={styles.chips}>
      {citations.map(c => (
        <TouchableOpacity key={c.n} style={styles.chip} onPress={() => onOpen(c)}>
          <Text style={styles.chipNum}>[{c.n}]</Text>
          <Text style={styles.chipText} numberOfLines={1}>{c.title} · {openAtLabel(c)}</Text>
          <Ionicons name="open-outline" size={13} color={C.primary} />
        </TouchableOpacity>
      ))}
    </View>
  )
}

function Flashcard({ card }) {
  const [flipped, setFlipped] = useState(false)
  return (
    <TouchableOpacity
      style={styles.flashcard}
      testID="study-card"
      activeOpacity={0.85}
      onPress={() => setFlipped(f => !f)}
    >
      <Text style={styles.flashcardHint}>{flipped ? 'Answer' : 'Question'} · tap to flip</Text>
      <Text style={styles.flashcardText}>{flipped ? card.back : card.front}</Text>
    </TouchableOpacity>
  )
}

function PracticeQuestion({ question }) {
  const [picked, setPicked] = useState(null)
  const answered = picked !== null
  return (
    <View style={styles.questionCard}>
      <Text style={styles.questionStem}>{question.stem}</Text>
      {question.options.map((opt, i) => {
        const isAnswer = opt === question.answer
        const isPicked = picked === i
        const show = answered && (isAnswer || isPicked)
        const tone = isAnswer ? styles.optionCorrect : isPicked ? styles.optionWrong : null
        return (
          <TouchableOpacity
            key={i}
            style={[styles.option, show && tone]}
            testID={`study-option-${i}`}
            disabled={answered}
            onPress={() => setPicked(i)}
          >
            <Text style={[styles.optionText, show && isAnswer && { color: C.greenDk }]}>{opt}</Text>
          </TouchableOpacity>
        )
      })}
      {answered && (
        <View style={styles.explanation}>
          <Text style={styles.explanationLabel}>{picked === question.options.indexOf(question.answer) ? 'Correct' : 'Not quite'}</Text>
          <Text style={styles.explanationText}>{question.explanation}</Text>
        </View>
      )}
    </View>
  )
}

export default function StudyTools({ route, navigation }) {
  const { courseId, courseCode } = route.params
  const { showToast } = useStudent()
  const [kind, setKind] = useState('summary')
  const [topic, setTopic] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const isSummary = kind === 'summary' || kind === 'study_guide'
  const isFlashcards = kind === 'flashcards'
  const isPractice = kind === 'practice_questions'

  const generate = async () => {
    const t = topic.trim()
    if (!t || loading) return
    setLoading(true)
    setResult(null)
    try {
      if (isSummary) setResult(await generateSummary(courseId, { topic: t, kind }))
      else setResult(await generateStudyTools(courseId, { topic: t, kind }))
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const openCitation = (citation) => navigation.navigate('AssistantSource', { citation, courseCode })

  return (
    <KeyboardAvoidingView style={styles.screen} behavior="padding">
      <Topbar title="Study tools" sub={courseCode} onBack={() => navigation.goBack()} />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.sectionLabel}>What would you like?</Text>
        <View style={styles.kindRow}>
          {KINDS.map(k => {
            const active = k.key === kind
            return (
              <TouchableOpacity
                key={k.key}
                style={[styles.kind, active && styles.kindActive]}
                testID={`study-kind-${k.key}`}
                onPress={() => { setKind(k.key); setResult(null) }}
              >
                <Ionicons name={k.icon} size={16} color={active ? '#fff' : C.primary} />
                <Text style={[styles.kindText, active && styles.kindTextActive]}>{k.label}</Text>
              </TouchableOpacity>
            )
          })}
        </View>

        <Text style={styles.sectionLabel}>Topic</Text>
        <TextInput
          testID="study-topic"
          style={styles.input}
          value={topic}
          onChangeText={setTopic}
          placeholder="e.g. boundary value analysis"
          placeholderTextColor={C.textHint}
          maxLength={200}
        />
        <TouchableOpacity
          style={[styles.generateBtn, (!topic.trim() || loading) && styles.disabled]}
          testID="study-generate"
          onPress={generate}
          disabled={!topic.trim() || loading}
        >
          <Ionicons name="sparkles" size={16} color="#fff" />
          <Text style={styles.generateText}>{loading ? 'Generating…' : 'Generate'}</Text>
        </TouchableOpacity>

        {loading && <ActivityIndicator style={{ marginTop: 24 }} color={C.primary} />}

        {result && isSummary && (
          <View style={styles.resultCard}>
            {result.source_type === 'general' && (
              <View style={styles.generalTag}>
                <Ionicons name="globe-outline" size={12} color={C.orangeDk} />
                <Text style={styles.generalText}>General knowledge · not from your course materials</Text>
              </View>
            )}
            <MarkdownText>{result.content}</MarkdownText>
            <CitationChips citations={result.citations} onOpen={openCitation} />
          </View>
        )}

        {result && isFlashcards && result.cards?.map((card, i) => (
          <Flashcard key={i} card={card} />
        ))}
        {result && isFlashcards && result.cards?.length === 0 && (
          <Text style={styles.emptyText}>No flashcards for this topic.</Text>
        )}

        {result && isPractice && result.questions?.map((q, i) => (
          <PracticeQuestion key={i} question={q} />
        ))}
        {result && isPractice && result.questions?.length === 0 && (
          <Text style={styles.emptyText}>No practice questions for this topic.</Text>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32 },
  sectionLabel: {
    fontSize: 12, fontWeight: '700', color: C.textSub, textTransform: 'uppercase',
    letterSpacing: 0.5, marginBottom: 8, marginTop: 6,
  },
  kindRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  kind: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 18,
    backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
  },
  kindActive: { backgroundColor: C.primary, borderColor: C.primary },
  kindText: { fontSize: 13, fontWeight: '600', color: C.primary },
  kindTextActive: { color: '#fff' },
  input: {
    fontSize: 15, color: C.text, backgroundColor: C.card, borderRadius: 10,
    borderWidth: 1, borderColor: C.border, paddingHorizontal: 12, paddingVertical: 10,
  },
  generateBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 12, marginTop: 12,
  },
  generateText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  disabled: { opacity: 0.45 },
  resultCard: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginTop: 16,
    borderWidth: 1, borderColor: C.border,
  },
  generalTag: {
    flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start',
    backgroundColor: C.orangeLt, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 3, marginBottom: 8,
  },
  generalText: { fontSize: 11, fontWeight: '600', color: C.orangeDk },
  chips: { marginTop: 10, gap: 6 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.blueLt, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6,
  },
  chipNum: { fontSize: 12, fontWeight: '700', color: C.primary },
  chipText: { flex: 1, fontSize: 12, color: C.blueDk },
  flashcard: {
    backgroundColor: C.card, borderRadius: 12, padding: 20, marginTop: 12, minHeight: 140,
    borderWidth: 1, borderColor: C.border, alignItems: 'center', justifyContent: 'center',
  },
  flashcardHint: { fontSize: 11, fontWeight: '600', color: C.textHint, textTransform: 'uppercase', marginBottom: 10 },
  flashcardText: { fontSize: 17, fontWeight: '700', color: C.text, textAlign: 'center', lineHeight: 24 },
  questionCard: { backgroundColor: C.card, borderRadius: 12, padding: 14, marginTop: 12, borderWidth: 1, borderColor: C.border },
  questionStem: { fontSize: 15, fontWeight: '600', color: C.text, marginBottom: 10 },
  option: {
    borderWidth: 1, borderColor: C.border, borderRadius: 8, paddingVertical: 10, paddingHorizontal: 12, marginBottom: 6,
  },
  optionCorrect: { borderColor: C.green, backgroundColor: C.greenLt },
  optionWrong: { borderColor: C.red, backgroundColor: C.redLt },
  optionText: { fontSize: 14, color: C.text },
  explanation: { marginTop: 8, padding: 10, backgroundColor: C.bg, borderRadius: 8 },
  explanationLabel: { fontSize: 12, fontWeight: '700', color: C.primary, marginBottom: 2 },
  explanationText: { fontSize: 13, color: C.text, lineHeight: 19 },
  emptyText: { fontSize: 13, color: C.textHint, textAlign: 'center', marginTop: 16 },
})
