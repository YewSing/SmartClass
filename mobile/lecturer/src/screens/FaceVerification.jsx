import { useCallback, useState } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, StyleSheet, RefreshControl, ActivityIndicator,
  Modal, Pressable,
} from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import AuthImage from '../components/AuthImage'
import * as api from '../services/api'
import {
  reasonLabel, percent, matricCheck, splitImages, rejectReasonError, REJECT_REASON_MAX,
} from '../services/faceReview'
import { C } from '../theme'

function when(iso) {
  return new Date(iso).toLocaleString('en-MY', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur',
  })
}

function Fact({ label, value, ok }) {
  return (
    <View style={styles.fact}>
      <Text style={styles.factLabel}>{label}</Text>
      <View style={styles.factValueRow}>
        {ok !== undefined && (
          <Ionicons name={ok ? 'checkmark-circle' : 'alert-circle'} size={14} color={ok ? C.green : C.orange} />
        )}
        <Text style={styles.factValue}>{value}</Text>
      </View>
    </View>
  )
}

// One pending submission: the student's selfies next to their card, what the checks found,
// and the decision. A rejection needs a reason the student will see (FR-114).
function SubmissionCard({ sub, onDecided }) {
  const { showToast } = useLecturer()
  const { selfies, card } = splitImages(sub.images)
  const matric = matricCheck(sub)
  const [mode, setMode] = useState(null)        // null | 'approve' | 'reject'
  const [reason, setReason] = useState('')
  const [reasonErr, setReasonErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const [zoom, setZoom] = useState(null)        // the photo shown full screen

  const decide = async () => {
    if (mode === 'reject') {
      const err = rejectReasonError(reason)
      setReasonErr(err)
      if (err) return
    }
    setBusy(true)
    try {
      if (mode === 'approve') await api.approveFaceSubmission(sub.id)
      else await api.rejectFaceSubmission(sub.id, reason)
      showToast(mode === 'approve' ? `Approved ${sub.student_name}` : `Rejected ${sub.student_name}`, 'success')
      onDecided(sub.id)
    } catch (e) {
      // 409: someone else decided it first, or the student withdrew consent meanwhile
      showToast(e.message, 'error')
      if (e.status === 409 || e.status === 404) onDecided(sub.id, { reload: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <View style={styles.card} testID="face-submission">
      <View style={styles.cardHead}>
        <View style={styles.flex}>
          <Text style={styles.name} testID="face-submission-name">{sub.student_name}</Text>
          <Text style={styles.meta}>{sub.matric_no} · {sub.courses.join(', ') || '—'}</Text>
        </View>
        <Text style={styles.meta}>{when(sub.submitted_at)}</Text>
      </View>

      <View style={styles.photos}>
        <View style={styles.selfieCol}>
          <Text style={styles.photoLabel}>Selfies</Text>
          <View style={styles.selfieRow}>
            {selfies.map(img => (
              <TouchableOpacity key={img.id} style={styles.selfie} onPress={() => setZoom(img)}>
                <AuthImage path={img.url} style={styles.fill}
                  testID="face-selfie" accessibilityLabel={`Selfie ${img.position + 1}`} />
              </TouchableOpacity>
            ))}
          </View>
        </View>
        <View style={styles.cardCol}>
          <Text style={styles.photoLabel}>Card</Text>
          {card ? (
            <TouchableOpacity style={styles.cardPhoto} onPress={() => setZoom(card)}>
              <AuthImage path={card.url} style={styles.fill} testID="face-card-photo" accessibilityLabel="Matric card" />
            </TouchableOpacity>
          ) : <Text style={styles.meta}>No card photo</Text>}
        </View>
      </View>
      <Text style={styles.hint}>Tap a photo to enlarge it</Text>
      <Modal visible={zoom !== null} transparent animationType="fade" onRequestClose={() => setZoom(null)}>
        <Pressable style={styles.zoomBackdrop} onPress={() => setZoom(null)} accessibilityLabel="Close photo">
          {zoom && <AuthImage path={zoom.url} style={styles.zoomPhoto} testID="face-zoom-photo" />}
          <Text style={styles.zoomClose}>Tap anywhere to close</Text>
        </Pressable>
      </Modal>

      <View style={styles.facts}>
        <Fact label="Account matric" value={sub.matric_no} />
        <Fact label="Card matric" value={matric.text} ok={matric.ok} />
        <Fact label="Face match" value={percent(sub.face_score)} />
        <Fact label="Name on card" value={percent(sub.name_score)} />
      </View>

      {sub.check_reasons.length > 0 && (
        <View style={styles.reasons}>
          {sub.check_reasons.map(r => (
            <View key={r} style={styles.reasonChip}>
              <Text style={styles.reasonText}>{reasonLabel(r)}</Text>
            </View>
          ))}
        </View>
      )}

      {mode === 'reject' && (
        <View style={styles.rejectBox}>
          <Text style={styles.photoLabel}>Reason (the student sees this)</Text>
          <TextInput
            style={[styles.input, reasonErr && styles.inputErr]}
            value={reason}
            onChangeText={t => { setReason(t); if (reasonErr) setReasonErr(null) }}
            placeholder="e.g. The card photo is someone else's card"
            placeholderTextColor={C.textHint}
            maxLength={REJECT_REASON_MAX + 50}
            multiline
            testID="face-reject-reason"
          />
          {reasonErr && <Text style={styles.errText}>{reasonErr}</Text>}
        </View>
      )}
      {mode === 'approve' && (
        <Text style={styles.confirmText}>
          Approve? The student's face data is stored and used for attendance.
        </Text>
      )}

      <View style={styles.actions}>
        {mode === null ? (
          <>
            <TouchableOpacity style={[styles.btn, styles.btnReject]} onPress={() => setMode('reject')}>
              <Ionicons name="close" size={16} color={C.red} />
              <Text style={[styles.btnText, { color: C.red }]}>Reject</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btn, styles.btnApprove]} onPress={() => setMode('approve')}>
              <Ionicons name="checkmark" size={16} color="#fff" />
              <Text style={[styles.btnText, { color: '#fff' }]}>Approve</Text>
            </TouchableOpacity>
          </>
        ) : (
          <>
            <TouchableOpacity style={[styles.btn, styles.btnCancel]} disabled={busy}
              onPress={() => { setMode(null); setReasonErr(null) }}>
              <Text style={[styles.btnText, { color: C.text }]}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.btn, mode === 'approve' ? styles.btnApprove : styles.btnRejectSolid, busy && styles.btnBusy]}
              disabled={busy}
              onPress={decide}
            >
              {busy
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={[styles.btnText, { color: '#fff' }]}>
                    {mode === 'approve' ? 'Confirm approve' : 'Confirm reject'}
                  </Text>}
            </TouchableOpacity>
          </>
        )}
      </View>
    </View>
  )
}

// Lecturers open this from Home. Administrators get it as a tab of the admin area, where it lists
// every pending submission, including students no lecturer reviewed (FR-117 fallback).
export default function FaceVerification({ navigation }) {
  const { state } = useLecturer()
  const isAdmin = !!state.lecturer?.isAdmin
  const [subs, setSubs] = useState(null)       // null while the first load runs
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      setSubs(await api.getPendingFaceSubmissions())
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  // Reload whenever the screen is shown: other lecturers may have decided some meanwhile
  useFocusEffect(useCallback(() => { load() }, [load]))

  const onRefresh = async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }

  const onDecided = (id, { reload = false } = {}) => {
    setSubs(list => (list ?? []).filter(s => s.id !== id))
    if (reload) load()
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Face verification"
        sub={isAdmin ? 'Every enrolment waiting for review' : 'Enrolments that need your review'}
        onBack={navigation.canGoBack() ? () => navigation.goBack() : undefined}
      />
      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        <Text style={styles.intro}>
          These students' photos didn't pass the automatic check. Compare the selfies with the card:
          approve if they show the same person and the card is theirs. Photos are deleted once you decide.
          {isAdmin ? ' Lecturers usually review their own students; this list also covers anyone they haven\'t.' : ''}
        </Text>
        {error && (
          <TouchableOpacity style={styles.errorBox} onPress={load}>
            <Text style={styles.errText}>{error}</Text>
            <Text style={styles.retry}>Tap to retry</Text>
          </TouchableOpacity>
        )}
        {subs === null && !error && <ActivityIndicator color={C.primary} style={{ marginTop: 24 }} />}
        {subs?.length === 0 && (
          <View style={styles.empty}>
            <Ionicons name="checkmark-done-circle-outline" size={40} color={C.green} />
            <Text style={styles.emptyText}>No submissions waiting for review</Text>
          </View>
        )}
        {subs?.map(s => <SubmissionCard key={s.id} sub={s} onDecided={onDecided} />)}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32, gap: 12 },
  intro: { fontSize: 13, color: C.textSub, lineHeight: 19 },
  card: {
    backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, gap: 12,
  },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  name: { fontSize: 15, fontWeight: '700', color: C.text },
  meta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  // Selfies and card side by side at every width, so faces can be compared at a glance
  photos: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  selfieCol: { flex: 3, gap: 6 },
  cardCol: { flex: 2, gap: 6 },
  photoLabel: { fontSize: 11, fontWeight: '700', color: C.textHint, textTransform: 'uppercase', letterSpacing: 0.6 },
  selfieRow: { flexDirection: 'row', gap: 4 },
  selfie: { flex: 1, aspectRatio: 3 / 4, borderRadius: 6, overflow: 'hidden', backgroundColor: C.gray100 },
  cardPhoto: { width: '100%', aspectRatio: 1.586, borderRadius: 6, overflow: 'hidden', backgroundColor: C.gray100 },
  fill: { width: '100%', height: '100%' },
  hint: { fontSize: 11, color: C.textHint, marginTop: -6 },
  zoomBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.9)', alignItems: 'center', justifyContent: 'center', padding: 16, gap: 12,
  },
  zoomPhoto: { width: '100%', maxWidth: 900, height: '80%', backgroundColor: 'transparent' },
  zoomClose: { color: '#fff', fontSize: 13 },
  facts: { flexDirection: 'row', flexWrap: 'wrap', rowGap: 8 },
  fact: { width: '50%' },
  factLabel: { fontSize: 11, color: C.textSub },
  factValueRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 1 },
  factValue: { fontSize: 14, fontWeight: '600', color: C.text },
  reasons: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  reasonChip: { backgroundColor: C.orangeLt, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3 },
  reasonText: { fontSize: 12, color: C.orangeDk, fontWeight: '500' },
  rejectBox: { gap: 6 },
  input: {
    borderWidth: 1, borderColor: C.border, borderRadius: 8, padding: 10, minHeight: 64,
    fontSize: 14, color: C.text, textAlignVertical: 'top', backgroundColor: C.card,
  },
  inputErr: { borderColor: C.red },
  errText: { fontSize: 12, color: C.red },
  confirmText: { fontSize: 13, color: C.text },
  actions: { flexDirection: 'row', gap: 8, justifyContent: 'flex-end' },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: 8, minWidth: 96,
  },
  btnText: { fontSize: 14, fontWeight: '700' },
  btnApprove: { backgroundColor: C.green },
  btnReject: { backgroundColor: C.redLt, borderWidth: 1, borderColor: C.red },
  btnRejectSolid: { backgroundColor: C.red },
  btnCancel: { backgroundColor: C.gray100 },
  btnBusy: { opacity: 0.6 },
  errorBox: { backgroundColor: C.redLt, borderRadius: 8, padding: 12, gap: 4 },
  retry: { fontSize: 12, color: C.primary, fontWeight: '600' },
  empty: { alignItems: 'center', gap: 8, paddingVertical: 32 },
  emptyText: { fontSize: 14, color: C.textSub },
})
