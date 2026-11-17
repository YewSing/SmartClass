import { Platform, StyleSheet, View } from 'react-native'
import { C } from '../theme'

// Web-only phone frame so the student web export looks like a handset.
// Fixed 390 × 844 px. On native (iOS/Android) renders children directly.
export default function PhoneShell({ children }) {
  if (Platform.OS !== 'web') {
    return <View style={styles.fill}>{children}</View>
  }

  return (
    <View style={styles.page}>
      <View style={styles.phone}>
        <View style={styles.statusBar} />
        <View style={styles.body}>{children}</View>
        <View style={styles.homeIndicator} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: '#E5E7EB',
    alignItems: 'center',
    justifyContent: 'center',
  },
  phone: {
    width: 390,
    height: 844,
    backgroundColor: '#111825',
    borderRadius: 44,
    overflow: 'hidden',
    position: 'relative',
  },
  statusBar: { height: 44, backgroundColor: '#111825' },
  body: { flex: 1, backgroundColor: C.bg },
  homeIndicator: {
    height: 34,
    backgroundColor: '#111825',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  fill: { flex: 1 },
})
