import { useCallback, useEffect, useRef, useState } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, StyleSheet, ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useFocusEffect } from '@react-navigation/native'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import * as api from '../services/api'
import { accountSubtitle, newAdminError } from '../services/adminHelpers'
import { C } from '../theme'

const PAGE = 50
const ROLES = [['', 'All'], ['student', 'Students'], ['lecturer', 'Lecturers'], ['admin', 'Administrators']]
const STATUSES = [['', 'Any status'], ['active', 'Active'], ['inactive', 'Deactivated']]

function Chips({ options, value, onChange, testPrefix }) {
  return (
    <View style={styles.chips}>
      {options.map(([v, label]) => (
        <TouchableOpacity
          key={v || 'all'}
          testID={`${testPrefix}-${v || 'all'}`}
          style={[styles.chip, value === v && styles.chipActive]}
          onPress={() => onChange(v)}
          accessibilityRole="button"
          accessibilityState={value === v ? { selected: true } : {}}
        >
          <Text style={[styles.chipText, value === v && styles.chipTextActive]}>{label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  )
}

// Create another administrator (FR-108). Students and lecturers come from SPeCTRUM, so this is the only kind made here.
function CreateAdmin({ onCreated, onCancel }) {
  const { showToast } = useLecturer()
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (v) => { setForm(f => ({ ...f, [k]: v })); if (err) setErr(null) }

  const submit = async () => {
    const problem = newAdminError(form)
    if (problem) { setErr(problem); return }
    setBusy(true)
    try {
      await api.adminCreateAdmin(form)
      showToast(`Administrator ${form.name.trim()} created`, 'success')
      onCreated()
    } catch (e) {
      setErr(e.status === 409 ? 'An account with this email already exists.' : e.message)
    } finally {
      setBusy(false)
    }
  }

  const field = (key, label, props = {}) => (
    <View style={styles.formField}>
      <Text style={styles.label}>{label}</Text>
      <TextInput style={styles.input} value={form[key]} onChangeText={set(key)} autoCapitalize="none"
        placeholderTextColor={C.textHint} testID={`new-admin-${key}`} {...props} />
    </View>
  )

  return (
    <View style={styles.card} testID="create-admin-form">
      <Text style={styles.cardTitle}>New administrator</Text>
      <Text style={styles.hint}>Administrators sign in to this browser area with an email and password. Students and lecturers come from SPeCTRUM.</Text>
      {err && <Text style={styles.errText}>{err}</Text>}
      <View style={styles.formGrid}>
        {field('name', 'Full name', { autoCapitalize: 'words', placeholder: 'e.g. Nur Aisyah' })}
        {field('email', 'Email', { keyboardType: 'email-address', placeholder: 'name@um.edu.my' })}
        {field('password', 'Password', { secureTextEntry: true, placeholder: 'At least 8 characters' })}
        {field('confirm', 'Confirm password', { secureTextEntry: true, placeholder: 'Type it again' })}
      </View>
      <View style={styles.actions}>
        <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={onCancel} disabled={busy}>
          <Text style={styles.btnOutlineText}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btn, styles.btnPrimary, busy && styles.busy]} onPress={submit} disabled={busy}>
          {busy ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.btnPrimaryText}>Create administrator</Text>}
        </TouchableOpacity>
      </View>
    </View>
  )
}

const CONFIRM = {
  deactivate: {
    text: (u) => `Deactivate ${u.name}? They can't sign in until reactivated. Their records are kept.`,
    button: 'Confirm deactivate',
  },
  reactivate: {
    text: (u) => `Reactivate ${u.name}? They can sign in again.`,
    button: 'Confirm reactivate',
  },
  reset: {
    text: (u) => `Reset ${u.name}'s face data? Their stored face data and any submission waiting for review are deleted. They enrol again in the student app.`,
    button: 'Confirm reset',
  },
}

function AccountRow({ user, isSelf, onChanged }) {
  const { showToast } = useLecturer()
  const [confirm, setConfirm] = useState(null)   // null | 'deactivate' | 'reactivate' | 'reset'
  const [busy, setBusy] = useState(false)
  const active = user.status === 'active'

  const run = async () => {
    setBusy(true)
    try {
      if (confirm === 'deactivate') {
        await api.adminDeactivateUser(user.id)
        showToast(`Deactivated ${user.name}`, 'success')
      } else if (confirm === 'reactivate') {
        await api.adminReactivateUser(user.id)
        showToast(`Reactivated ${user.name}`, 'success')
      } else {
        await api.adminResetFaceData(user.id)
        showToast(`Face data reset for ${user.name}`, 'success')
      }
      setConfirm(null)
      onChanged()
    } catch (e) {
      showToast(confirm === 'reset' && e.status === 404 ? `${user.name} has no face data to reset` : e.message, 'error')
      setConfirm(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <View style={styles.row} testID="account-row">
      <View style={styles.rowMain}>
        <View style={styles.flex}>
          <Text style={styles.name} testID="account-name">{user.name}{isSelf ? ' (you)' : ''}</Text>
          <Text style={styles.meta}>{accountSubtitle(user)}</Text>
          <Text style={styles.meta}>{user.email}</Text>
        </View>
        <View style={styles.badges}>
          <View style={[styles.badge, active ? styles.badgeGood : styles.badgeBad]}>
            <Text style={[styles.badgeText, { color: active ? C.greenDk : C.redDk }]} testID="account-status">
              {active ? 'Active' : 'Deactivated'}
            </Text>
          </View>
          {user.role === 'student' && (
            <Text style={styles.meta}>{user.face_enrolled ? 'Face enrolled' : 'No face data'}</Text>
          )}
        </View>
      </View>

      {confirm ? (
        <View style={styles.confirmBox}>
          <Text style={styles.confirmText}>{CONFIRM[confirm].text(user)}</Text>
          <View style={styles.actions}>
            <TouchableOpacity style={[styles.btnSm, styles.btnOutline]} onPress={() => setConfirm(null)} disabled={busy}>
              <Text style={styles.btnOutlineText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.btnSm, confirm === 'reactivate' ? styles.btnPrimary : styles.btnDanger, busy && styles.busy]}
              onPress={run} disabled={busy}
            >
              {busy ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.btnPrimaryText}>{CONFIRM[confirm].button}</Text>}
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <View style={styles.rowActions}>
          {user.role === 'student' && user.face_enrolled && (
            <TouchableOpacity style={[styles.btnSm, styles.btnOutline]} onPress={() => setConfirm('reset')}>
              <Ionicons name="scan-outline" size={14} color={C.text} />
              <Text style={styles.btnOutlineText}>Reset face data</Text>
            </TouchableOpacity>
          )}
          {!isSelf && (active ? (
            <TouchableOpacity style={[styles.btnSm, styles.btnOutlineDanger]} onPress={() => setConfirm('deactivate')}>
              <Text style={[styles.btnOutlineText, { color: C.red }]}>Deactivate</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={[styles.btnSm, styles.btnOutline]} onPress={() => setConfirm('reactivate')}>
              <Text style={[styles.btnOutlineText, { color: C.primary }]}>Reactivate</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  )
}

export default function AdminAccounts() {
  const { state, openModal } = useLecturer()
  const me = state.lecturer
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [data, setData] = useState(null)        // { items, total }
  const [error, setError] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [creating, setCreating] = useState(false)
  const reqId = useRef(0)

  const load = useCallback(async () => {
    const id = ++reqId.current
    try {
      const res = await api.adminListUsers({ q: search, role, status, limit: PAGE })
      if (id !== reqId.current) return   // a newer search has started
      setData({ items: res.items, total: res.total, page: 1 })
      setError(null)
    } catch (e) {
      if (id === reqId.current) setError(e.message)
    }
  }, [search, role, status])

  // Search as the admin types, after a short pause
  useEffect(() => {
    const t = setTimeout(load, 250)
    return () => clearTimeout(t)
  }, [load])

  // Coming back to this tab (e.g. after approving a face in Face verification) shows fresh
  // statuses. The first focus is covered by the search effect above.
  const loadRef = useRef(load)
  loadRef.current = load
  const focusedBefore = useRef(false)
  useFocusEffect(useCallback(() => {
    if (focusedBefore.current) loadRef.current()
    focusedBefore.current = true
  }, []))

  const loadMore = async () => {
    setLoadingMore(true)
    try {
      const page = data.page + 1
      const res = await api.adminListUsers({ q: search, role, status, page, limit: PAGE })
      setData(d => ({ items: [...d.items, ...res.items], total: res.total, page }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title="Accounts"
        sub="Everyone who can sign in to SmartClass"
        right={(
          <TouchableOpacity onPress={() => openModal('change-password')} accessibilityLabel="Change my password" style={styles.topBtn}>
            <Ionicons name="key-outline" size={16} color={C.primary} />
            <Text style={styles.topBtnText}>Change my password</Text>
          </TouchableOpacity>
        )}
      />
      <ScrollView style={styles.flex} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.toolbar}>
          <View style={styles.searchWrap}>
            <Ionicons name="search" size={16} color={C.textHint} />
            <TextInput
              style={styles.searchInput}
              value={search}
              onChangeText={setSearch}
              placeholder="Search by name, email, matric or staff number"
              placeholderTextColor={C.textHint}
              autoCapitalize="none"
              testID="account-search"
            />
          </View>
          {!creating && (
            <TouchableOpacity style={[styles.btn, styles.btnPrimary, styles.grow0]} onPress={() => setCreating(true)}>
              <Ionicons name="person-add-outline" size={16} color="#fff" />
              <Text style={styles.btnPrimaryText}>New administrator</Text>
            </TouchableOpacity>
          )}
        </View>
        <Chips options={ROLES} value={role} onChange={setRole} testPrefix="role" />
        <Chips options={STATUSES} value={status} onChange={setStatus} testPrefix="status" />

        {creating && <CreateAdmin onCancel={() => setCreating(false)} onCreated={() => { setCreating(false); load() }} />}

        {error && (
          <TouchableOpacity style={styles.errorBox} onPress={load}>
            <Text style={styles.errText}>{error}</Text>
            <Text style={styles.retry}>Tap to retry</Text>
          </TouchableOpacity>
        )}
        {data === null && !error && <ActivityIndicator color={C.primary} style={{ marginTop: 24 }} />}
        {data && (
          <Text style={styles.count}>{data.total} {data.total === 1 ? 'account' : 'accounts'}</Text>
        )}
        {data?.items.map(u => (
          <AccountRow key={u.id} user={u} isSelf={u.id === me?.id} onChanged={load} />
        ))}
        {data && data.items.length < data.total && (
          <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={loadMore} disabled={loadingMore}>
            {loadingMore ? <ActivityIndicator color={C.primary} size="small" /> : <Text style={styles.btnOutlineText}>Show more</Text>}
          </TouchableOpacity>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 32, gap: 10 },
  toolbar: { flexDirection: 'row', gap: 10, flexWrap: 'wrap', alignItems: 'center' },
  searchWrap: {
    flex: 1, minWidth: 220, flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 12,
  },
  searchInput: { flex: 1, paddingVertical: 10, fontSize: 14, color: C.text },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: C.border, backgroundColor: C.card },
  chipActive: { backgroundColor: C.blueLt, borderColor: C.primary },
  chipText: { fontSize: 12, fontWeight: '600', color: C.textSub },
  chipTextActive: { color: C.primary },
  count: { fontSize: 12, color: C.textSub, marginTop: 4 },
  card: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, gap: 10 },
  cardTitle: { fontSize: 15, fontWeight: '700', color: C.text },
  hint: { fontSize: 12, color: C.textSub, lineHeight: 18 },
  formGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  formField: { flexGrow: 1, flexBasis: 220 },
  label: { fontSize: 12, fontWeight: '700', color: C.text, marginBottom: 4 },
  input: {
    borderWidth: 1.5, borderColor: C.border, borderRadius: 10, padding: 10, fontSize: 14, color: C.text, backgroundColor: C.bg,
  },
  row: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, gap: 10 },
  rowMain: { flexDirection: 'row', gap: 12 },
  name: { fontSize: 15, fontWeight: '700', color: C.text },
  meta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  badges: { alignItems: 'flex-end', gap: 4 },
  badge: { borderRadius: 10, paddingVertical: 3, paddingHorizontal: 8 },
  badgeGood: { backgroundColor: C.greenLt },
  badgeBad: { backgroundColor: C.redLt },
  badgeText: { fontSize: 11, fontWeight: '700' },
  rowActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap' },
  confirmBox: { backgroundColor: C.gray50, borderRadius: 8, padding: 10, gap: 10 },
  confirmText: { fontSize: 13, color: C.text, lineHeight: 19 },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap' },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 10, paddingHorizontal: 16, borderRadius: 10,
  },
  grow0: { flexGrow: 0 },
  btnSm: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    paddingVertical: 7, paddingHorizontal: 12, borderRadius: 8,
  },
  btnPrimary: { backgroundColor: C.primary },
  btnDanger: { backgroundColor: C.red },
  btnOutline: { borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card },
  btnOutlineDanger: { borderWidth: 1.5, borderColor: C.redLt, backgroundColor: C.card },
  btnPrimaryText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  btnOutlineText: { fontSize: 13, fontWeight: '600', color: C.text },
  busy: { opacity: 0.6 },
  topBtn: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  topBtnText: { fontSize: 13, fontWeight: '600', color: C.primary },
  errorBox: { backgroundColor: C.redLt, borderRadius: 8, padding: 10 },
  errText: { fontSize: 13, color: C.redDk, backgroundColor: C.redLt, borderRadius: 8, padding: 8 },
  retry: { fontSize: 12, fontWeight: '600', color: C.redDk, paddingHorizontal: 8 },
})
