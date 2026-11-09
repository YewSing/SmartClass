import { useState } from 'react'
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { useStudent } from '../context/StudentContext'
import { giveFaceConsent } from '../services/api'
import { C } from '../theme'

const NOTICE = [
  {
    icon: 'scan-outline',
    title: 'What we collect',
    text: 'Three selfies and one photo of your UM matric card. From the selfies we store a face '
      + 'template (a list of numbers), not the photos.',
  },
  {
    icon: 'checkmark-done-outline',
    title: 'Why',
    text: 'To take your attendance with the classroom camera. The card photo is used only to check '
      + 'that the selfies are you.',
  },
  {
    icon: 'trash-outline',
    title: 'How long we keep the photos',
    text: 'The photos are deleted as soon as they are checked. If a lecturer has to review them, '
      + 'they are deleted when the lecturer decides. Card photos never leave the SmartClass server.',
  },
  {
    icon: 'people-outline',
    title: 'Who can see them',
    text: 'Only a lecturer of one of your courses, or an administrator, and only when your photos '
      + 'could not be checked automatically.',
  },
  {
    icon: 'hand-left-outline',
    title: 'Your choice',
    text: 'You may decline. Your lecturer can still mark your attendance by hand. You can withdraw '
      + 'consent at any time in Profile → Face enrolment, and your face data is deleted at once.',
  },
]

// PDPA consent before any face data is captured (FR-109, NFR-03)
export default function FaceConsent({ route, navigation }) {
  const { currentVersion } = route.params ?? {}
  const { showToast } = useStudent()
  const [saving, setSaving] = useState(false)

  const accept = async () => {
    setSaving(true)
    try {
      await giveFaceConsent(currentVersion)
      navigation.replace('FaceCapture')
    } catch (e) {
      showToast(e.message, 'error')
      setSaving(false)
    }
  }

  return (
    <View style={styles.screen}>
      <Topbar title="Face data consent" sub={`PDPA notice · ${currentVersion ?? ''}`} onBack={() => navigation.goBack()} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.intro}>
          Before you enrol your face, please read how SmartClass uses your face data.
        </Text>
        {NOTICE.map(n => (
          <View key={n.title} style={styles.item}>
            <View style={styles.icon}><Ionicons name={n.icon} size={18} color={C.primary} /></View>
            <View style={styles.itemBody}>
              <Text style={styles.itemTitle}>{n.title}</Text>
              <Text style={styles.itemText}>{n.text}</Text>
            </View>
          </View>
        ))}
        <TouchableOpacity
          style={[styles.primaryBtn, (saving || !currentVersion) && styles.disabled]}
          onPress={accept}
          disabled={saving || !currentVersion}
        >
          {saving ? <ActivityIndicator color="#fff" size="small" /> : (
            <Text style={styles.primaryText}>I agree</Text>
          )}
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryBtn} onPress={() => navigation.goBack()} disabled={saving}>
          <Text style={styles.secondaryText}>Not now</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32, gap: 12 },
  intro: { fontSize: 14, color: C.text, lineHeight: 20 },
  item: {
    flexDirection: 'row', gap: 12, backgroundColor: C.card, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: C.border,
  },
  icon: {
    width: 34, height: 34, borderRadius: 8, backgroundColor: C.blueLt,
    alignItems: 'center', justifyContent: 'center',
  },
  itemBody: { flex: 1 },
  itemTitle: { fontSize: 14, fontWeight: '700', color: C.text, marginBottom: 2 },
  itemText: { fontSize: 13, color: C.textSub, lineHeight: 19 },
  primaryBtn: {
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 14, alignItems: 'center', marginTop: 4,
  },
  primaryText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  secondaryBtn: { paddingVertical: 12, alignItems: 'center' },
  secondaryText: { color: C.textSub, fontSize: 14, fontWeight: '600' },
  disabled: { opacity: 0.6 },
})
