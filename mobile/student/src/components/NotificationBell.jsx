import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { countLabel, bellLabel } from '../services/notifications'
import { C } from '../theme'

// The bell with the unread count (FR-209). `light` for a dark background (the Home banner).
export default function NotificationBell({ count, onPress, light = false }) {
  const label = countLabel(count)
  return (
    <TouchableOpacity
      style={[styles.btn, light ? styles.btnLight : styles.btnPlain]}
      onPress={onPress}
      testID="notif-bell"
      accessibilityRole="button"
      accessibilityLabel={bellLabel(count)}
      hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
    >
      <Ionicons name="notifications-outline" size={20} color={light ? '#fff' : C.text} />
      {label ? (
        <View style={styles.badge}>
          <Text style={styles.badgeText} testID="notif-bell-count">{label}</Text>
        </View>
      ) : null}
    </TouchableOpacity>
  )
}

const styles = StyleSheet.create({
  btn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnLight: { backgroundColor: 'rgba(255,255,255,0.16)' },
  btnPlain: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border },
  badge: {
    position: 'absolute',
    top: -3,
    right: -3,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 4,
    backgroundColor: C.red,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#fff',
  },
  badgeText: { fontSize: 10, fontWeight: '700', color: '#fff' },
})
