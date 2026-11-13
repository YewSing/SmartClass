// Full-screen flashcards from a chat message (FR-811): one card at a time, tap to flip.
import { useState } from 'react'
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import { openAtLabel, openCitation } from '../services/openSource'
import { C } from '../theme'

export default function Flashcards({ route, navigation }) {
  const { cards = [], topic, courseCode } = route.params
  const insets = useSafeAreaInsets()
  const { showToast } = useStudent()
  const [i, setI] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const card = cards[i]

  const go = (next) => {
    setI(next)
    setFlipped(false)
  }

  return (
    <View style={[styles.screen, { paddingTop: insets.top + 6, paddingBottom: insets.bottom + 12 }]}>
      <View style={styles.top}>
        <TouchableOpacity onPress={() => navigation.goBack()} accessibilityLabel="Close" testID="flashcards-close">
          <Ionicons name="close" size={26} color={C.text} />
        </TouchableOpacity>
        <Text style={styles.count}>Card {cards.length ? i + 1 : 0} of {cards.length}</Text>
        <View style={{ width: 26 }} />
      </View>
      {topic ? <Text style={styles.topic} numberOfLines={1}>{topic}</Text> : null}

      {card ? (
        <TouchableOpacity
          style={[styles.card, flipped && styles.cardBack]}
          activeOpacity={0.9}
          onPress={() => setFlipped(f => !f)}
          testID="study-card"
        >
          <Text style={styles.side}>{flipped ? 'Answer' : 'Question'}</Text>
          <Text style={styles.cardText}>{flipped ? card.back : card.front}</Text>
          <Text style={styles.flipHint}>Tap to {flipped ? 'see the question' : 'flip'}</Text>
        </TouchableOpacity>
      ) : <Text style={styles.empty}>No cards.</Text>}

      {card?.citation ? (
        <TouchableOpacity
          style={styles.source}
          onPress={() => openCitation(card.citation, navigation).catch(e => showToast(e.message, 'error'))}
        >
          <Ionicons name="document-text-outline" size={14} color={C.primary} />
          <Text style={styles.sourceText} numberOfLines={1}>{card.citation.title} · {openAtLabel(card.citation)}</Text>
        </TouchableOpacity>
      ) : null}

      <View style={styles.nav}>
        <TouchableOpacity
          style={[styles.navBtn, i === 0 && styles.navDisabled]}
          disabled={i === 0}
          onPress={() => go(i - 1)}
          accessibilityLabel="Previous card"
        >
          <Ionicons name="chevron-back" size={22} color={C.primary} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.navBtn, i >= cards.length - 1 && styles.navDisabled]}
          disabled={i >= cards.length - 1}
          onPress={() => go(i + 1)}
          accessibilityLabel="Next card"
          testID="flashcards-next"
        >
          <Ionicons name="chevron-forward" size={22} color={C.primary} />
        </TouchableOpacity>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg, paddingHorizontal: 16 },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', height: 40 },
  count: { fontSize: 14, fontWeight: '600', color: C.textSub },
  topic: { fontSize: 13, color: C.textHint, textAlign: 'center', marginTop: 2 },
  card: {
    flex: 1, marginTop: 18, borderRadius: 18, backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
    alignItems: 'center', justifyContent: 'center', padding: 24,
  },
  cardBack: { backgroundColor: C.blueLt, borderColor: C.primary },
  side: { position: 'absolute', top: 16, fontSize: 12, fontWeight: '700', color: C.textHint, textTransform: 'uppercase' },
  cardText: { fontSize: 20, lineHeight: 28, fontWeight: '600', color: C.text, textAlign: 'center' },
  flipHint: { position: 'absolute', bottom: 16, fontSize: 12, color: C.textHint },
  empty: { flex: 1, textAlign: 'center', marginTop: 40, color: C.textSub },
  source: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'center', marginTop: 12, maxWidth: '90%' },
  sourceText: { fontSize: 12, color: C.primary },
  nav: { flexDirection: 'row', justifyContent: 'center', gap: 40, marginTop: 16 },
  navBtn: {
    width: 52, height: 52, borderRadius: 26, borderWidth: 1, borderColor: C.primary,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.card,
  },
  navDisabled: { opacity: 0.3 },
})
