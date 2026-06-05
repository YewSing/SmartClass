import { useState } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import ModalRouter from '../components/Modals'
import { QUIZZES } from '../data/mockData'
import { C } from '../theme'

const FILTERS = ['all', 'active', 'closed', 'draft']

export default function QuizList({ navigation }) {
  const { openModal } = useLecturer()
  const [filter, setFilter] = useState('all')

  const visible = filter === 'all' ? QUIZZES : QUIZZES.filter(q => q.status === filter)

  return (
    <View style={styles.flex}>
      <Topbar
        title="Quiz & Poll"
        sub="WIA2005 — Session in progress"
        right={
          <TouchableOpacity style={styles.createBtn} onPress={() => navigation.navigate('CreateQuiz')}>
            <Ionicons name="add" size={16} color="#fff" />
            <Text style={styles.createBtnText}>Create</Text>
          </TouchableOpacity>
        }
      />

      {/* Filter pills */}
      <View style={styles.filterRow}>
        {FILTERS.map(f => (
          <TouchableOpacity
            key={f}
            style={[styles.pill, filter === f && styles.pillActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.pillText, filter === f && styles.pillTextActive]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        <Text style={styles.countLabel}>{visible.length} questions this session</Text>
        {visible.map(q => (
          <TouchableOpacity key={q.id} style={styles.quizCard} onPress={() => openModal('quiz', q)}>
            <View style={styles.quizCardTop}>
              <Text style={styles.quizQ} numberOfLines={3}>{q.question}</Text>
              <Badge variant={q.status === 'active' ? 'blue' : q.status === 'closed' ? 'gray' : 'yellow'}>
                {q.status.charAt(0).toUpperCase() + q.status.slice(1)}
              </Badge>
            </View>

            <View style={styles.metaRow}>
              <Ionicons name="time-outline" size={11} color={C.textHint} />
              <Text style={styles.metaText}>
                {q.time}{q.timer ? ` · ${q.timer} timer` : ' · not pushed yet'}
              </Text>
              {q.status === 'active' && (
                <Text style={styles.metaText}>· {q.answered}/{q.total} answered</Text>
              )}
              {q.status === 'closed' && (
                <Text style={[styles.metaText, { color: C.greenDk, fontWeight: '700' }]}>· {q.pct}% correct</Text>
              )}
            </View>

            {q.status === 'active' && (
              <View style={styles.progressRow}>
                <View style={styles.progressTrack}>
                  <View style={[styles.progressFill, { width: `${q.pct}%` }]} />
                </View>
                <Text style={styles.progressPct}>{q.pct}%</Text>
              </View>
            )}

            {q.status === 'closed' && (
              <View style={styles.closedChips}>
                <View style={[styles.chip, { backgroundColor: C.greenLt }]}>
                  <Text style={[styles.chipText, { color: C.greenDk }]}>{q.correct_count} Correct</Text>
                </View>
                <View style={[styles.chip, { backgroundColor: C.redLt }]}>
                  <Text style={[styles.chipText, { color: C.redDk }]}>{q.wrong_count} Wrong</Text>
                </View>
                <View style={[styles.chip, { backgroundColor: C.gray100 }]}>
                  <Text style={[styles.chipText, { color: C.gray500 }]}>{q.unanswered_count} Skipped</Text>
                </View>
              </View>
            )}

            {q.status === 'draft' && (
              <TouchableOpacity style={styles.pushBtn} onPress={() => openModal('quiz', q)}>
                <Ionicons name="send-outline" size={13} color="#fff" />
                <Text style={styles.pushBtnText}>Push now</Text>
              </TouchableOpacity>
            )}
          </TouchableOpacity>
        ))}
        <View style={{ height: 20 }} />
      </ScrollView>

      <ModalRouter navigation={navigation} />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  createBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    gap: 4,
  },
  createBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: C.gray100,
  },
  pillActive: {
    backgroundColor: C.primary,
  },
  pillText: {
    fontSize: 13,
    fontWeight: '600',
    color: C.textSub,
  },
  pillTextActive: {
    color: '#fff',
  },
  countLabel: {
    padding: 12,
    paddingBottom: 4,
    fontSize: 12,
    color: C.textSub,
  },
  quizCard: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginHorizontal: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: C.border,
    gap: 8,
  },
  quizCardTop: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
  },
  quizQ: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
    lineHeight: 20,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    flexWrap: 'wrap',
  },
  metaText: {
    fontSize: 11,
    color: C.textHint,
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  progressTrack: {
    flex: 1,
    height: 4,
    backgroundColor: C.gray100,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: C.primary,
    borderRadius: 2,
  },
  progressPct: {
    fontSize: 10,
    color: C.textHint,
  },
  closedChips: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
  },
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  chipText: {
    fontSize: 11,
    fontWeight: '700',
  },
  pushBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.primary,
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    gap: 6,
  },
  pushBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
})
