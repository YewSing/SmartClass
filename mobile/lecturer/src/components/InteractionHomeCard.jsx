// Home's interaction card, under the attendance card (S38f): one session's numbers at a glance. A running
// class updates live and opens its live screen; an ended one opens its summary. Counts only, no names.
import { useCallback, useRef, useState } from 'react'
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import * as api from '../services/api'
import { BASE, getToken } from '../services/client'
import { connectInteractionLive, homeCounts } from '../services/interaction'
import { C, TONES } from '../interactionTheme'

const RELOAD_MS = 800   // several events close together read the numbers once
const ITEMS = [
  ['questions', 'Questions', 'teal'],
  ['polls', 'Polls', 'blue'],
  ['answers', 'Answers', 'purple'],
  ['reactions', 'Reactions', 'green'],
  ['confused', 'Confused', 'orange'],
]

async function refreshViaApi() {
  try { await api.getLecturer(); return true } catch { return false }
}

export default function InteractionHomeCard({ sessionId, live, label, onPress, testID, refreshKey }) {
  const [loaded, setLoaded] = useState(null)   // { id, counts } of the session last read
  const [failed, setFailed] = useState(false)
  const timer = useRef(null)

  // Only while Home is on screen; `refreshKey` changes on a pull to refresh
  useFocusEffect(useCallback(() => {
    let active = true
    const load = async () => {
      try {
        const counts = homeCounts(await api.getInteractionSummary(sessionId))
        if (active) { setLoaded({ id: sessionId, counts }); setFailed(false) }
      } catch {
        if (active) setFailed(true)
      }
    }
    load()
    const socket = live ? connectInteractionLive({
      baseUrl: BASE, sessionId, getToken, refreshToken: refreshViaApi,
      onMessage: () => {
        if (!active) return
        clearTimeout(timer.current)
        timer.current = setTimeout(load, RELOAD_MS)
      },
    }) : null
    return () => { active = false; clearTimeout(timer.current); socket?.close() }
  }, [sessionId, live, refreshKey]))

  const counts = loaded?.id === sessionId ? loaded.counts : null
  const waiting = counts && live
    ? (counts.waiting ? `${counts.waiting} waiting for an answer` : 'no question waiting') : null
  const sub = [label, live ? 'live' : null, waiting].filter(Boolean).join(' · ')

  return (
    <TouchableOpacity style={s.card} onPress={onPress} testID={testID} accessibilityRole="button">
      {sub ? <Text style={s.sub}>{sub}</Text> : null}
      <View style={s.row}>
        {ITEMS.map(([key, name, tone]) => {
          const t = TONES[tone]
          return (
            <View key={key} style={[s.item, { backgroundColor: t.lt }]}>
              <Text style={[s.num, { color: t.dk }]} testID={`${testID}-${key}`}>{counts ? counts[key] : '–'}</Text>
              <Text style={[s.name, { color: t.dk }]} numberOfLines={1}>{name}</Text>
            </View>
          )
        })}
      </View>
      {failed && !counts ? <Text style={s.failed}>Couldn't load the numbers. Pull down to try again.</Text> : null}
      <View style={s.footer}>
        <Ionicons name="chevron-forward" size={12} color={C.textHint} />
        <Text style={s.footerText}>{live ? 'Tap to open the live interaction' : 'Tap to view the summary'}</Text>
      </View>
    </TouchableOpacity>
  )
}

const s = StyleSheet.create({
  card: {
    backgroundColor: C.card, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: C.border,
  },
  sub: { fontSize: 12, color: C.textSub, marginBottom: 10 },
  row: { flexDirection: 'row', gap: 6, marginBottom: 12 },
  item: { flex: 1, alignItems: 'center', borderRadius: 10, paddingVertical: 10, paddingHorizontal: 1 },
  num: { fontSize: 22, fontWeight: '800' },
  name: { fontSize: 11, fontWeight: '600', marginTop: 1 },
  failed: { fontSize: 12, color: C.redDk, marginBottom: 10 },
  footer: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingTop: 10, borderTopWidth: 1,
    borderTopColor: C.border,
  },
  footerText: { fontSize: 12, color: C.textHint },
})
