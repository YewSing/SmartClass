import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { LinearGradient } from 'expo-linear-gradient'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useFocusEffect } from '@react-navigation/native'
import { useStudent } from '../context/StudentContext'
import Badge from '../components/Badge'
import { getOpenInteractions } from '../services/api'
import { C } from '../theme'

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning,'
  if (h < 17) return 'Good afternoon,'
  return 'Good evening,'
}

export default function Home({ navigation }) {
  const { state, loadClasses, showToast } = useStudent()
  const { classes, student } = state
  const insets = useSafeAreaInsets()

  useEffect(() => { loadClasses() }, [loadClasses])

  // ── Live interaction card (UC-501 step 3 / FR-201 ongoing activities, S25) ──
  const [openInteractions, setOpenInteractions] = useState([])
  const loadOpenInteractions = useCallback(async () => {
    try { setOpenInteractions(await getOpenInteractions()) } catch { /* card hides on failure */ }
  }, [])
  useFocusEffect(useCallback(() => { loadOpenInteractions() }, [loadOpenInteractions]))

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadClasses(), loadOpenInteractions()])
    setRefreshing(false)
  }, [loadClasses, loadOpenInteractions])

  // One live session at a time per the FR-501 flow; if several are open, join the first.
  const liveInteraction = openInteractions[0] ?? null

  const joinInteraction = () => {
    if (!liveInteraction) return
    navigation.navigate('Participation', { interaction_id: liveInteraction.id })
  }

  return (
    <View style={styles.flex}>
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* Greeting banner */}
        <LinearGradient
          colors={['#0D47A1', '#1565C0', '#1976D2']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[styles.banner, { paddingTop: insets.top + 20 }]}
        >
          <Text style={styles.greetingText}>{greeting()}</Text>
          <Text style={styles.greetingName}>{student?.name ?? '—'}</Text>
          <Text style={styles.greetingSub}>
            {classes.length > 0
              ? `${classes.length} enrolled class${classes.length !== 1 ? 'es' : ''}`
              : 'Loading classes…'}
          </Text>
        </LinearGradient>

        {/* Live interaction — ongoing classroom activity (FR-201, UC-501 step 3) */}
        {liveInteraction && (
          <TouchableOpacity
            testID="home-interaction-card"
            style={styles.liveCard}
            activeOpacity={0.8}
            onPress={joinInteraction}
          >
            <View style={styles.liveCardIcon}>
              <Ionicons name="chatbubbles" size={20} color="#fff" />
            </View>
            <View style={styles.liveCardBody}>
              <Text style={styles.liveCardTitle}>Class interaction is live</Text>
              <Text style={styles.liveCardSub} numberOfLines={1}>
                {liveInteraction.class_code} · {liveInteraction.class_name}
              </Text>
            </View>
            <View style={styles.liveBadge}>
              <Text style={styles.liveBadgeText}>Join</Text>
            </View>
          </TouchableOpacity>
        )}

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>My Classes</Text>
        </View>

        {classes.map(cls => (
          <TouchableOpacity
            key={cls.id}
            style={styles.classCard}
            activeOpacity={0.7}
            onPress={() => navigation.navigate('Attendance')}
          >
            <View style={[styles.accent, { backgroundColor: cls.accentColor }]} />
            <View style={styles.classBody}>
              <View style={styles.codeRow}>
                <Text style={styles.classCode}>{cls.code}</Text>
                <Badge variant={cls.type === 'LECTURE' ? 'blue' : 'green'}>
                  {cls.type === 'LECTURE' ? 'Lecture' : (cls.label ?? 'Tutorial')}
                </Badge>
              </View>
              <Text style={styles.classTitle}>{cls.name}</Text>
              {cls.venue ? (
                <View style={styles.metaRow}>
                  <Ionicons name="location-outline" size={12} color={C.textSub} />
                  <Text style={styles.metaText}>{cls.venue}</Text>
                </View>
              ) : null}
            </View>
            <View style={styles.cardArrow}>
              <Ionicons name="chevron-forward" size={20} color={C.gray400} />
            </View>
          </TouchableOpacity>
        ))}

        {classes.length === 0 && (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>No enrolled classes found.</Text>
          </View>
        )}

        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  banner: {
    paddingHorizontal: 20,
    paddingBottom: 28,
  },
  liveCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0D47A1',
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
    padding: 12,
    gap: 12,
  },
  liveCardIcon: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(255,255,255,0.18)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  liveCardBody: { flex: 1 },
  liveCardTitle: { fontSize: 14, fontWeight: '700', color: '#fff' },
  liveCardSub: { fontSize: 12, color: '#BFDBFE', marginTop: 2 },
  liveBadge: {
    backgroundColor: '#fff',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 6,
  },
  liveBadgeText: { fontSize: 12, fontWeight: '800', color: '#0D47A1' },
  greetingText: {
    fontSize: 14,
    color: '#DBEAFE',
    fontWeight: '500',
  },
  greetingName: {
    fontSize: 24,
    fontWeight: '800',
    color: '#fff',
    marginTop: 4,
  },
  greetingSub: {
    fontSize: 13,
    color: '#BFDBFE',
    marginTop: 6,
  },
  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  classCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    marginHorizontal: 16,
    marginBottom: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    overflow: 'hidden',
  },
  accent: {
    width: 5,
    alignSelf: 'stretch',
  },
  classBody: {
    flex: 1,
    paddingVertical: 14,
    paddingLeft: 14,
    paddingRight: 6,
  },
  codeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  classCode: {
    fontSize: 12,
    fontWeight: '700',
    color: C.primary,
  },
  classTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: C.text,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 6,
  },
  metaText: {
    fontSize: 12,
    color: C.textSub,
  },
  cardArrow: {
    justifyContent: 'center',
    paddingRight: 14,
    paddingLeft: 4,
  },
  empty: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    color: C.textSub,
  },
})
