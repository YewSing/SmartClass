import { useState } from 'react'
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import { C } from '../theme'
import Badge from './Badge'

// ─── Sheet wrapper ─────────────────────────────────────────────────────────────

function Sheet({ visible, onClose, children }) {
  return (
    <Modal transparent animationType="slide" visible={visible} onRequestClose={onClose}>
      <TouchableOpacity style={styles.overlay} activeOpacity={1} onPress={onClose}>
        <TouchableOpacity activeOpacity={1} onPress={() => {}}>
          <View style={styles.sheet}>
            <View style={styles.handle} />
            <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
              {children}
            </ScrollView>
          </View>
        </TouchableOpacity>
      </TouchableOpacity>
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

// ─── ForgotPasswordModal ───────────────────────────────────────────────────────

function ForgotPasswordModal({ visible, onClose }) {
  const [email, setEmail] = useState('')
  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Reset Password</ModalTitle>
      <ModalSub>Enter your university email and we'll send a reset link.</ModalSub>
      <TextInput
        style={styles.input}
        placeholder="your@um.edu.my"
        placeholderTextColor={C.textHint}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <BtnPrimary label="Send Reset Link" icon="send-outline" onPress={onClose} />
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
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

function QuizModal({ visible, onClose, quiz, navigation }) {
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
        <BtnPrimary label="Live Results" icon="bar-chart-outline" onPress={() => { onClose(); navigation.navigate('LiveResults') }} />
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
        <BtnOutline label="View Results" icon="bar-chart-outline" onPress={() => { onClose(); navigation.navigate('ResultsClosed') }} />
        <BtnPrimary label="Breakdown" icon="list-outline" onPress={() => { onClose(); navigation.navigate('Breakdown') }} />
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
        <BtnOutline label="Edit" icon="create-outline" onPress={() => { onClose(); navigation.navigate('CreateQuiz') }} />
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
  if (!data) return null

  const avatarStyle = data.status === 'present'
    ? { bg: C.blueLt, color: C.blueDk }
    : data.status === 'absent'
    ? { bg: C.redLt, color: C.redDk }
    : { bg: C.orangeLt, color: C.orangeDk }

  const inits = data.initials ?? data.name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()

  const handleOverride = async (newStatus) => {
    if (!data.recordId) { onClose(); return }
    setBusy(true)
    try {
      await overrideStudent(data.recordId, newStatus)
      onClose()
    } catch {
      setBusy(false)
    }
  }

  const statusVariant = data.status === 'present' ? 'green' : data.status === 'absent' ? 'red' : 'orange'
  const statusLabel = data.status === 'present' ? 'Present' : data.status === 'absent' ? 'Absent' : 'Unidentified'

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={[styles.rowGap, { marginBottom: 16 }]}>
        <View style={[styles.avatarLg, { backgroundColor: avatarStyle.bg }]}>
          <Text style={[styles.avatarLgText, { color: avatarStyle.color }]}>{inits}</Text>
        </View>
        <View>
          <Text style={styles.studentName}>{data.name}</Text>
          <Text style={styles.studentId}>{data.id}</Text>
        </View>
      </View>
      <View style={styles.statusBox}>
        <Text style={styles.statusBoxLabel}>Current Status</Text>
        <Badge variant={statusVariant} dot>{statusLabel}</Badge>
      </View>
      <Text style={styles.overrideLabel}>Manual Override</Text>
      <Text style={styles.overrideSub}>This override is logged with your identity and timestamp.</Text>
      <BtnRow>
        <BtnPrimary label="Mark Present" icon="checkmark" disabled={busy} onPress={() => handleOverride('present')} />
        <BtnDanger label="Mark Absent" icon="close" disabled={busy} onPress={() => handleOverride('absent')} />
      </BtnRow>
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
}

// ─── ExportModal ───────────────────────────────────────────────────────────────

function ExportModal({ visible, onClose }) {
  const [selected, setSelected] = useState('pdf')
  const options = [
    { id: 'pdf', icon: 'document-outline', iconColor: C.red, label: 'PDF', sub: 'Formatted report' },
    { id: 'csv', icon: 'document-outline', iconColor: C.green, label: 'CSV', sub: 'Raw data spreadsheet' },
  ]
  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Export Report</ModalTitle>
      <ModalSub>WIA2005 · Attendance · This month</ModalSub>
      <View style={styles.exportRow}>
        {options.map(f => (
          <TouchableOpacity
            key={f.id}
            style={[styles.exportCard, selected === f.id && styles.exportCardSelected]}
            onPress={() => setSelected(f.id)}
          >
            <Ionicons name={f.icon} size={28} color={f.iconColor} />
            <Text style={styles.exportLabel}>{f.label}</Text>
            <Text style={styles.exportSub}>{f.sub}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <BtnPrimary label={`Export ${selected.toUpperCase()}`} icon="download-outline" onPress={onClose} />
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
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Change Password</ModalTitle>
      <ModalSub>Your new password must be at least 8 characters.</ModalSub>
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
      <BtnPrimary label="Update Password" icon="checkmark" onPress={onClose} />
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
}

// ─── SessionInfoModal ──────────────────────────────────────────────────────────

function SessionInfoModal({ visible, onClose }) {
  const recent = [
    { date: '23 May 2025', sub: 'Android App · 8:05 AM' },
    { date: '21 May 2025', sub: 'Android App · 10:02 AM' },
  ]
  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Login Activity</ModalTitle>
      <View style={styles.sessionCurrentBox}>
        <Text style={styles.sessionCurrentLabel}>Current Session</Text>
        <Text style={styles.sessionCurrentDate}>Today, 24 May 2025</Text>
        <Text style={styles.sessionCurrentSub}>Logged in at 9:41 AM · Android App</Text>
      </View>
      <Text style={styles.recentLabel}>Recent Activity</Text>
      {recent.map(r => (
        <View key={r.date} style={styles.recentRow}>
          <View>
            <Text style={styles.recentDate}>{r.date}</Text>
            <Text style={styles.recentSub}>{r.sub}</Text>
          </View>
          <Badge variant="green">Success</Badge>
        </View>
      ))}
      <Divider />
      <BtnOutline label="Close" onPress={onClose} />
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

export default function ModalRouter({ navigation }) {
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
      <ForgotPasswordModal visible={type === 'forgot-password'} onClose={closeModal} />
      <ConfusionResetModal visible={type === 'confusion-reset'} onClose={closeModal} />
      <QuizModal visible={type === 'quiz'} onClose={closeModal} quiz={data} navigation={navigation} />
      <StudentModal visible={type === 'student'} onClose={closeModal} data={data} overrideStudent={overrideStudent} />
      <ExportModal visible={type === 'export'} onClose={closeModal} />
      <OverrideLightsModal visible={type === 'override-lights'} onClose={closeModal} />
      <OverrideACModal visible={type === 'override-ac'} onClose={closeModal} />
      <ChangePasswordModal visible={type === 'change-password'} onClose={closeModal} />
      <SessionInfoModal visible={type === 'session-info'} onClose={closeModal} />
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
    paddingBottom: 36,
    paddingTop: 12,
    maxHeight: '90%',
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
  statusBox: {
    backgroundColor: C.gray50,
    borderRadius: 8,
    padding: 10,
    marginBottom: 14,
    gap: 4,
  },
  statusBoxLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: C.textSub,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  overrideLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: C.text,
    marginBottom: 4,
  },
  overrideSub: {
    fontSize: 13,
    color: C.textSub,
    marginBottom: 14,
  },
  exportRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  exportCard: {
    flex: 1,
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    gap: 6,
  },
  exportCardSelected: {
    borderColor: C.primary,
    borderWidth: 2,
  },
  exportLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
  },
  exportSub: {
    fontSize: 11,
    color: C.textSub,
    textAlign: 'center',
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
  sessionCurrentBox: {
    backgroundColor: C.greenLt,
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
    gap: 3,
  },
  sessionCurrentLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: C.greenDk,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 2,
  },
  sessionCurrentDate: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
  },
  sessionCurrentSub: {
    fontSize: 12,
    color: C.textSub,
  },
  recentLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: C.textSub,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  recentRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 10,
    backgroundColor: C.gray50,
    borderRadius: 8,
    marginBottom: 8,
  },
  recentDate: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
  },
  recentSub: {
    fontSize: 12,
    color: C.textSub,
  },
})
