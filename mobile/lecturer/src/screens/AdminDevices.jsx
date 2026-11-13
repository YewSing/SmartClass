import { useCallback, useRef, useState } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, StyleSheet, ActivityIndicator, Platform,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import * as api from '../services/api'
import { deviceStatus, formatMyt, newDeviceError } from '../services/adminHelpers'
import { C } from '../theme'

// The one-time key after registering a device or issuing a new one (FR-408). It lives only in
// this screen's state: never in context, AsyncStorage or localStorage.
function KeyPanel({ shown, onDone }) {
  const { showToast } = useLecturer()
  const { device, key, kind } = shown
  const canCopy = Platform.OS === 'web' && typeof navigator !== 'undefined' && !!navigator.clipboard

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(key)
      showToast('Key copied', 'success')
    } catch {
      showToast("Couldn't copy; select the key and copy it", 'error')
    }
  }

  return (
    <View style={styles.card} testID="device-key-panel">
      <Text style={styles.cardTitle}>Key for {device.name} ({device.room})</Text>
      <Text style={styles.hint}>
        Copy it now. It is shown only this once; SmartClass keeps only a fingerprint of it.
        Put it in the device's DEVICE_KEY setting.
        {kind === 'regenerated' ? ' The old key has stopped working.' : ''}
      </Text>
      <Text selectable testID="device-key" style={styles.key}>{key}</Text>
      <Text style={styles.meta}>Device ID: {device.device_id}</Text>
      <View style={styles.actions}>
        {canCopy && (
          <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={copy} testID="device-key-copy">
            <Text style={styles.btnOutlineText}>Copy</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={onDone} testID="device-key-done">
          <Text style={styles.btnPrimaryText}>Done</Text>
        </TouchableOpacity>
      </View>
    </View>
  )
}

// Register a camera for one room (FR-408). The room has to match the timetable, or the camera
// never finds the sessions held there.
function RegisterDevice({ onRegistered, onCancel }) {
  const [form, setForm] = useState({ name: '', room: '' })
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (v) => { setForm(f => ({ ...f, [k]: v })); if (err) setErr(null) }

  const submit = async () => {
    const problem = newDeviceError(form)
    if (problem) { setErr(problem); return }
    setBusy(true)
    try {
      onRegistered(await api.adminRegisterDevice(form))
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <View style={styles.card} testID="register-device-form">
      <Text style={styles.cardTitle}>Register a camera</Text>
      {err && <Text style={styles.errText}>{err}</Text>}
      <View style={styles.formGrid}>
        <View style={styles.formField}>
          <Text style={styles.label}>Device name</Text>
          <TextInput style={styles.input} value={form.name} onChangeText={set('name')}
            placeholder="e.g. DK1 door camera" placeholderTextColor={C.textHint} testID="new-device-name" />
        </View>
        <View style={styles.formField}>
          <Text style={styles.label}>Room</Text>
          <TextInput style={styles.input} value={form.room} onChangeText={set('room')}
            placeholder="Room, exactly as in the timetable" placeholderTextColor={C.textHint} testID="new-device-room" />
        </View>
      </View>
      <Text style={styles.hint}>
        The room must match the class timetable's room so the camera finds its sessions.
      </Text>
      <View style={styles.actions}>
        <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={onCancel} disabled={busy}>
          <Text style={styles.btnOutlineText}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btn, styles.btnPrimary, busy && styles.busy]} onPress={submit}
          disabled={busy} testID="new-device-submit">
          {busy ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.btnPrimaryText}>Register</Text>}
        </TouchableOpacity>
      </View>
    </View>
  )
}

function DeviceRow({ d, onKey }) {
  const { showToast } = useLecturer()
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const status = deviceStatus(d)

  const run = async () => {
    setBusy(true)
    try {
      const res = await api.adminRegenerateDeviceKey(d.id)
      onKey({ device: res, key: res.key, kind: d.has_key ? 'regenerated' : 'new' })
      setConfirm(false)
    } catch (e) {
      showToast(e.message, 'error')
      setConfirm(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <View style={styles.row} testID="device-row">
      <View style={styles.rowMain}>
        <View style={styles.flex}>
          <Text style={styles.name}>{d.name}</Text>
          <Text style={styles.meta}>{d.room} · {d.device_id}</Text>
          {d.key_created_at ? <Text style={styles.meta}>Key issued {formatMyt(d.key_created_at)}</Text> : null}
        </View>
        <View testID="device-status">
          <Badge dot variant={status.tone === 'good' ? 'green' : status.tone === 'bad' ? 'red' : 'gray'}>
            {status.label}
          </Badge>
        </View>
      </View>

      {confirm ? (
        <View style={styles.confirmBox}>
          <Text style={styles.confirmText}>
            {d.has_key
              ? `${d.name} gets a new key. The old key stops working at once, so the device stays offline until you put the new key on it.`
              : `Issue a key for ${d.name}?`}
          </Text>
          <View style={styles.actions}>
            <TouchableOpacity style={[styles.btnSm, styles.btnOutline]} onPress={() => setConfirm(false)} disabled={busy}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btnSm, styles.btnPrimary, busy && styles.busy]} onPress={run}
              disabled={busy} testID="device-regenerate-confirm">
              {busy ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.btnPrimaryText}>Confirm new key</Text>}
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <View style={styles.rowActions}>
          <TouchableOpacity style={[styles.btnSm, styles.btnOutline]} onPress={() => setConfirm(true)}
            testID="device-regenerate">
            <Ionicons name="key-outline" size={14} color={C.text} />
            <Text style={styles.btnOutlineText}>{d.has_key ? 'Regenerate key' : 'Issue key'}</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  )
}

// The cameras at the rooms' doors (FR-408): which are online (NFR-23), register one, and issue
// or regenerate its key. The key is shown once and never stored.
export default function AdminDevices() {
  const [devices, setDevices] = useState(undefined)   // undefined while loading, then an array
  const [error, setError] = useState(null)
  const [registering, setRegistering] = useState(false)
  const [shownKey, setShownKey] = useState(null)      // null | { device, key, kind: 'new'|'regenerated' }
  const scrollRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setDevices(await api.adminListDevices())
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  // Load now and keep the online/offline state current while the tab is open
  useFocusEffect(useCallback(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [load]))

  const showKey = (next) => {
    setShownKey(next)
    scrollRef.current?.scrollTo({ y: 0, animated: true })
    load()
  }

  return (
    <View style={styles.flex}>
      <Topbar title="Camera devices" sub="Door cameras that record attendance (one per room)" />
      <ScrollView ref={scrollRef} style={styles.flex} contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled">
        <View style={styles.toolbar}>
          <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={() => setRegistering(r => !r)}
            testID="device-register-open">
            <Ionicons name="add-circle-outline" size={16} color="#fff" />
            <Text style={styles.btnPrimaryText}>Register device</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={load} testID="devices-refresh">
            <Ionicons name="refresh" size={16} color={C.text} />
            <Text style={styles.btnOutlineText}>Refresh</Text>
          </TouchableOpacity>
        </View>

        {shownKey && <KeyPanel shown={shownKey} onDone={() => setShownKey(null)} />}

        {registering && (
          <RegisterDevice
            onCancel={() => setRegistering(false)}
            onRegistered={(res) => { setRegistering(false); showKey({ device: res, key: res.key, kind: 'new' }) }}
          />
        )}

        {error && (
          <TouchableOpacity style={styles.errorBox} onPress={load}>
            <Text style={styles.errText}>{error}</Text>
            <Text style={styles.retry}>Tap to retry</Text>
          </TouchableOpacity>
        )}

        {devices === undefined && !error && <ActivityIndicator color={C.primary} style={{ marginTop: 24 }} />}
        {devices?.length === 0 && (
          <Text style={styles.empty}>No camera devices yet. Register one for each room with a door camera.</Text>
        )}
        {devices?.map(d => <DeviceRow key={d.id} d={d} onKey={showKey} />)}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32, gap: 10 },
  toolbar: { flexDirection: 'row', gap: 10, flexWrap: 'wrap', alignItems: 'center' },
  card: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, gap: 10 },
  cardTitle: { fontSize: 15, fontWeight: '700', color: C.text },
  hint: { fontSize: 12, color: C.textSub, lineHeight: 18 },
  meta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  key: {
    fontSize: 13, color: C.text, backgroundColor: C.gray50, borderRadius: 8, padding: 10,
    fontFamily: Platform.OS === 'web' ? 'monospace' : undefined,
  },
  formGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  formField: { flexGrow: 1, flexBasis: 220 },
  label: { fontSize: 12, fontWeight: '700', color: C.text, marginBottom: 4 },
  input: {
    borderWidth: 1.5, borderColor: C.border, borderRadius: 10, padding: 10, fontSize: 14, color: C.text, backgroundColor: C.bg,
  },
  row: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, gap: 10 },
  rowMain: { flexDirection: 'row', gap: 12 },
  name: { fontSize: 15, fontWeight: '700', color: C.text },
  rowActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap' },
  confirmBox: { backgroundColor: C.gray50, borderRadius: 8, padding: 10, gap: 10 },
  confirmText: { fontSize: 13, color: C.text, lineHeight: 19 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap' },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 10, paddingHorizontal: 16, borderRadius: 10,
  },
  btnSm: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 7, paddingHorizontal: 12, borderRadius: 8,
  },
  btnPrimary: { backgroundColor: C.primary },
  btnOutline: { borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card },
  btnPrimaryText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  btnOutlineText: { fontSize: 13, fontWeight: '600', color: C.text },
  busy: { opacity: 0.6 },
  empty: { fontSize: 13, color: C.textSub, marginTop: 8 },
  errorBox: { backgroundColor: C.redLt, borderRadius: 8, padding: 10 },
  errText: { fontSize: 13, color: C.redDk, backgroundColor: C.redLt, borderRadius: 8, padding: 8 },
  retry: { fontSize: 12, fontWeight: '600', color: C.redDk, paddingHorizontal: 8 },
})
