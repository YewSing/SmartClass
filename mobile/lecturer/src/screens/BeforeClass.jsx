import { useCallback, useEffect, useState } from 'react'
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import MarkdownText from '../components/MarkdownText'
import Topbar from '../components/Topbar'
import { useLecturer } from '../context/LecturerContext'
import { getBeforeClass } from '../services/api'
import { openAtLabel } from '../services/openSource'
import { C } from '../theme'

export default function BeforeClass({ route, navigation }) {
  const { courseId, courseCode } = route.params
  const { showToast } = useLecturer()
  const [summary, setSummary] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      setSummary(await getBeforeClass(courseId))
    } catch (e) { showToast(e.message, 'error') }
  }, [courseId, showToast])

  useEffect(() => { load() }, [load])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }, [load])

  return (
    <View style={styles.screen}>
      <Topbar title="Before next class" sub={courseCode} onBack={() => navigation.goBack()} />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {!summary ? (
          <ActivityIndicator style={{ marginTop: 40 }} color={C.primary} />
        ) : summary.not_enough_data ? (
          <View style={styles.empty}>
            <Ionicons name="hourglass-outline" size={36} color={C.textHint} />
            <Text style={styles.emptyTitle}>Not enough questions yet</Text>
            <Text style={styles.emptyText}>{summary.content}</Text>
          </View>
        ) : (
          <>
            <View style={styles.card}>
              <MarkdownText>{summary.content}</MarkdownText>
              {summary.citations?.length ? (
                <View style={styles.chips}>
                  {summary.citations.map(c => (
                    <TouchableOpacity
                      key={c.n}
                      style={styles.chip}
                      testID="before-class-citation"
                      onPress={() => navigation.navigate('LecturerSource', { citation: c, courseCode })}
                    >
                      <Text style={styles.chipNum}>[{c.n}]</Text>
                      <Text style={styles.chipText} numberOfLines={1}>{c.title} · {openAtLabel(c)}</Text>
                      <Ionicons name="open-outline" size={13} color={C.primary} />
                    </TouchableOpacity>
                  ))}
                </View>
              ) : null}
            </View>
            <Text style={styles.hint}>Built from what students ask — only topics asked by at least 3 students, with no names.</Text>
          </>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32 },
  card: { backgroundColor: C.card, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: C.border },
  empty: { alignItems: 'center', marginTop: 60, gap: 10, paddingHorizontal: 24 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: C.text },
  emptyText: { fontSize: 13, color: C.textSub, textAlign: 'center', lineHeight: 19 },
  chips: { marginTop: 12, gap: 6 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.blueLt, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6,
  },
  chipNum: { fontSize: 12, fontWeight: '700', color: C.primary },
  chipText: { flex: 1, fontSize: 12, color: C.blueDk },
  hint: { fontSize: 12, color: C.textHint, textAlign: 'center', marginTop: 12, lineHeight: 17 },
})
