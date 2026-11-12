import { useState, useEffect } from 'react'
import { changePassword } from '../services/api'
import { getSaveFolderLabel, forgetSaveFolder } from '../services/saveCsv'
import {
  Modal, View, Text, TextInput, TouchableOpacity, TouchableWithoutFeedback,
  ScrollView, StyleSheet, Dimensions, Platform,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import { navigateTo } from '../navigation/navigationRef'
import { useWideLayout } from '../hooks/useWideLayout'
import { C } from '../theme'
import Badge from './Badge'
import {
  STATUSES, WEEK_DAYS, timeOptions, OVERRIDE_REASON_MAX, statusLabel, statusBadge, overrideReasonError,
  weeklyScheduleError,
} from '../services/attendance'

// ─── Sheet wrapper ─────────────────────────────────────────────────────────────

// Bottom sheet on phones; a centred dialog on wide (desktop browser) screens.
function Sheet({ visible, onClose, children }) {
  const { bottom } = useSafeAreaInsets()
  const wide = useWideLayout()
  return (
    <Modal transparent animationType={wide ? 'fade' : 'slide'} visible={visible} onRequestClose={onClose}>
      <View style={[styles.overlay, wide && styles.overlayWide]}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={StyleSheet.absoluteFillObject} />
        </TouchableWithoutFeedback>
        <View style={[styles.sheet, wide ? styles.dialog : { paddingBottom: bottom }]}>
          {!wide && <View style={styles.handle} />}
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

// Override to any of the four statuses with an optional reason (FR-305); the reason is audited
function StudentModal({ visible, onClose, data, overrideStudent }) {
  const [busy, setBusy] = useState(false)
  const [choice, setChoice] = useState(null)
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    if (visible) { setBusy(false); setChoice(null); setReason(''); setErr('') }
  }, [visible])

  if (!data) return null

  const inits = data.initials ?? data.name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase()
  const picked = choice ?? data.status

  const handleSave = async () => {
    const reasonErr = overrideReasonError(reason)
    if (reasonErr) { setErr(reasonErr); return }
    setBusy(true)
    try {
      await overrideStudent(data.recordId, picked, data.studentId, reason)
      onClose()
    } catch {
      setBusy(false)   // the error toast is shown by the context
    }
  }

  const unchanged = !choice || choice === data.status

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.studentHeader}>
        <View style={[styles.avatarLg, { backgroundColor: C.blueLt }]}>
          <Text style={[styles.avatarLgText, { color: C.blueDk }]}>{inits}</Text>
        </View>
        <View style={styles.studentHeaderInfo}>
          <Text style={styles.studentName}>{data.name}</Text>
          <Text style={styles.studentId}>{data.id}{data.arrivedAt ? ` · arrived ${data.arrivedAt}` : ''}</Text>
        </View>
        <Badge variant={statusBadge(data.status)} dot>{statusLabel(data.status)}</Badge>
      </View>

      <Text style={styles.inputLabel}>Change status to</Text>
      <View style={styles.statusGrid}>
        {STATUSES.map(s => {
          const on = picked === s
          return (
            <TouchableOpacity
              key={s}
              testID={`status-option-${s}`}
              accessibilityRole="radio"
              accessibilityState={{ selected: on }}
              style={[styles.statusOption, on && styles.statusOptionOn]}
              onPress={() => setChoice(s)}
            >
              <Text style={[styles.statusOptionText, on && styles.statusOptionTextOn]}>{statusLabel(s)}</Text>
            </TouchableOpacity>
          )
        })}
      </View>

      <Text style={styles.inputLabel}>Reason (optional)</Text>
      <TextInput
        testID="override-reason"
        style={[styles.input, styles.reasonInput]}
        placeholder="e.g. medical certificate"
        placeholderTextColor={C.textHint}
        value={reason}
        onChangeText={(t) => { setReason(t); setErr('') }}
        multiline
        maxLength={OVERRIDE_REASON_MAX + 50}
      />
      {err ? <Text style={styles.errText}>{err}</Text> : null}

      <BtnPrimary
        label={busy ? 'Saving…' : unchanged ? 'Pick a new status' : `Mark ${statusLabel(picked)}`}
        icon={busy || unchanged ? undefined : 'checkmark'}
        disabled={busy || unchanged}
        onPress={handleSave}
      />
      <Divider />
      <BtnOutline label="Cancel" onPress={onClose} />
    </Sheet>
  )
}

// ─── WeeklyScheduleModal (FR-301) ──────────────────────────────────────────────

// A time field that opens a list of half-hour times instead of free typing
function TimeSelect({ label, value, onChange, after, testID }) {
  const [open, setOpen] = useState(false)
  const options = timeOptions(after)
  return (
    <View style={styles.flex1}>
      <Text style={styles.inputLabel}>{label}</Text>
      <TouchableOpacity style={[styles.input, styles.timeField, open && styles.statusOptionOn]} testID={testID}
        onPress={() => setOpen(o => !o)} accessibilityRole="button" accessibilityLabel={`${label} time`}>
        <Text style={[styles.statusOptionText, !value && { color: C.textHint }]}>{value || 'Choose'}</Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={16} color={C.textSub} />
      </TouchableOpacity>
      {open ? (
        <ScrollView style={styles.timeList} nestedScrollEnabled>
          {options.length === 0 ? <Text style={styles.hintText}>Pick an earlier start first.</Text> : null}
          {options.map(t => (
            <TouchableOpacity key={t} testID={`${testID}-${t}`} style={[styles.timeOption, value === t && styles.statusOptionOn]}
              onPress={() => { onChange(t); setOpen(false) }} accessibilityRole="radio" accessibilityState={{ selected: value === t }}>
              <Text style={[styles.statusOptionText, value === t && styles.statusOptionTextOn]}>{t}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      ) : null}
    </View>
  )
}

const SCHEDULE_HINT =
  'Changes apply to upcoming classes. A class already in progress is not affected. For an extra class, use Start now.'

function WeeklyScheduleModal({ visible, onClose, data }) {
  const { doSetWeeklySchedule, closeModal } = useLecturer()
  const [day, setDay] = useState(null)
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [room, setRoom] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!visible || !data) return
    setDay(WEEK_DAYS.includes(data.day_of_week) ? data.day_of_week : null);   // a weekend slot must be moved to a weekday setStart(data.start_time ?? ''); setEnd(data.end_time ?? '')
    setRoom(data.room ?? ''); setErr(''); setBusy(false)
  }, [visible, data])

  if (!data) return null

  const save = async (slot) => {
    const e = weeklyScheduleError(slot)
    if (e) { setErr(e); return }
    setBusy(true)
    try {
      await doSetWeeklySchedule(data.classId, slot)
      closeModal()
    } catch (ex) {
      setErr(ex.message || 'Could not save the schedule.')
      setBusy(false)
    }
  }

  return (
    <Sheet visible={visible} onClose={onClose}>
      <ModalTitle>Weekly schedule</ModalTitle>
      <ModalSub>{data.title} · sessions open {data.earlyMinutes ?? 15} min before the start. SPeCTRUM sync never changes this.</ModalSub>
      {err ? <Text style={styles.errText}>{err}</Text> : null}
      <Text style={styles.inputLabel}>Day</Text>
      <View style={styles.statusGrid}>
        {WEEK_DAYS.map(d => (
          <TouchableOpacity key={d} style={[styles.dayChip, day === d && styles.statusOptionOn]}
            onPress={() => setDay(d)} accessibilityRole="radio" accessibilityState={{ selected: day === d }}>
            <Text style={[styles.statusOptionText, day === d && styles.statusOptionTextOn]}>{d}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={[styles.btnRow, styles.timeRow]}>
        <TimeSelect label="Start" value={start} testID="schedule-start"
          onChange={t => { setStart(t); if (end && end <= t) setEnd('') }} />
        <TimeSelect label="End" value={end} after={start || null} testID="schedule-end" onChange={setEnd} />
      </View>
      <Text style={styles.inputLabel}>Room (optional)</Text>
      <TextInput style={styles.input} value={room} onChangeText={setRoom}
        placeholder="e.g. DK 2 FSKTM" placeholderTextColor={C.textHint} />
      <Text style={styles.hintText} testID="schedule-hint">
        {SCHEDULE_HINT}
      </Text>
      <BtnRow>
        <BtnOutline label="Cancel" onPress={onClose} />
        <BtnPrimary label={busy ? 'Saving…' : 'Save schedule'} icon="checkmark" disabled={busy}
          onPress={() => save({ day, start: start.trim(), end: end.trim(), room })} />
      </BtnRow>
    </Sheet>
  )
}

// ─── ExportModal ───────────────────────────────────────────────────────────────

function ExportModal({ visible, onClose, data }) {
  const { exportCsv, closeModal } = useLecturer()
  const [busy, setBusy] = useState(false)
  const [folder, setFolder] = useState(null)

  useEffect(() => {
    if (visible) getSaveFolderLabel().then(setFolder)
  }, [visible])

  const changeFolder = async () => {
    await forgetSaveFolder()
    setFolder(null)
  }

  const handleExport = async () => {
    if (busy || !data) return
    setBusy(true)
    try {
      await exportCsv(data)
    } catch {
      // showToast already called inside exportCsv
    } finally {
      setBusy(false)
      closeModal()   // also on failure: toasts show behind an open dialog
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
        {Platform.OS === 'android' && (
          <View style={styles.exportSummaryRow}>
            <Ionicons name="folder-outline" size={16} color={C.primary} />
            {folder ? (
              <>
                <Text style={[styles.exportSummaryText, styles.exportFolderText]}>Saves to {folder}</Text>
                <TouchableOpacity onPress={changeFolder} accessibilityRole="button" hitSlop={8}>
                  <Text style={styles.exportFolderChange}>Change</Text>
                </TouchableOpacity>
              </>
            ) : (
              <Text style={[styles.exportSummaryText, styles.exportFolderText]}>
                Next, choose where to save. Android doesn't allow Download itself, so create a folder inside it, such as SmartClass.
              </Text>
            )}
          </View>
        )}
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
      <WeeklyScheduleModal visible={type === 'weekly-schedule'} onClose={closeModal} data={type === 'weekly-schedule' ? data : null} />
      <ExportModal visible={type === 'export'} onClose={closeModal} data={data} />
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
  overlayWide: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  dialog: {
    width: '100%',
    maxWidth: 480,
    borderRadius: 16,
    paddingTop: 22,
    paddingBottom: 20,
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
  statusGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 14,
  },
  statusOption: {
    flexGrow: 1,
    flexBasis: '45%',
    alignItems: 'center',
    paddingVertical: 11,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: C.card,
  },
  dayChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: C.border,
    backgroundColor: C.card,
  },
  statusOptionOn: {
    borderColor: C.primary,
    backgroundColor: C.blueLt,
  },
  statusOptionText: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  statusOptionTextOn: {
    color: C.primary,
  },
  reasonInput: {
    minHeight: 64,
    textAlignVertical: 'top',
  },
  timeRow: {
    alignItems: 'flex-start',
  },
  timeField: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  timeList: {
    maxHeight: 180,
    marginTop: -6,
    marginBottom: 12,
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 10,
    backgroundColor: C.card,
  },
  timeOption: {
    paddingVertical: 9,
    paddingHorizontal: 12,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  hintText: {
    fontSize: 12,
    color: C.textSub,
    marginTop: -8,
    marginBottom: 12,
  },
  flex1: {
    flex: 1,
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
  exportFolderText: {
    flex: 1,
  },
  exportFolderChange: {
    fontSize: 14,
    fontWeight: '700',
    color: C.primary,
  },
  exportSummaryText: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
})
