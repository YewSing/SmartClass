import {
  View, Text, ScrollView, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { C } from '../theme'

const DETAILS = [
  { label: 'Session',   value: 'Lec 8 — Requirements Eng.' },
  { label: 'Date',      value: '29 Apr 2025' },
  { label: 'Reason',    value: 'Face recognition did not detect me' },
  { label: 'Submitted', value: '25 May 2025, 10:10 AM' },
]

export default function AttReportStatus({ navigation }) {
  return (
    <View style={styles.flex}>
      <Topbar title="Report Status" sub="Lec 8 · WIA2005" onBack={() => navigation.goBack()} />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <View style={styles.heroIcon}>
            <Ionicons name="hourglass-outline" size={26} color={C.yellow} />
          </View>
          <Text style={styles.heroLabel}>Under Review</Text>
          <Text style={styles.heroSub}>
            Your report has been received and is awaiting review by your lecturer.
          </Text>
        </View>

        {/* Report details */}
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Report Details</Text>
          {DETAILS.map(row => (
            <View key={row.label} style={styles.detailRow}>
              <Text style={styles.detailKey}>{row.label}</Text>
              <Text style={styles.detailVal}>{row.value}</Text>
            </View>
          ))}
          <View style={styles.detailRow}>
            <Text style={styles.detailKey}>Ref. No.</Text>
            <Text style={styles.refNo}>RPT-2025-04290012</Text>
          </View>
        </View>

        {/* Progress timeline */}
        <Text style={styles.sectionTitle}>Progress</Text>
        <View style={styles.timeline}>
          <View style={styles.tlItem}>
            <View style={[styles.tlDot, { backgroundColor: C.green }]}>
              <Ionicons name="checkmark" size={12} color="#fff" />
            </View>
            <View style={styles.tlContent}>
              <Text style={styles.tlTitle}>Report Submitted</Text>
              <Text style={styles.tlTime}>25 May 2025 · 10:10 AM</Text>
            </View>
          </View>

          <View style={styles.tlItem}>
            <View style={[styles.tlDot, { backgroundColor: C.yellow }]}>
              <Ionicons name="time-outline" size={12} color="#fff" />
            </View>
            <View style={styles.tlContent}>
              <Text style={styles.tlTitle}>Under Review</Text>
              <Text style={styles.tlTime}>Pending · Awaiting lecturer action</Text>
              <Text style={styles.tlNote}>
                Your report has been forwarded to Dr. Tan Wei Lin for review. You will be notified once a decision is made.
              </Text>
            </View>
          </View>

          <View style={styles.tlItem}>
            <View style={[styles.tlDot, { backgroundColor: C.gray300 }]}>
              <Ionicons name="checkmark-done" size={12} color="#fff" />
            </View>
            <View style={[styles.tlContent, { opacity: 0.45 }]}>
              <Text style={styles.tlTitle}>Resolved</Text>
              <Text style={styles.tlTime}>Awaiting review completion</Text>
            </View>
          </View>
        </View>

        <View style={styles.infoBanner}>
          <Ionicons name="information-circle-outline" size={14} color={C.textHint} style={{ marginTop: 1 }} />
          <Text style={styles.infoBannerText}>
            Resolution typically takes 1–3 business days. Your attendance status will be updated automatically if the report is approved.
          </Text>
        </View>
        <View style={{ height: 24 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
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
    backgroundColor: C.yellowLt,
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
  refNo: {
    fontSize: 12,
    fontWeight: '700',
    color: C.textHint,
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
