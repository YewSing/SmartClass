import { View, Text, StyleSheet } from 'react-native'
import { C } from '../theme'

const VARIANTS = {
  blue:   { bg: C.blueLt,   text: C.primary,  dot: C.primary  },
  green:  { bg: C.greenLt,  text: C.greenDk,  dot: C.green    },
  red:    { bg: C.redLt,    text: C.redDk,    dot: C.red      },
  orange: { bg: C.orangeLt, text: C.orangeDk, dot: C.orange   },
  yellow: { bg: C.yellowLt, text: C.yellowDk, dot: C.yellow   },
  gray:   { bg: C.gray100,  text: C.gray600,  dot: C.gray400  },
}

export default function Badge({ variant = 'gray', dot = false, children, style }) {
  const v = VARIANTS[variant] ?? VARIANTS.gray
  return (
    <View style={[styles.badge, { backgroundColor: v.bg }, style]}>
      {dot && <View style={[styles.dot, { backgroundColor: v.dot }]} />}
      <Text style={[styles.text, { color: v.text }]}>{children}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 20,
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  text: {
    fontSize: 11,
    fontWeight: '700',
  },
})
