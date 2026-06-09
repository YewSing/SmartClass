import { useState, useEffect } from 'react'
import { changePassword } from '../services/api'
import {
  Modal, View, Text, TextInput, TouchableOpacity, TouchableWithoutFeedback,
  ScrollView, StyleSheet, Dimensions,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import { navigateTo } from '../navigation/navigationRef'
import { C } from '../theme'
import Badge from './Badge'

// ─── Sheet wrapper ─────────────────────────────────────────────────────────────

function Sheet({ visible, onClose, children }) {
  const { bottom } = useSafeAreaInsets()
  return (
    <Modal transparent animationType="slide" visible={visible} onRequestClose={onClose}>
      <View style={styles.overlay}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={StyleSheet.absoluteFillObject} />
        </TouchableWithoutFeedback>
        <View style={[styles.sheet, { paddingBottom: bottom }]}>
          <View style={styles.handle} />
          <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled" bounces={false}>
            {children}
          </ScrollView>
        </View>
      </View>
    </Modal>
  )
}

// ─── Reusable sub-components ──────────────────────────────────────────────────

function ModalTitle({ children }) {
  return <Text style={styles.modalTitle}>{children}</Text>
}

function ModalSub({ children }) {
  return <Text style={styles.modalSub}>{children}</Text>
}

function Divider() {
  return <View style={styles.divider} />
}

function BtnPrimary({ label, onPress, icon, disabled }) {
  return (
    <TouchableOpacity
      style={[styles.btn, styles.btnPrimary, disabled && styles.btnDisabled]}
      onPress={onPress}
      disabled={disabled}
    >
      {icon && <Ionicons name={icon} size={16} color="#fff" style={{ marginRight: 6 }} />}
      <Text style={styles.btnPrimaryText}>{label}</Text>
    </TouchableOpacity>
  )
}

function BtnOutline({ label, onPress, icon }) {
  return (
    <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={onPress}>
      {icon && <Ionicons name={icon} size={16} color={C.text} style={{ marginRight: 6 }} />}
      <Text style={styles.btnOutlineText}>{label}</Text>
    </TouchableOpacity>
  )
}

function BtnDanger({ label, onPress, icon }) {
  return (
    <TouchableOpacity style={[styles.btn, styles.btnDanger]} onPress={onPress}>
      {icon && <Ionicons name={icon} size={16} color="#fff" style={{ marginRight: 6 }} />}
      <Text style={styles.btnPrimaryText}>{label}</Text>
    </TouchableOpacity>
  )
}

function BtnRow({ children }) {
  return <View style={styles.btnRow}>{children}</View>
}

// ─── ConfusionResetModal ───────────────────────────────────────────────────────

function ConfusionResetModal({ visible, onClose }) {
  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Reset Confusion Counter</ModalTitle>
      <Text style={styles.bodyText}>
        This will reset the confusion counter to 0%. Students' "I Don't Understand" signals will be cleared. Historical IDU logs are preserved.
      </Text>
      <View style={styles.warningBox}>
        <Ionicons name="warning-outline" size={14} color={C.yellowDk} />
        <Text style={[styles.warningText, { marginLeft: 6 }]}>
          Current rate: <Text style={{ fontWeight: '700' }}>34%</Text> · 8 signals this session
        </Text>
      </View>
      <BtnRow>
        <BtnOutline label="Cancel" onPress={onClose} />
        <BtnPrimary label="Confirm Reset" icon="refresh-outline" onPress={onClose} />
      </BtnRow>
    </Sheet>
  )
}

// ─── QuizModal ─────────────────────────────────────────────────────────────────

function QuizModal({ visible, onClose, quiz }) {
  if (!quiz) return null

  if (quiz.status === 'active') return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.rowBetween}>
        <Badge variant="blue" dot>Active</Badge>
        <Text style={styles.metaText}>Today, {quiz.time} · {quiz.timer}</Text>
      </View>
      <Text style={styles.quizQuestion}>{quiz.question}</Text>
      <View style={styles.optionBox}>
        {quiz.options.map((o, i) => (
          <Text key={i} style={styles.optionText}>
            {String.fromCharCode(65 + i)}. {i === quiz.correct ? <Text style={{ fontWeight: '700' }}>{o} ✓</Text> : o}
          </Text>
        ))}
      </View>
      <View style={[styles.rowGap, { marginBottom: 14 }]}>
        <View style={styles.greenDot} />
        <Text style={styles.metaText}>Answered: {quiz.answered} / {quiz.total} students</Text>
      </View>
      <BtnRow>
        <BtnDanger label="Close Early" icon="stop-outline" onPress={onClose} />
        <BtnPrimary label="Live Results" icon="bar-chart-outline" onPress={() => { onClose(); navigateTo('LiveResults') }} />
      </BtnRow>
      <Divider />
      <BtnOutline label="Dismiss" onPress={onClose} />
    </Sheet>
  )

  if (quiz.status === 'closed') return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.rowBetween}>
        <Badge variant="gray">Closed</Badge>
        <Text style={styles.metaText}>Today, {quiz.time} · {quiz.timer}</Text>
      </View>
      <Text style={styles.quizQuestion}>{quiz.question}</Text>
      <View style={styles.statsRow}>
        <View style={styles.statCell}>
          <Text style={[styles.statNum, { color: C.green }]}>{quiz.correct_count}</Text>
          <Text style={[styles.statLbl, { color: C.greenDk }]}>Correct</Text>
        </View>
        <View style={styles.statCell}>
          <Text style={[styles.statNum, { color: C.red }]}>{quiz.wrong_count}</Text>
          <Text style={[styles.statLbl, { color: C.redDk }]}>Incorrect</Text>
        </View>
        <View style={styles.statCell}>
          <Text style={[styles.statNum, { color: C.gray400 }]}>{quiz.unanswered_count}</Text>
          <Text style={[styles.statLbl, { color: C.gray500 }]}>Unanswered</Text>
        </View>
      </View>
      <BtnRow>
        <BtnOutline label="View Results" icon="bar-chart-outline" onPress={() => { onClose(); navigateTo('ResultsClosed') }} />
        <BtnPrimary label="Breakdown" icon="list-outline" onPress={() => { onClose(); navigateTo('Breakdown') }} />
      </BtnRow>
      <Divider />
      <BtnOutline label="Dismiss" onPress={onClose} />
    </Sheet>
  )

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.rowBetween}>
        <Badge variant="yellow">Draft</Badge>
        <Text style={styles.metaText}>Today, {quiz.time}</Text>
      </View>
      <Text style={styles.quizQuestion}>{quiz.question}</Text>
      <View style={styles.optionBox}>
        {quiz.options.map((o, i) => (
          <Text key={i} style={styles.optionText}>
            {String.fromCharCode(65 + i)}. {i === quiz.correct ? <Text style={{ fontWeight: '700' }}>{o} ✓</Text> : o}
          </Text>
        ))}
      </View>
      <BtnPrimary label="Push to All Desks" icon="send-outline" onPress={onClose} />
      <View style={{ height: 8 }} />
      <BtnRow>
        <BtnOutline label="Edit" icon="create-outline" onPress={() => { onClose(); navigateTo('CreateQuiz') }} />
        <BtnDanger label="Delete" icon="trash-outline" onPress={onClose} />
      </BtnRow>
      <Divider />
      <BtnOutline label="Dismiss" onPress={onClose} />
    </Sheet>
  )
}

// ─── StudentModal ──────────────────────────────────────────────────────────────

function StudentModal({ visible, onClose, data, overrideStudent }) {
  const [busy, setBusy] = useState(false)

  useEffect(() => { if (visible) setBusy(false) }, [visible])

  if (!data) return null

  const avatarStyle = data.status === 'present'
    ? { bg: C.blueLt, color: C.blueDk }
    : data.status === 'absent'
    ? { bg: C.redLt, color: C.redDk }
    : { bg: C.orangeLt, color: C.orangeDk }

  const inits = data.initials ?? data.name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()

  const handleOverride = async (newStatus) => {
    setBusy(true)
    try {
      await overrideStudent(data.recordId, newStatus, data.studentId)
      onClose()
    } catch {
      setBusy(false)
    }
  }

  const statusVariant = data.status === 'present' ? 'green' : data.status === 'absent' ? 'red' : 'orange'
  const statusLabel = data.status === 'present' ? 'Present' : data.status === 'absent' ? 'Absent' : 'Unidentified'

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.studentHeader}>
        <View style={[styles.avatarLg, { backgroundColor: avatarStyle.bg }]}>
          <Text style={[styles.avatarLgText, { color: avatarStyle.color }]}>{inits}</Text>
        </View>
        <View style={styles.studentHeaderInfo}>
          <Text style={styles.studentName}>{data.name}</Text>
          <Text style={styles.studentId}>{data.id}</Text>
        </View>
        <Badge variant={statusVariant} dot>{statusLabel}</Badge>
      </View>
      {data.status === 'present'
        ? <BtnDanger label="Mark Absent" icon="close" disabled={busy} onPress={() => handleOverride('absent')} />
        : <BtnPrimary label="Mark Present" icon="checkmark" disabled={busy} onPress={() => handleOverride('present')} />
      }
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
}

// ─── ExportModal ───────────────────────────────────────────────────────────────

function ExportModal({ visible, onClose, data }) {
  const { exportCsv, closeModal } = useLecturer()
  const [busy, setBusy] = useState(false)

  const handleExport = async () => {
    if (busy || !data) return
    setBusy(true)
    try {
      await exportCsv(data)
      closeModal()
    } catch {
      // showToast already called inside exportCsv
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Export Attendance</ModalTitle>
      <ModalSub>{data?.subtitle ?? ''}</ModalSub>
      <View style={styles.exportSummaryCard}>
        <View style={styles.exportSummaryRow}>
          <Ionicons name="calendar-outline" size={16} color={C.primary} />
          <Text style={styles.exportSummaryText}>
            {data?.sessionCount != null
              ? `${data.sessionCount} session${data.sessionCount !== 1 ? 's' : ''}`
              : '—'}
          </Text>
        </View>
        <View style={styles.exportSummaryRow}>
          <Ionicons name="people-outline" size={16} color={C.primary} />
          <Text style={styles.exportSummaryText}>
            {data?.studentCount != null ? `${data.studentCount} students enrolled` : '—'}
          </Text>
        </View>
      </View>
      <BtnPrimary
        label={busy ? 'Exporting…' : 'Export CSV'}
        icon={busy ? undefined : 'download-outline'}
        onPress={handleExport}
        disabled={busy || !data}
      />
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
}

// ─── OverrideLightsModal ───────────────────────────────────────────────────────

function OverrideLightsModal({ visible, onClose }) {
  const [mode, setMode] = useState('Auto')
  const [on, setOn] = useState(true)
  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={[styles.rowGap, { marginBottom: 16 }]}>
        <View style={[styles.actIcon, { backgroundColor: C.yellowLt }]}>
          <Ionicons name="bulb-outline" size={20} color={C.yellow} />
        </View>
        <ModalTitle>Lights Override</ModalTitle>
      </View>
      <Text style={styles.overrideGroupLabel}>Control Mode</Text>
      <View style={styles.pillRow}>
        {['Auto', 'Manual'].map(m => (
          <TouchableOpacity key={m} style={[styles.pill, mode === m && styles.pillActive]} onPress={() => setMode(m)}>
            <Text style={[styles.pillText, mode === m && styles.pillTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={styles.overrideGroupLabel}>State</Text>
      <View style={styles.pillRow}>
        <TouchableOpacity style={[styles.pill, on && styles.pillActive]} onPress={() => setOn(true)}>
          <Text style={[styles.pillText, on && styles.pillTextActive]}>ON</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.pill, !on && styles.pillDanger]} onPress={() => setOn(false)}>
          <Text style={[styles.pillText, !on && styles.pillTextActive]}>OFF</Text>
        </TouchableOpacity>
      </View>
      <BtnPrimary label="Confirm Override" icon="checkmark" onPress={onClose} />
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
}

// ─── OverrideACModal ───────────────────────────────────────────────────────────

function OverrideACModal({ visible, onClose }) {
  const [mode, setMode] = useState('Auto')
  const [on, setOn] = useState(true)
  const [temp, setTemp] = useState(23)

  const presets = [
    { v: 18, label: '18°C', sub: 'Very cool', bg: C.blueLt, color: C.blueDk },
    { v: 23, label: '23°C', sub: 'Recommended', bg: C.blueLt, color: C.blueDk },
    { v: 26, label: '26°C', sub: 'Energy saving', bg: C.yellowLt, color: C.yellowDk },
  ]

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={[styles.rowGap, { marginBottom: 16 }]}>
        <View style={[styles.actIcon, { backgroundColor: C.blueLt }]}>
          <Ionicons name="snow-outline" size={20} color={C.primary} />
        </View>
        <ModalTitle>AC Override</ModalTitle>
      </View>
      <Text style={styles.overrideGroupLabel}>Control Mode</Text>
      <View style={styles.pillRow}>
        {['Auto', 'Manual'].map(m => (
          <TouchableOpacity key={m} style={[styles.pill, mode === m && styles.pillActive]} onPress={() => setMode(m)}>
            <Text style={[styles.pillText, mode === m && styles.pillTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={styles.overrideGroupLabel}>State</Text>
      <View style={styles.pillRow}>
        <TouchableOpacity style={[styles.pill, on && styles.pillActive]} onPress={() => setOn(true)}>
          <Text style={[styles.pillText, on && styles.pillTextActive]}>ON</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.pill, !on && styles.pillDanger]} onPress={() => setOn(false)}>
          <Text style={[styles.pillText, !on && styles.pillTextActive]}>OFF</Text>
        </TouchableOpacity>
      </View>
      <Text style={styles.overrideGroupLabel}>Target Temperature</Text>
      <View style={styles.tempRow}>
        <TouchableOpacity
          style={styles.tempBtn}
          onPress={() => setTemp(t => Math.max(16, t - 1))}
        >
          <Ionicons name="remove" size={20} color={C.primary} />
        </TouchableOpacity>
        <Text style={styles.tempDisplay}>{temp}<Text style={styles.tempUnit}> °C</Text></Text>
        <TouchableOpacity
          style={styles.tempBtn}
          onPress={() => setTemp(t => Math.min(30, t + 1))}
        >
          <Ionicons name="add" size={20} color={C.primary} />
        </TouchableOpacity>
      </View>
      <View style={styles.presetRow}>
        {presets.map(p => (
          <TouchableOpacity
            key={p.v}
            style={[styles.presetCard, { backgroundColor: p.bg }, temp === p.v && styles.presetCardSelected]}
            onPress={() => setTemp(p.v)}
          >
            <Text style={[styles.presetLabel, { color: p.color }]}>{p.label}</Text>
            <Text style={[styles.presetSub, { color: p.color }]}>{p.sub}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.infoBox}>
        <Ionicons name="information-circle-outline" size={14} color={C.blueDk} />
        <Text style={[styles.infoText, { marginLeft: 6 }]}>
          In Auto mode, AC activates when occupancy ≥ 5. Temperature setpoint applies in both modes.
        </Text>
      </View>
      <BtnPrimary label="Confirm Override" icon="checkmark" onPress={onClose} />
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
}

// ─── ChangePasswordModal ───────────────────────────────────────────────────────

function ChangePasswordModal({ visible, onClose }) {
  const { showToast } = useLecturer()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const reset = () => { setCurrent(''); setNext(''); setConfirm(''); setErr('') }

  const handleClose = () => { reset(); onClose() }

  const handleSubmit = async () => {
    setErr('')
    if (!current || !next || !confirm) { setErr('All fields are required.'); return }
    if (next.length < 8) { setErr('New password must be at least 8 characters.'); return }
    if (next !== confirm) { setErr('New passwords do not match.'); return }
    setLoading(true)
    try {
      await changePassword(current, next)
      showToast('Password updated successfully.', 'success')
      handleClose()
    } catch (e) {
      setErr(e.message || 'Failed to update password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Sheet visible={visible} onClose={handleClose}>
      <ModalTitle>Change Password</ModalTitle>
      <ModalSub>Your new password must be at least 8 characters.</ModalSub>
      {err ? <Text style={styles.errText}>{err}</Text> : null}
      <Text style={styles.inputLabel}>Current Password</Text>
      <TextInput
        style={styles.input}
        placeholder="Enter current password"
        placeholderTextColor={C.textHint}
        secureTextEntry
        value={current}
        onChangeText={setCurrent}
      />
      <Text style={styles.inputLabel}>New Password</Text>
      <TextInput
        style={styles.input}
        placeholder="Enter new password"
        placeholderTextColor={C.textHint}
        secureTextEntry
        value={next}
        onChangeText={setNext}
      />
      <Text style={styles.inputLabel}>Confirm New Password</Text>
      <TextInput
        style={styles.input}
        placeholder="Re-enter new password"
        placeholderTextColor={C.textHint}
        secureTextEntry
        value={confirm}
        onChangeText={setConfirm}
      />
      <BtnPrimary label={loading ? 'Updating…' : 'Update Password'} icon="checkmark" onPress={handleSubmit} disabled={loading} />
      <Divider />
      <BtnOutline label="Cancel" onPress={handleClose} />
    </Sheet>
  )
}

// ─── SignOutModal ──────────────────────────────────────────────────────────────

function SignOutModal({ visible, onClose, onConfirm }) {
  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Sign Out</ModalTitle>
      <Text style={[styles.bodyText, { marginBottom: 18 }]}>
        Are you sure you want to sign out? Active sessions will continue running in the background.
      </Text>
      <BtnRow>
        <BtnOutline label="Cancel" onPress={onClose} />
        <BtnDanger label="Sign Out" icon="log-out-outline" onPress={onConfirm} />
      </BtnRow>
    </Sheet>
  )
}

// ─── ModalRouter ───────────────────────────────────────────────────────────────

export default function ModalRouter() {
  const { state, closeModal, overrideStudent, logout } = useLecturer()
  const { modal } = state

  const type = modal?.type
  const data = modal?.data

  const handleSignOut = async () => {
    await logout()
    closeModal()
  }

  return (
    <>
      <ConfusionResetModal visible={type === 'confusion-reset'} onClose={closeModal} />
      <QuizModal visible={type === 'quiz'} onClose={closeModal} quiz={type === 'quiz' ? data : null} />
      <StudentModal visible={type === 'student'} onClose={closeModal} data={type === 'student' ? data : null} overrideStudent={overrideStudent} />
      <ExportModal visible={type === 'export'} onClose={closeModal} data={data} />
      <OverrideLightsModal visible={type === 'override-lights'} onClose={closeModal} />
      <OverrideACModal visible={type === 'override-ac'} onClose={closeModal} />
      <ChangePasswordModal visible={type === 'change-password'} onClose={closeModal} />
      <SignOutModal visible={type === 'signout'} onClose={closeModal} onConfirm={handleSignOut} />
    </>
  )
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: C.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingTop: 12,
    maxHeight: Dimensions.get('window').height * 0.85,
  },
  handle: {
    width: 40,
    height: 4,
    backgroundColor: C.gray300,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 18,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: C.text,
    marginBottom: 6,
  },
  modalSub: {
    fontSize: 13,
    color: C.textSub,
    marginBottom: 14,
  },
  bodyText: {
    fontSize: 14,
    color: C.textSub,
    lineHeight: 22,
    marginBottom: 14,
  },
  divider: {
    height: 1,
    backgroundColor: C.border,
    marginVertical: 12,
  },
  btn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 13,
    borderRadius: 10,
  },
  btnPrimary: {
    backgroundColor: C.primary,
    marginBottom: 8,
  },
  btnOutline: {
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: C.card,
    marginBottom: 8,
  },
  btnDanger: {
    backgroundColor: C.red,
    marginBottom: 8,
  },
  btnDisabled: {
    opacity: 0.5,
  },
  btnPrimaryText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#fff',
  },
  btnOutlineText: {
    fontSize: 15,
    fontWeight: '600',
    color: C.text,
  },
  btnRow: {
    flexDirection: 'row',
    gap: 8,
  },
  input: {
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
    color: C.text,
    marginBottom: 12,
    backgroundColor: C.bg,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: C.text,
    marginBottom: 4,
  },
  errText: {
    fontSize: 13,
    color: C.red,
    backgroundColor: C.redLt,
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  warningBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.yellowLt,
    borderWidth: 1,
    borderColor: C.yellow,
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
  },
  warningText: {
    fontSize: 13,
    color: C.yellowDk,
    flex: 1,
  },
  infoBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: C.blueLt,
    borderRadius: 8,
    padding: 10,
    marginBottom: 14,
  },
  infoText: {
    fontSize: 12,
    color: C.blueDk,
    flex: 1,
    lineHeight: 18,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  rowGap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  metaText: {
    fontSize: 12,
    color: C.textSub,
  },
  quizQuestion: {
    fontSize: 15,
    fontWeight: '700',
    color: C.text,
    lineHeight: 22,
    marginBottom: 12,
  },
  optionBox: {
    backgroundColor: C.gray50,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    gap: 8,
  },
  optionText: {
    fontSize: 13,
    color: C.text,
    lineHeight: 22,
  },
  statsRow: {
    flexDirection: 'row',
    backgroundColor: C.gray50,
    borderRadius: 8,
    padding: 12,
    marginBottom: 14,
  },
  statCell: {
    flex: 1,
    alignItems: 'center',
  },
  statNum: {
    fontSize: 20,
    fontWeight: '700',
  },
  statLbl: {
    fontSize: 11,
    fontWeight: '700',
    marginTop: 2,
  },
  greenDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: C.green,
  },
  studentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 20,
  },
  studentHeaderInfo: {
    flex: 1,
  },
  avatarLg: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarLgText: {
    fontSize: 16,
    fontWeight: '700',
  },
  studentName: {
    fontSize: 17,
    fontWeight: '700',
    color: C.text,
  },
  studentId: {
    fontSize: 13,
    color: C.textSub,
  },
  exportSummaryCard: {
    backgroundColor: C.blueLt,
    borderRadius: 10,
    padding: 14,
    marginBottom: 20,
    gap: 10,
  },
  exportSummaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  exportSummaryText: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  overrideGroupLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: C.text,
    marginBottom: 8,
    marginTop: 4,
  },
  pillRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
  },
  pill: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: C.border,
    alignItems: 'center',
  },
  pillActive: {
    backgroundColor: C.primary,
    borderColor: C.primary,
  },
  pillDanger: {
    backgroundColor: C.red,
    borderColor: C.red,
  },
  pillText: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  pillTextActive: {
    color: '#fff',
  },
  tempRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 20,
    marginBottom: 14,
  },
  tempBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    borderWidth: 1.5,
    borderColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: C.blueLt,
  },
  tempDisplay: {
    fontSize: 32,
    fontWeight: '700',
    color: C.text,
  },
  tempUnit: {
    fontSize: 18,
    fontWeight: '400',
    color: C.textSub,
  },
  presetRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 14,
  },
  presetCard: {
    flex: 1,
    borderRadius: 8,
    padding: 8,
    alignItems: 'center',
  },
  presetCardSelected: {
    borderWidth: 2,
    borderColor: C.primary,
  },
  presetLabel: {
    fontSize: 13,
    fontWeight: '700',
  },
  presetSub: {
    fontSize: 10,
    marginTop: 2,
  },
  actIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
