import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { C } from '../theme'

export default function Topbar({ title, sub, onBack, right }) {
  const insets = useSafeAreaInsets()

  return (
    <View style={[styles.container, { paddingTop: insets.top + 8 }]}>
      <View style={styles.inner}>
        {onBack ? (
          <TouchableOpacity onPress={onBack} style={styles.backBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Ionicons name="arrow-back" size={22} color={C.text} />
          </TouchableOpacity>
        ) : (
          <View style={styles.backPlaceholder} />
        )}
        <View style={styles.titleWrap}>
          <Text style={styles.title} numberOfLines={1}>{title}</Text>
          {sub ? <Text style={styles.sub} numberOfLines={1}>{sub}</Text> : null}
        </View>
        {right ? (
          <View style={styles.right}>{right}</View>
        ) : (
          <View style={styles.backPlaceholder} />
        )}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    paddingBottom: 10,
    paddingHorizontal: 16,
  },
  inner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  backBtn: {
    width: 32,
    alignItems: 'flex-start',
  },
  backPlaceholder: {
    width: 32,
  },
  titleWrap: {
    flex: 1,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
    color: C.text,
  },
  sub: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 1,
  },
  right: {
    alignItems: 'flex-end',
  },
})
