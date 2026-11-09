import { useCallback, useState } from 'react'
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Alert,
} from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { useStudent } from '../context/StudentContext'
import { getFaceConsent, getFaceEnrolment, withdrawFaceConsent } from '../services/api'
import { statusInfo, canStartEnrolment, consentNeeded } from '../services/faceEnrolment'
import { C } from '../theme'

const fmtDate = (iso) => iso
  ? new Date(iso).toLocaleString('en-MY', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Kuala_Lumpur',
  })
  : null

// Face enrolment status (FR-115) and the way into consent + capture (FR-109, FR-110)
export default function FaceEnrolment({ navigation }) {
  const { showToast } = useStudent()
  const [enrolment, setEnrolment] = useState(null)
  const [consent, setConsent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [withdrawing, setWithdrawing] = useState(false)

  const load = useCallback(async () => {
    try {
      const [e, c] = await Promise.all([getFaceEnrolment(), getFaceConsent()])
      setEnrolment(e)
      setConsent(c)
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useFocusEffect(useCallback(() => { load() }, [load]))

  const start = () => {
    navigation.navigate(consentNeeded(consent) ? 'FaceConsent' : 'FaceCapture', {
      currentVersion: consent?.current_version,
    })
  }

  const withdraw = async () => {
    setWithdrawing(true)
    try {
      await withdrawFaceConsent()
      showToast('Consent withdrawn. Your face data has been deleted.', 'success')
      await load()
    } catch (err) {
      showToast(err.message, 'error')
    } finally {
      setWithdrawing(false)
    }
  }

  const confirmWithdraw = () => Alert.alert(
    'Withdraw consent?',
    'Your face data will be deleted at once and the camera will no longer take your attendance. '
      + 'Your lecturer can still mark you present by hand.',
    [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Withdraw', style: 'destructive', onPress: withdraw },
    ],
  )

  const status = enrolment?.status ?? 'not_enrolled'
  const info = statusInfo(status)
  const submitted = fmtDate(enrolment?.submitted_at)
  const decided = fmtDate(enrolment?.decided_at)

  return (
    <View style={styles.screen}>
      <Topbar title="Face enrolment" sub="Attendance by face recognition" onBack={() => navigation.goBack()} />
      {loading ? (
        <View style={styles.center}><ActivityIndicator color={C.primary} /></View>
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          <View style={styles.card}>
            <View style={styles.row}>
              <Ionicons name="scan-outline" size={22} color={C.primary} />
              <Text style={styles.cardTitle}>Status</Text>
              <Badge variant={info.variant}>{info.label}</Badge>
            </View>
            <Text style={styles.body}>{info.text}</Text>
            {status === 'rejected' && enrolment?.reason ? (
              <View style={styles.reasonBox}>
                <Text style={styles.reasonLabel}>Reason</Text>
                <Text style={styles.reasonText}>{enrolment.reason}</Text>
              </View>
            ) : null}
            {submitted ? <Text style={styles.meta}>Submitted {submitted}</Text> : null}
            {decided && status !== 'pending_review' ? <Text style={styles.meta}>Decided {decided}</Text> : null}
          </View>

          {canStartEnrolment(status) ? (
            <TouchableOpacity style={styles.primaryBtn} onPress={start}>
              <Ionicons name="camera-outline" size={18} color="#fff" style={{ marginRight: 8 }} />
              <Text style={styles.primaryText}>{status === 'rejected' ? 'Try again' : 'Start enrolment'}</Text>
            </TouchableOpacity>
          ) : null}

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Your face data (PDPA)</Text>
            <Text style={styles.body}>
              {consent?.active
                ? `You accepted the face-data notice on ${fmtDate(consent.accepted_at)}.`
                : 'You have not given consent. Nothing about your face is stored.'}
            </Text>
            {consent?.active ? (
              <TouchableOpacity style={styles.dangerBtn} onPress={confirmWithdraw} disabled={withdrawing}>
                {withdrawing ? <ActivityIndicator color={C.red} size="small" /> : (
                  <Text style={styles.dangerText}>Withdraw consent</Text>
                )}
              </TouchableOpacity>
            ) : null}
          </View>
        </ScrollView>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  content: { padding: 16, paddingBottom: 32, gap: 12 },
  card: { backgroundColor: C.card, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: C.border, gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardTitle: { flex: 1, fontSize: 15, fontWeight: '700', color: C.text },
  body: { fontSize: 14, color: C.textSub, lineHeight: 20 },
  meta: { fontSize: 12, color: C.textHint },
  reasonBox: { backgroundColor: C.redLt, borderRadius: 8, padding: 10 },
  reasonLabel: { fontSize: 11, fontWeight: '700', color: C.redDk, textTransform: 'uppercase', marginBottom: 2 },
  reasonText: { fontSize: 14, color: C.redDk },
  primaryBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 14,
  },
  primaryText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  dangerBtn: {
    borderWidth: 1, borderColor: C.red, borderRadius: 10, paddingVertical: 10,
    alignItems: 'center', marginTop: 4,
  },
  dangerText: { color: C.red, fontSize: 14, fontWeight: '700' },
})
