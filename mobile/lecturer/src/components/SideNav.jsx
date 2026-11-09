import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { CommonActions } from '@react-navigation/native'
import { useLecturer } from '../context/LecturerContext'
import { SIDE_NAV_WIDTH } from '../hooks/useWideLayout'
import { C } from '../theme'

// Tab bar replacement for wide (desktop browser) screens. Receives the same
// props as a bottom tab bar, so it drives the same tab navigator.
export default function SideNav({ state, descriptors, navigation, icons }) {
  const { state: app, openModal } = useLecturer()
  const lecturer = app.lecturer

  return (
    <View style={styles.container} accessibilityRole="navigation">
      <View style={styles.brand}>
        <View style={styles.logoIcon}>
          <Ionicons name="school" size={18} color={C.primary} />
        </View>
        <Text style={styles.brandName}>SmartClass</Text>
      </View>

      <View style={styles.items}>
        {state.routes.map((route, index) => {
          const focused = state.index === index
          const { options } = descriptors[route.key]
          const label = options.title ?? route.name
          const icon = icons[route.name]

          const onPress = () => {
            const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true })
            if (!focused && !event.defaultPrevented) {
              navigation.dispatch({ ...CommonActions.navigate({ name: route.name, merge: true }), target: state.key })
            }
          }

          return (
            <TouchableOpacity
              key={route.key}
              testID={`sidenav-${route.name}`}
              accessibilityRole="link"
              accessibilityState={focused ? { selected: true } : {}}
              onPress={onPress}
              style={[styles.item, focused && styles.itemActive]}
            >
              <Ionicons
                name={focused ? icon.active : icon.inactive}
                size={20}
                color={focused ? C.primary : C.gray500}
              />
              <Text style={[styles.itemLabel, focused && styles.itemLabelActive]}>{label}</Text>
            </TouchableOpacity>
          )
        })}
      </View>

      <View style={styles.footer}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{lecturer?.initials ?? 'ME'}</Text>
        </View>
        <View style={styles.flex}>
          <Text style={styles.userName} numberOfLines={1}>{lecturer?.name ?? 'Lecturer'}</Text>
          <Text style={styles.userEmail} numberOfLines={1}>{lecturer?.email ?? ''}</Text>
        </View>
        <TouchableOpacity
          onPress={() => openModal('signout')}
          accessibilityLabel="Sign out"
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Ionicons name="log-out-outline" size={20} color={C.gray500} />
        </TouchableOpacity>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    width: SIDE_NAV_WIDTH,
    backgroundColor: C.card,
    borderRightWidth: 1,
    borderRightColor: C.border,
    paddingVertical: 20,
    paddingHorizontal: 14,
  },
  flex: { flex: 1 },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 8,
    marginBottom: 24,
  },
  logoIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandName: {
    fontSize: 18,
    fontWeight: '800',
    color: C.text,
    letterSpacing: -0.3,
  },
  items: {
    flex: 1,
    gap: 4,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
  },
  itemActive: {
    backgroundColor: C.blueLt,
  },
  itemLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: C.textSub,
  },
  itemLabelActive: {
    color: C.primary,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingTop: 14,
    paddingHorizontal: 4,
    borderTopWidth: 1,
    borderTopColor: C.border,
  },
  avatar: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#fff',
  },
  userName: {
    fontSize: 13,
    fontWeight: '600',
    color: C.text,
  },
  userEmail: {
    fontSize: 11,
    color: C.textSub,
  },
})
