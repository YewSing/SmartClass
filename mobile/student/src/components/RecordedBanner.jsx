import { useEffect } from 'react'
import { Text, TouchableOpacity, StyleSheet } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useStudent } from '../context/StudentContext'
import { C } from '../theme'

const AUTO_HIDE_MS = 8000

// The global "Attendance recorded for <CODE> · Present" banner (FR-406). It sits above every tab
// (rendered once by AppNavigator) and a tap dismisses it.
export default function RecordedBanner() {
  const { state, dispatch, dismissBanner } = useStudent()
  const insets = useSafeAreaInsets()
  const banner = state.banner

  useEffect(() => {
    if (!banner) return undefined
    const timer = setTimeout(() => dispatch({ type: 'HIDE_BANNER', payload: banner.id }), AUTO_HIDE_MS)
    return () => clearTimeout(timer)
  }, [banner?.id, dispatch])

  if (!banner) return null

  return (
    <TouchableOpacity
      testID="recorded-banner"
      activeOpacity={0.9}
      onPress={dismissBanner}
      style={[styles.banner, { top: insets.top + 8 }]}
    >
      <Ionicons name="checkmark-circle" size={18} color={C.green} style={{ marginTop: 1 }} />
      <Text testID="recorded-banner-text" style={styles.text}>{banner.text}</Text>
      <Ionicons name="close" size={15} color={C.greenDk} />
    </TouchableOpacity>
  )
}

const styles = StyleSheet.create({
  banner: {
    position: 'absolute',
    left: 16,
    right: 16,
    zIndex: 1000,
    elevation: 6,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.greenLt,
    borderWidth: 1,
    borderColor: C.green,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
  },
  text: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    color: C.greenDk,
  },
})
