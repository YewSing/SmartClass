import { useEffect, useState, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { LinearGradient } from 'expo-linear-gradient'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import Badge from '../components/Badge'
import { C } from '../theme'

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning,'
  if (h < 17) return 'Good afternoon,'
  return 'Good evening,'
}

export default function Home({ navigation }) {
  const { state, loadClasses } = useStudent()
  const { classes, student } = state
  const insets = useSafeAreaInsets()

  useEffect(() => { loadClasses() }, [loadClasses])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadClasses()
    setRefreshing(false)
  }, [loadClasses])

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
