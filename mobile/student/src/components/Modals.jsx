import {
  Modal, View, Text, TouchableOpacity, TouchableWithoutFeedback,
  ScrollView, StyleSheet, Dimensions,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import { C } from '../theme'

// ─── Sheet wrapper ─────────────────────────────────────────────────────────────

export function Sheet({ visible, onClose, children }) {
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

export function ModalTitle({ children }) {
  return <Text style={styles.modalTitle}>{children}</Text>
}

export function BtnOutline({ label, onPress, testID }) {
  return (
    <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={onPress} testID={testID}>
      <Text style={styles.btnOutlineText}>{label}</Text>
    </TouchableOpacity>
  )
}

export function BtnDanger({ label, onPress, icon, testID }) {
  return (
    <TouchableOpacity style={[styles.btn, styles.btnDanger]} onPress={onPress} testID={testID}>
      {icon && <Ionicons name={icon} size={16} color="#fff" style={{ marginRight: 6 }} />}
      <Text style={styles.btnPrimaryText}>{label}</Text>
    </TouchableOpacity>
  )
}

export function BtnRow({ children }) {
  return <View style={styles.btnRow}>{children}</View>
}

export function BtnPrimary({ label, onPress, icon, disabled, testID }) {
  return (
    <TouchableOpacity
      style={[styles.btn, styles.btnPrimary, disabled && styles.btnDisabled]}
      onPress={onPress}
      disabled={disabled}
      testID={testID}
    >
      {icon && <Ionicons name={icon} size={16} color="#fff" style={{ marginRight: 6 }} />}
      <Text style={styles.btnPrimaryText}>{label}</Text>
    </TouchableOpacity>
  )
}

// A plain row in an options sheet ("Rename", "Delete")
export function SheetOption({ label, icon, onPress, danger, testID }) {
  return (
    <TouchableOpacity style={styles.option} onPress={onPress} testID={testID}>
      <Ionicons name={icon} size={20} color={danger ? C.red : C.text} />
      <Text style={[styles.optionText, danger && { color: C.red }]}>{label}</Text>
    </TouchableOpacity>
  )
}

export const modalStyles = { bodyText: null, input: null }

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
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    paddingVertical: 14,
  },
  optionText: {
    fontSize: 16,
    color: C.text,
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

modalStyles.bodyText = styles.bodyText
modalStyles.input = styles.input
