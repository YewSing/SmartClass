import { useState } from 'react'
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { useStudent } from '../context/StudentContext'
import { openAtLabel, openCitedSource } from '../services/openSource'
import { C } from '../theme'

export default function AssistantSource({ route, navigation }) {
  const { citation, courseCode } = route.params
  const { showToast } = useStudent()
  const [opening, setOpening] = useState(false)
  const where = openAtLabel(citation)

  const open = async () => {
    setOpening(true)
    try {
      await openCitedSource(citation)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setOpening(false)
    }
  }

  return (
    <View style={styles.screen}>
      <Topbar title={`Source [${citation.n}]`} sub={courseCode} onBack={() => navigation.goBack()} />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.card}>
          <View style={styles.titleRow}>
            <Ionicons name="document-text-outline" size={22} color={C.primary} />
            <Text style={styles.title}>{citation.title}</Text>
          </View>
          {citation.section ? <Text style={styles.meta}>{citation.section}</Text> : null}
          <Text style={styles.location}>{citation.location}</Text>
        </View>

        <Text style={styles.label}>Cited passage</Text>
        <View style={styles.snippetBox}>
          <Text style={styles.snippet}>{citation.snippet}</Text>
        </View>

        <TouchableOpacity style={[styles.openBtn, opening && styles.disabled]} onPress={open} disabled={opening}>
          {opening ? <ActivityIndicator color="#fff" size="small" /> : (
            <>
              <Ionicons name="open-outline" size={18} color="#fff" style={{ marginRight: 8 }} />
              <Text style={styles.openText}>Open file at {where}</Text>
            </>
          )}
        </TouchableOpacity>
        <Text style={styles.hint}>
          Most phone viewers open the file at the start. Go to {where} to see this passage.
        </Text>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32 },
  card: { backgroundColor: C.card, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: C.border },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { flex: 1, fontSize: 16, fontWeight: '700', color: C.text },
  meta: { fontSize: 13, color: C.textSub, marginTop: 6 },
  location: { fontSize: 13, fontWeight: '600', color: C.primary, marginTop: 6 },
  label: {
    fontSize: 12, fontWeight: '700', color: C.textSub, textTransform: 'uppercase',
    letterSpacing: 0.5, marginTop: 18, marginBottom: 8,
  },
  snippetBox: {
    backgroundColor: C.card, borderRadius: 10, padding: 12,
    borderLeftWidth: 3, borderLeftColor: C.primary,
  },
  snippet: { fontSize: 14, color: C.text, lineHeight: 21 },
  openBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 13, marginTop: 20,
  },
  disabled: { opacity: 0.65 },
  openText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  hint: { fontSize: 12, color: C.textHint, textAlign: 'center', marginTop: 10, lineHeight: 17 },
})
