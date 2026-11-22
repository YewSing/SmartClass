// Notification preferences (FR-214; plan-shino.md S19). Urgent and important notifications always
// go to the phone and by email; only general ones can be turned on or off per channel.
import { useCallback, useEffect, useState } from 'react'
import { View, Text, Switch, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native'
import { useLecturer as useApp } from '../context/LecturerContext'
import * as api from '../services/api'
import { prefsUpdate } from '../services/notifications'
import Topbar from '../components/Topbar'
import { C } from '../theme'

const GENERAL_EXAMPLES = 'Other class updates'

const CHANNELS = [
  { key: 'push',  label: 'Push notifications', hint: 'On your phone, when you use the SmartClass app (Android).' },
  { key: 'email', label: 'Email',              hint: 'To your university email address.' },
]

export default function NotificationPrefs({ navigation }) {
  const { showToast } = useApp()
  const [prefs, setPrefs] = useState(null)
  const [failed, setFailed] = useState(false)
  const [saving, setSaving] = useState(null)
  const [sending, setSending] = useState(false)

  const load = useCallback(async () => {
    setFailed(false)
    try { setPrefs(await api.getNotificationPrefs()) } catch (e) { setFailed(true); showToast(e.message, 'error') }
  }, [showToast])
  useEffect(() => { load() }, [load])

  const toggle = async (channel, on) => {
    setSaving(channel)
    try {
      setPrefs(await api.updateNotificationPrefs(prefsUpdate(channel, on)))
      showToast('Preferences saved', 'success')
    } catch (e) { showToast(e.message, 'error') } finally { setSaving(null) }
  }

  const sendTest = async () => {
    setSending(true)
    try {
      const r = await api.sendTestNotification()
      showToast(r.sent ? 'Test notification sent' : 'A test was sent less than a minute ago', r.sent ? 'success' : 'info')
    } catch (e) { showToast(e.message, 'error') } finally { setSending(false) }
  }

  return (
    <View style={styles.flex}>
      <Topbar title="Notification settings" onBack={() => navigation.goBack()} />
      <ScrollView contentContainerStyle={styles.content}>
        {!prefs ? (
          failed ? (
            <TouchableOpacity style={styles.retry} onPress={load}><Text style={styles.retryText}>Try again</Text></TouchableOpacity>
          ) : <ActivityIndicator style={{ marginTop: 40 }} color={C.primary} />
        ) : (
          <>
            <Text style={styles.intro}>
              Urgent and important notifications (confused students, attendance flags, at-risk alerts) always reach you.
              You choose whether general ones do too. Every notification is always in the app.
            </Text>
            {CHANNELS.map(ch => (
              <View key={ch.key} style={styles.card}>
                <Text style={styles.cardTitle}>{ch.label}</Text>
                <Text style={styles.cardHint}>{ch.hint}</Text>
                <Row group={ch.label} label="Urgent" value locked />
                <Row group={ch.label} label="Important" value locked />
                <Row
                  group={ch.label}
                  label="General"
                  sub={GENERAL_EXAMPLES}
                  value={!!prefs[ch.key]?.general}
                  busy={saving === ch.key}
                  onChange={(v) => toggle(ch.key, v)}
                  testID={`prefs-${ch.key}-general`}
                />
              </View>
            ))}
            <TouchableOpacity style={[styles.test, sending && styles.disabled]} onPress={sendTest} disabled={sending} testID="prefs-send-test">
              <Text style={styles.testText}>{sending ? 'Sending…' : 'Send a test notification'}</Text>
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
    </View>
  )
}

function Row({ group, label, sub, value, locked = false, busy = false, onChange, testID }) {
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel}>{label}</Text>
        {locked ? <Text style={styles.rowSub}>Always on</Text> : sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        disabled={locked || busy}
        trackColor={{ true: C.primary, false: C.gray300 }}
        testID={testID}
        accessibilityLabel={`${group}: ${label}${locked ? ', always on' : ''}`}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, gap: 12, paddingBottom: 32 },
  intro: { fontSize: 13, color: C.textSub, lineHeight: 19 },
  card: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 12, padding: 14 },
  cardTitle: { fontSize: 15, fontWeight: '600', color: C.text },
  cardHint: { fontSize: 12, color: C.textSub, marginTop: 2, marginBottom: 6 },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderTopWidth: 1, borderTopColor: C.border, gap: 8 },
  rowLabel: { fontSize: 14, color: C.text },
  rowSub: { fontSize: 12, color: C.textHint, marginTop: 1 },
  test: { borderWidth: 1, borderColor: C.primary, borderRadius: 10, paddingVertical: 12, alignItems: 'center', backgroundColor: C.card },
  testText: { fontSize: 14, fontWeight: '600', color: C.primary },
  disabled: { opacity: 0.5 },
  retry: { alignSelf: 'center', marginTop: 40, backgroundColor: C.primary, borderRadius: 10, paddingVertical: 10, paddingHorizontal: 20 },
  retryText: { fontSize: 14, fontWeight: '600', color: '#fff' },
})
