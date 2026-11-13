import { useState, useCallback } from 'react'
import {
  View, Text, ScrollView, StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useStudent } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import { flagView } from '../services/attendance'
import { C } from '../theme'

const HERO_COLORS = {
  pending:   { fg: C.yellow, bg: C.yellowLt },
  confirmed: { fg: C.green,  bg: C.greenLt },
  rejected:  { fg: C.red,    bg: C.redLt },
}

const REVIEW = {
  pending:   { dot: C.gray300, icon: 'time-outline' },
  confirmed: { dot: C.green,   icon: 'checkmark' },
  rejected:  { dot: C.red,     icon: 'close' },
}

// The real state of the student's "I'm here" flag (FR-319). The context's SET_FLAG, from the
// student's own websocket, re-renders this screen live when the lecturer decides.
export default function AttReportStatus({ route, navigation }) {
  const { state, loadFlag } = useStudent()
  const { sessionId } = route.params ?? {}
  const sid = Number(sessionId)
  const flag = state.flags[sid] ?? null
  const view = flagView(flag)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useFocusEffect(useCallback(() => {
    let gone = false
    setLoading(true)
    loadFlag(sid).finally(() => { if (!gone) setLoading(false) })
    return () => { gone = true }
  }, [loadFlag, sid]))

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadFlag(sid)
    setRefreshing(false)
  }, [loadFlag, sid])

  const colors = HERO_COLORS[view?.state] ?? HERO_COLORS.pending
  const review = REVIEW[view?.state] ?? REVIEW.pending

  const details = view ? [
    { label: 'Class', value: view.classText },
    { label: 'Date', value: view.dateText },
    { label: 'Flagged at', value: view.flaggedText },
    ...(view.resolvedText ? [{ label: 'Resolved at', value: view.resolvedText }] : []),
  ] : []

  let reviewTitle = 'Lecturer review'
  let reviewTime = 'Waiting'
  if (view?.state === 'confirmed') reviewTime = `Confirmed at ${view.resolvedText}`
  if (view?.state === 'rejected') reviewTime = `Rejected at ${view.resolvedText}`

  return (
    <View style={styles.flex}>
      <Topbar title="Flag Status" sub={flag?.class_code} onBack={() => navigation.goBack()} />
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {loading && !view ? (
          <View style={styles.empty}>
            <ActivityIndicator color={C.primary} />
          </View>
        ) : !view ? (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>You haven't flagged this class.</Text>
          </View>
        ) : (
          <>
            {/* Hero */}
            <View style={styles.hero}>
              <View style={[styles.heroIcon, { backgroundColor: colors.bg }]}>
                <Ionicons name={view.icon} size={26} color={colors.fg} />
              </View>
              <Text testID="flag-status" style={styles.heroLabel}>{view.title}</Text>
              <Text testID="flag-status-sub" style={styles.heroSub}>{view.sub}</Text>
            </View>

            {/* Flag details */}
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Flag details</Text>
              {details.map(row => (
                <View key={row.label} style={styles.detailRow}>
                  <Text style={styles.detailKey}>{row.label}</Text>
                  <Text style={styles.detailVal}>{row.value}</Text>
                </View>
              ))}
            </View>

            {/* Progress timeline */}
            <Text style={styles.sectionTitle}>Progress</Text>
            <View style={styles.timeline}>
              <View style={styles.tlItem}>
                <View style={[styles.tlDot, { backgroundColor: C.green }]}>
                  <Ionicons name="checkmark" size={12} color="#fff" />
                </View>
                <View style={styles.tlContent}>
                  <Text style={styles.tlTitle}>Flagged</Text>
                  <Text style={styles.tlTime}>{view.flaggedText}</Text>
                </View>
              </View>

              <View style={styles.tlItem}>
                <View style={[styles.tlDot, { backgroundColor: review.dot }]}>
                  <Ionicons name={review.icon} size={12} color="#fff" />
                </View>
                <View style={styles.tlContent}>
                  <Text style={styles.tlTitle}>{reviewTitle}</Text>
                  <Text style={styles.tlTime}>{reviewTime}</Text>
                  {view.state === 'rejected' && flag.reject_reason ? (
                    <Text style={styles.tlNote}>{flag.reject_reason}</Text>
                  ) : null}
                </View>
              </View>
            </View>

            <View style={styles.infoBanner}>
              <Ionicons name="information-circle-outline" size={14} color={C.textHint} style={{ marginTop: 1 }} />
              <Text style={styles.infoBannerText}>
                Only your lecturer can confirm a flag. You can flag a class once, while it is running.
              </Text>
            </View>
          </>
        )}
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  empty: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    color: C.textSub,
    textAlign: 'center',
  },
  hero: {
    alignItems: 'center',
    backgroundColor: C.card,
    paddingVertical: 28,
    paddingHorizontal: 24,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  heroIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  heroLabel: {
    fontSize: 18,
    fontWeight: '700',
    color: C.text,
  },
  heroSub: {
    fontSize: 13,
    color: C.textSub,
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 20,
  },
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    margin: 16,
    marginBottom: 0,
    padding: 16,
  },
  cardLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 12,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
    gap: 12,
  },
  detailKey: {
    fontSize: 12,
    color: C.textSub,
  },
  detailVal: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
    textAlign: 'right',
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  timeline: {
    paddingHorizontal: 20,
  },
  tlItem: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 14,
  },
  tlDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tlContent: {
    flex: 1,
  },
  tlTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  tlTime: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 1,
  },
  tlNote: {
    fontSize: 12,
    color: C.textSub,
    lineHeight: 18,
    marginTop: 4,
  },
  infoBanner: {
    flexDirection: 'row',
    gap: 8,
    margin: 16,
    backgroundColor: C.gray50,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 10,
    padding: 12,
  },
  infoBannerText: {
    flex: 1,
    fontSize: 12,
    color: C.textSub,
    lineHeight: 18,
  },
})
