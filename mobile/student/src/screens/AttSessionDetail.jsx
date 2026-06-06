import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import Topbar from '../components/Topbar'
import { C } from '../theme'

const VARIANT_CONFIG = {
  present: {
    rowBg: C.greenLt, rowBorder: '#9DE8C5',
    iconBg: C.green, icon: 'checkmark', labelColor: C.greenDk, statusLabel: 'Present',
    checkinBg: C.greenLt, checkinIcon: 'log-in-outline', checkinIconColor: C.green, checkinValueColor: C.greenDk,
    infoBox: null,
  },
  absent: {
    rowBg: C.redLt, rowBorder: '#f5c5c5',
    iconBg: C.red, icon: 'close', labelColor: C.redDk, statusLabel: 'Absent',
    checkinBg: C.redLt, checkinIcon: 'log-in-outline', checkinIconColor: C.red, checkinValueColor: C.redDk,
    infoBox: {
      bg: C.redLt, border: '#f5c5c5', icon: 'alert-circle-outline', iconColor: C.red, textColor: C.redDk,
      text: 'No face detection event was recorded for this session. If you believe this is an error, contact your lecturer.',
    },
  },
  unid: {
    rowBg: C.orangeLt, rowBorder: '#F7C8A0',
    iconBg: C.orange, icon: 'help', labelColor: C.orangeDk, statusLabel: 'Unidentified',
    checkinBg: null, checkinIcon: null, checkinIconColor: null, checkinValueColor: null,
    infoBox: null,
  },
  pending: {
    rowBg: C.blueLt, rowBorder: '#93C5FD',
    iconBg: C.primary, icon: 'time-outline', labelColor: C.primary, statusLabel: 'Not Yet Detected',
    checkinBg: C.blueLt, checkinIcon: 'radio-button-on', checkinIconColor: C.primary, checkinValueColor: C.primary,
    infoBox: {
      bg: C.blueLt, border: '#93C5FD', icon: 'information-circle-outline', iconColor: C.primary, textColor: C.primary,
      text: 'This session is currently in progress. Face detection is running — your attendance status will update once you are detected.',
    },
  },
}

const REPORT_REASONS = [
  { id: 'present',     label: 'I was physically present in class' },
  { id: 'no-detect',   label: 'Face recognition did not detect me' },
  { id: 'obstruction', label: 'I had a seating obstruction (hat/glasses)' },
  { id: 'other',       label: 'Other' },
]

function InfoRow({ iconBg, icon, iconColor, label, value, valueColor, valueBold, borderless }) {
  return (
    <View style={[styles.infoRow, borderless && { borderBottomWidth: 0 }]}>
      <View style={[styles.infoIcon, { backgroundColor: iconBg }]}>
        <Ionicons name={icon} size={16} color={iconColor} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.infoLbl}>{label}</Text>
        <Text style={[styles.infoVal, valueColor && { color: valueColor }, valueBold && { fontWeight: '700' }]}>
          {value}
        </Text>
      </View>
    </View>
  )
}

export default function AttSessionDetail({ route, navigation }) {
  const { showToast, state, loadAttendanceGroups } = useStudent()
  const { attendanceGroups } = state
  const sessionId = route.params?.sessionId

  const [variant, setVariant] = useState(route.params?.variant ?? 'present')
  const [detail, setDetail]   = useState(route.params?.session ?? {})
  const [refreshing, setRefreshing] = useState(false)
  const [selectedReason, setSelectedReason] = useState('present')
  const [notes, setNotes] = useState('')

  useEffect(() => {
    if (!sessionId) return
    for (const group of attendanceGroups) {
      const found = group.sessions.find(s => s.id === sessionId)
      if (found) { setVariant(found.variant); setDetail(found.detail); break }
    }
  }, [attendanceGroups, sessionId])

  const onRefresh = useCallback(async () => {
    setRefreshing(true)
    await loadAttendanceGroups()
    setRefreshing(false)
  }, [loadAttendanceGroups])

  const cfg = VARIANT_CONFIG[variant] ?? VARIANT_CONFIG.present

  return (
    <View style={styles.flex}>
      <Topbar title="Session Detail" onBack={() => navigation.goBack()} />
      <ScrollView
        style={styles.flex}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      >
        {/* Hero */}
        <View style={styles.hero}>
          <Text style={styles.heroTitle}>{detail.title}</Text>
          <Text style={styles.heroMeta}>{detail.meta}</Text>

          <View style={[styles.statusRow, { backgroundColor: cfg.rowBg, borderColor: cfg.rowBorder }]}>
            <View style={[styles.statusIcon, { backgroundColor: cfg.iconBg }]}>
              <Ionicons name={cfg.icon} size={18} color="#fff" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.statusLabel, { color: cfg.labelColor }]}>Your Status</Text>
              <Text style={[styles.statusVal, { color: cfg.labelColor }]}>{cfg.statusLabel}</Text>
            </View>
            {detail.isLive && (
              <View style={styles.liveChip}>
                <View style={styles.liveDot} />
                <Text style={styles.liveText}>Live Now</Text>
              </View>
            )}
          </View>
        </View>

        {variant === 'unid' && (
          <View style={styles.warnBanner}>
            <Ionicons name="warning-outline" size={15} color={C.orange} style={{ marginTop: 1 }} />
            <Text style={styles.warnText}>
              Face detection picked up your presence but could not confidently match your identity. Submit a report to have your lecturer manually verify this session.
            </Text>
          </View>
        )}

        {/* Session info */}
        <Text style={styles.sectionTitle}>Session Info</Text>
        <View style={styles.card}>
          <InfoRow iconBg={C.blueLt} icon="time-outline" iconColor={C.primary}
            label="Session Time" value={detail.sessionTime ?? '—'} />

          {variant === 'present' && (
            <InfoRow iconBg={cfg.checkinBg} icon={cfg.checkinIcon} iconColor={cfg.checkinIconColor}
              label="Your Check-in Time"
              value={detail.checkinTime ? `${detail.checkinTime}${detail.checkinNote ? ` ${detail.checkinNote}` : ''}` : '—'}
              valueColor={cfg.checkinValueColor} valueBold />
          )}

          {variant === 'absent' && (
            <InfoRow iconBg={C.redLt} icon="log-in-outline" iconColor={C.red}
              label="Your Check-in Time" value="Not detected" valueColor={C.redDk} />
          )}

          {variant === 'pending' && (
            <InfoRow iconBg={C.blueLt} icon="radio-button-on" iconColor={C.primary}
              label="Your Check-in Time" value="Detecting…" valueColor={C.primary} />
          )}

          <InfoRow iconBg={C.gray100} icon="location-outline" iconColor={C.gray500}
            label="Venue" value={detail.venue ?? '—'} />
          <InfoRow iconBg={C.gray100} icon="person-outline" iconColor={C.gray500}
            label="Lecturer" value={detail.lecturer ?? '—'} borderless />
        </View>

        {cfg.infoBox && (
          <View style={[styles.infoBanner, { backgroundColor: cfg.infoBox.bg, borderColor: cfg.infoBox.border }]}>
            <Ionicons name={cfg.infoBox.icon} size={15} color={cfg.infoBox.iconColor} style={{ marginTop: 1 }} />
            <Text style={[styles.infoBannerText, { color: cfg.infoBox.textColor }]}>{cfg.infoBox.text}</Text>
          </View>
        )}

        {variant === 'present' && detail.classPresent != null && (
          <>
            <Text style={styles.sectionTitle}>Class Attendance</Text>
            <View style={styles.card}>
              <InfoRow iconBg={C.greenLt} icon="people-outline" iconColor={C.green}
                label="Present" value={`${detail.classPresent} students`} />
              <InfoRow iconBg={C.redLt} icon="person-remove-outline" iconColor={C.red}
                label="Absent" value={`${detail.classAbsent} students`} />
              <InfoRow iconBg={C.orangeLt} icon="help-circle-outline" iconColor={C.orange}
                label="Unidentified" value={`${detail.classUnid} student`} borderless />
            </View>
          </>
        )}

        {variant === 'unid' && (
          <>
            <Text style={styles.sectionTitle}>Report This Session</Text>
            <View style={{ paddingHorizontal: 16 }}>
              <Text style={styles.reportIntro}>
                Your attendance was marked as <Text style={{ color: C.orangeDk, fontWeight: '700' }}>Unidentified</Text>. Select the reason for your report:
              </Text>
              {REPORT_REASONS.map(r => {
                const selected = selectedReason === r.id
                return (
                  <TouchableOpacity
                    key={r.id}
                    style={[styles.reasonRow, selected && styles.reasonRowSelected]}
                    onPress={() => setSelectedReason(r.id)}
                  >
                    <View style={[styles.radio, selected && styles.radioSelected]}>
                      {selected && <View style={styles.radioDot} />}
                    </View>
                    <Text style={styles.reasonText}>{r.label}</Text>
                  </TouchableOpacity>
                )
              })}

              <Text style={styles.notesLabel}>Additional notes (optional)</Text>
              <View style={{ position: 'relative' }}>
                <TextInput
                  style={styles.notesInput}
                  placeholder="Describe the situation…"
                  placeholderTextColor={C.textHint}
                  value={notes}
                  onChangeText={setNotes}
                  multiline
                  numberOfLines={3}
                  textAlignVertical="top"
                />
                {notes ? (
                  <TouchableOpacity
                    onPress={() => setNotes('')}
                    style={{ position: 'absolute', top: 8, right: 8 }}
                  >
                    <Ionicons name="close-circle" size={16} color={C.textHint} />
                  </TouchableOpacity>
                ) : null}
              </View>

              <TouchableOpacity
                style={styles.submitBtn}
                onPress={() => {
                  showToast('Report submitted', 'success')
                  navigation.navigate('AttReportStatus')
                }}
              >
                <Ionicons name="flag-outline" size={16} color="#fff" style={{ marginRight: 6 }} />
                <Text style={styles.submitText}>Submit Report</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        <View style={{ height: 28 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  hero: {
    backgroundColor: C.card,
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  heroTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: C.text,
  },
  heroMeta: {
    fontSize: 13,
    color: C.textSub,
    marginTop: 4,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 14,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  statusIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusLabel: {
    fontSize: 11,
    fontWeight: '600',
  },
  statusVal: {
    fontSize: 16,
    fontWeight: '700',
    marginTop: 1,
  },
  liveChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: C.redLt,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: C.red,
  },
  liveText: {
    fontSize: 11,
    fontWeight: '700',
    color: C.redDk,
  },
  warnBanner: {
    flexDirection: 'row',
    gap: 8,
    margin: 16,
    marginBottom: 0,
    backgroundColor: C.orangeLt,
    borderWidth: 1,
    borderColor: '#F7C8A0',
    borderRadius: 10,
    padding: 12,
  },
  warnText: {
    flex: 1,
    fontSize: 12,
    color: C.orangeDk,
    lineHeight: 18,
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
  card: {
    backgroundColor: C.card,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: C.border,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  infoIcon: {
    width: 36,
    height: 36,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoLbl: {
    fontSize: 11,
    color: C.textSub,
    marginBottom: 1,
  },
  infoVal: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  infoBanner: {
    flexDirection: 'row',
    gap: 8,
    margin: 16,
    marginBottom: 0,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
  },
  infoBannerText: {
    flex: 1,
    fontSize: 12,
    lineHeight: 18,
  },
  reportIntro: {
    fontSize: 13,
    color: C.textSub,
    marginBottom: 12,
    lineHeight: 20,
  },
  reasonRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 12,
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 10,
    marginBottom: 8,
    backgroundColor: C.card,
  },
  reasonRowSelected: {
    borderColor: C.primary,
    backgroundColor: C.blueLt,
  },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: C.gray300,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioSelected: {
    borderColor: C.primary,
  },
  radioDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: C.primary,
  },
  reasonText: {
    flex: 1,
    fontSize: 13,
    color: C.text,
  },
  notesLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: C.text,
    marginTop: 10,
    marginBottom: 6,
  },
  notesInput: {
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
    color: C.text,
    backgroundColor: C.bg,
    minHeight: 76,
  },
  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: C.orange,
    borderRadius: 10,
    paddingVertical: 14,
    marginTop: 14,
  },
  submitText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },
})
