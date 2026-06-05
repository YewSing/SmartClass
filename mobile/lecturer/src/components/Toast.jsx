import { useEffect, useRef } from 'react'
import { Animated, Text, StyleSheet, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useLecturer } from '../context/LecturerContext'
import { C } from '../theme'

const COLORS = {
  success: { bg: C.green,   text: '#fff' },
  error:   { bg: C.red,     text: '#fff' },
  info:    { bg: C.primary, text: '#fff' },
}

function ToastItem({ toast, onDismiss }) {
  const slideY = useRef(new Animated.Value(60)).current
  const opacity = useRef(new Animated.Value(0)).current
  const col = COLORS[toast.variant] ?? COLORS.info

  useEffect(() => {
    Animated.parallel([
      Animated.timing(slideY, { toValue: 0, duration: 250, useNativeDriver: true }),
      Animated.timing(opacity, { toValue: 1, duration: 250, useNativeDriver: true }),
    ]).start()

    const timer = setTimeout(() => {
      Animated.parallel([
        Animated.timing(slideY, { toValue: 60, duration: 250, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0, duration: 250, useNativeDriver: true }),
      ]).start(() => onDismiss(toast.id))
    }, 3000)

    return () => clearTimeout(timer)
  }, [])

  return (
    <Animated.View style={[styles.toast, { backgroundColor: col.bg, transform: [{ translateY: slideY }], opacity }]}>
      <Text style={[styles.toastText, { color: col.text }]}>{toast.message}</Text>
    </Animated.View>
  )
}

export default function ToastContainer() {
  const { state, dispatch } = useLecturer()
  const insets = useSafeAreaInsets()
  const { toasts } = state

  const dismiss = (id) => dispatch({ type: 'DISMISS_TOAST', payload: id })

  return (
    <View style={[styles.container, { bottom: insets.bottom + 80 }]} pointerEvents="none">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
      ))}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: 16,
    right: 16,
    alignItems: 'center',
    zIndex: 9999,
  },
  toast: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 10,
    marginTop: 8,
    width: '100%',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.18,
    shadowRadius: 4,
    elevation: 4,
  },
  toastText: {
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
})
