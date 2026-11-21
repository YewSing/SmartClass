import { View, Text, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from './Topbar'
import { C } from '../theme'

// Placeholder for areas being rebuilt (live class, quizzes, insights; plan-shino.md S02)
export default function ComingSoon({ title, icon = 'construct-outline', message }) {
  return (
    <View style={styles.flex}>
      <Topbar title={title} />
      <View style={styles.content}>
        <View style={styles.card} testID="coming-soon">
          <View style={styles.iconWrap}>
            <Ionicons name={icon} size={22} color={C.primary} />
          </View>
          <Text style={styles.heading}>Coming soon</Text>
          <Text style={styles.text}>{message ?? `${title} is being rebuilt and will be available here soon.`}</Text>
        </View>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16 },
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 20,
    alignItems: 'center',
    gap: 8,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heading: { fontSize: 16, fontWeight: '600', color: C.text },
  text: { fontSize: 13, color: C.textSub, textAlign: 'center', lineHeight: 19 },
})
