import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { C } from '../theme'

const DEFAULT_OPTIONS = ['Class Diagram', 'Use Case Diagram', 'Sequence Diagram', 'Activity Diagram']
const TIME_LIMITS = ['15s', '30s', '60s']

export default function CreateQuiz({ navigation }) {
  const [question, setQuestion] = useState('Which UML diagram best represents the sequence of operations in a use case?')
  const [options, setOptions] = useState(DEFAULT_OPTIONS)
  const [correct, setCorrect] = useState(2)
  const [timer, setTimer] = useState('30s')

  const updateOption = (i, text) => {
    setOptions(prev => prev.map((o, j) => j === i ? text : o))
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Create Quiz / Poll"
        sub="Leave answers unmarked for poll mode"
        onBack={() => navigation.goBack()}
      />
      <ScrollView style={styles.flex} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {/* Question */}
        <Text style={styles.label}>Question</Text>
        <TextInput
          style={styles.textarea}
          multiline
          numberOfLines={4}
          placeholder="Enter your question…"
          placeholderTextColor={C.textHint}
          value={question}
          onChangeText={setQuestion}
          textAlignVertical="top"
        />

        {/* Options */}
        <Text style={styles.label}>
          Answer Options{' '}
          <Text style={styles.labelHint}>· tap ✓ to mark correct answer</Text>
        </Text>
        {options.map((opt, i) => (
          <View key={i} style={styles.answerOption}>
            <View style={styles.optLabel}>
              <Text style={styles.optLabelText}>{String.fromCharCode(65 + i)}</Text>
            </View>
            <TextInput
              style={styles.optInput}
              value={opt}
              onChangeText={t => updateOption(i, t)}
              placeholder={`Option ${String.fromCharCode(65 + i)}`}
              placeholderTextColor={C.textHint}
            />
            <TouchableOpacity
              style={[styles.correctToggle, correct === i && styles.correctToggleActive]}
              onPress={() => setCorrect(i)}
            >
              <Ionicons name="checkmark" size={16} color={correct === i ? '#fff' : C.gray400} />
            </TouchableOpacity>
          </View>
        ))}

        {/* Time limit */}
        <Text style={[styles.label, { marginTop: 16 }]}>Time Limit</Text>
        <View style={styles.timePills}>
          {TIME_LIMITS.map(t => (
            <TouchableOpacity
              key={t}
              style={[styles.timePill, timer === t && styles.timePillActive]}
              onPress={() => setTimer(t)}
            >
              <Text style={[styles.timePillText, timer === t && styles.timePillTextActive]}>{t}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.divider} />

        {/* Actions */}
        <View style={styles.btnRow}>
          <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={() => navigation.goBack()}>
            <Ionicons name="save-outline" size={16} color={C.text} />
            <Text style={styles.btnOutlineText}>Save Draft</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={() => navigation.goBack()}>
            <Ionicons name="send-outline" size={16} color="#fff" />
            <Text style={styles.btnPrimaryText}>Push to Desks</Text>
          </TouchableOpacity>
        </View>
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: {
    padding: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: C.text,
    marginBottom: 8,
  },
  labelHint: {
    fontSize: 11,
    color: C.textHint,
    fontWeight: '400',
  },
  textarea: {
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
    color: C.text,
    backgroundColor: C.card,
    marginBottom: 18,
    minHeight: 90,
  },
  answerOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: C.border,
    marginBottom: 8,
    overflow: 'hidden',
  },
  optLabel: {
    width: 42,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: C.gray50,
    alignSelf: 'stretch',
  },
  optLabelText: {
    fontSize: 14,
    fontWeight: '700',
    color: C.textSub,
  },
  optInput: {
    flex: 1,
    fontSize: 14,
    color: C.text,
    paddingHorizontal: 12,
    paddingVertical: 13,
  },
  correctToggle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    marginRight: 8,
    backgroundColor: C.gray100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  correctToggleActive: {
    backgroundColor: C.green,
  },
  timePills: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 4,
  },
  timePill: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: C.border,
    alignItems: 'center',
    backgroundColor: C.card,
  },
  timePillActive: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  timePillText: {
    fontSize: 14,
    fontWeight: '600',
    color: C.textSub,
  },
  timePillTextActive: {
    color: '#fff',
  },
  divider: {
    height: 1,
    backgroundColor: C.border,
    marginVertical: 18,
  },
  btnRow: {
    flexDirection: 'row',
    gap: 10,
  },
  btn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 13,
    borderRadius: 10,
    gap: 6,
  },
  btnPrimary: {
    backgroundColor: C.primary,
  },
  btnOutline: {
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: C.card,
  },
  btnPrimaryText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
  },
  btnOutlineText: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
})
