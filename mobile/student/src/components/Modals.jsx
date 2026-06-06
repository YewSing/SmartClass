import { useState } from 'react'
import { changePassword } from '../services/api'
import {
  Modal, View, Text, TextInput, TouchableOpacity, TouchableWithoutFeedback,
  ScrollView, StyleSheet, Dimensions,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import { C } from '../theme'

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

function ModalTitle({ children }) {
  return <Text style={styles.modalTitle}>{children}</Text>
}

function Divider() {
  return <View style={styles.divider} />
}

function BtnPrimary({ label, onPress, icon, disabled }) {
  return (
    <TouchableOpacity style={[styles.btn, styles.btnPrimary, disabled && styles.btnDisabled]} onPress={onPress} disabled={disabled}>
      {icon && <Ionicons name={icon} size={16} color="#fff" style={{ marginRight: 6 }} />}
      <Text style={styles.btnPrimaryText}>{label}</Text>
    </TouchableOpacity>
  )
}

function BtnOutline({ label, onPress }) {
  return (
    <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={onPress}>
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

// ─── ChangePasswordModal ───────────────────────────────────────────────────────

function ChangePasswordModal({ visible, onClose }) {
  const { showToast } = useStudent()
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
      <Text style={styles.modalSub}>Your new password must be at least 8 characters.</Text>
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
        Are you sure you want to sign out of your student account?
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
  const { state, closeModal, logout } = useStudent()
  const { modal } = state
  const type = modal?.type

  const handleSignOut = async () => {
    await logout()
    closeModal()
  }

  return (
    <>
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
  btnDisabled: {
    opacity: 0.5,
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
})
