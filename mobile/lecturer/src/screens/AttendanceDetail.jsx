import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  View, Text, SectionList, TouchableOpacity, TextInput, StyleSheet, RefreshControl, ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import {
  statusLabel, statusBadge, groupRoster, countStatuses, timeRange, sessionStateLabel, sessionStateBadge,
  syncInfo, moodleValueLabel, canTakeMoodle,
} from '../services/attendance'
import { C } from '../theme'

const AVATAR_BG_CYCLE = [C.blueLt, C.greenLt, C.orangeLt]
const AVATAR_CLR_CYCLE = [C.blueDk, C.greenDk, C.orangeDk]
const EXTEND_MINUTES = 15

function Count({ n, label, color, testID }) {
  return (
    <View style={styles.count}>
      <Text style={[styles.countNum, { color }]} testID={testID}>{n}</Text>
      <Text style={styles.countLbl}>{label}</Text>
    </View>
  )
}

function SmallBtn({ label, icon, onPress, variant = 'outline', disabled, testID }) {
  const v = {
    outline: [styles.smallBtnOutline, styles.smallBtnOutlineText, C.text],
    primary: [styles.smallBtnPrimary, styles.smallBtnFilledText, '#fff'],
    danger: [styles.smallBtnDanger, styles.smallBtnFilledText, '#fff'],
  }[variant]
  return (
    <TouchableOpacity
      testID={testID}
      style={[styles.smallBtn, v[0], disabled && styles.disabled]}
      onPress={onPress}
      disabled={disabled}
    >
      {icon ? <Ionicons name={icon} size={15} color={v[2]} /> : null}
      <Text style={v[1]}>{label}</Text>
    </TouchableOpacity>
  )
}

// Live controls while the class runs: extend or end early (FR-315)
function OpenControls({ session }) {
  const { doExtendSession, doCloseSession } = useLecturer()
  const [busy, setBusy] = useState(false)
  const [confirmEnd, setConfirmEnd] = useState(false)

  const run = async (fn) => {
    setBusy(true)
    try { await fn() } catch { /* toast shown in context */ } finally { setBusy(false); setConfirmEnd(false) }
  }

  if (confirmEnd) {
    return (
      <View style={styles.block}>
        <Text style={styles.blockText}>End the class now? Anyone not recorded is marked Absent and the marks are sent to SPeCTRUM.</Text>
        <View style={styles.btnRow}>
          <SmallBtn label="Keep running" onPress={() => setConfirmEnd(false)} disabled={busy} />
          <SmallBtn label={busy ? 'Ending…' : 'End now'} icon="stop-circle-outline" variant="danger" testID="session-end-confirm"
            disabled={busy} onPress={() => run(() => doCloseSession(session.id))} />
        </View>
      </View>
    )
  }
  return (
    <View style={styles.btnRow}>
      <SmallBtn label={`+${EXTEND_MINUTES} min`} icon="add-circle-outline" testID="session-extend" disabled={busy}
        onPress={() => run(() => doExtendSession(session.id, EXTEND_MINUTES))} />
      <SmallBtn label="End class" icon="stop-circle-outline" variant="danger" testID="session-end" disabled={busy}
        onPress={() => setConfirmEnd(true)} />
    </View>
  )
}

// The job couldn't tell the class was held: no recognitions and no lecturer action (FR-317)
function ConfirmHeld({ session }) {
  const { doConfirmSession } = useLecturer()
  const [busy, setBusy] = useState(false)
  const confirm = async (held) => {
    setBusy(true)
    try { await doConfirmSession(session.id, held) } catch { /* toast */ } finally { setBusy(false) }
  }
  return (
    <View style={[styles.block, styles.blockWarn]}>
      <Text style={styles.blockTitle}>Was this class held?</Text>
      <Text style={styles.blockText}>
        Nobody was recognised and no one was marked, so no one is marked Absent and nothing goes to SPeCTRUM until you confirm.
      </Text>
      <View style={styles.btnRow}>
        <SmallBtn label="Not held" icon="close-outline" testID="confirm-not-held" disabled={busy} onPress={() => confirm(false)} />
        <SmallBtn label="It was held" icon="checkmark" variant="primary" testID="confirm-held" disabled={busy} onPress={() => confirm(true)} />
      </View>
    </View>
  )
}

// SPeCTRUM (Moodle) sync status, Retry, and the conflict choice (FR-312, FR-320)
function SyncStatus({ session }) {
  const { doRetrySync, doResolveConflict } = useLecturer()
  const [busy, setBusy] = useState(null)
  const info = syncInfo(session)
  if (!info) return null

  const run = async (key, fn) => {
    setBusy(key)
    try { await fn() } catch { /* toast */ } finally { setBusy(null) }
  }

  return (
    <View style={styles.block} testID="sync-status">
      <View style={styles.rowBetween}>
        <Text style={styles.blockTitle}>SPeCTRUM attendance</Text>
        <Badge variant={info.badge} dot>{info.label}</Badge>
      </View>
      {info.detail ? <Text style={styles.blockText}>{info.detail}</Text> : null}
      {session.moodle_conflicts.map(c => (
        <View key={c.record_id} style={styles.conflict} testID="sync-conflict">
          <Text style={styles.conflictName}>{c.name} · {c.matric_no}</Text>
          <Text style={styles.conflictValues}>
            SmartClass: <Text style={styles.bold}>{statusLabel(c.smartclass_status)}</Text>
            {'   '}SPeCTRUM: <Text style={styles.bold}>{moodleValueLabel(c.moodle_status)}</Text>
          </Text>
          {c.keep_smartclass ? (
            <Text style={styles.blockText}>Keeping SmartClass&apos;s value; it is sent on the next sync.</Text>
          ) : (
            <View style={styles.btnRow}>
              <SmallBtn label="Keep SmartClass" disabled={busy != null}
                onPress={() => run(`k${c.record_id}`, () => doResolveConflict(session.id, c.record_id, 'smartclass'))} />
              <SmallBtn label="Use SPeCTRUM" disabled={busy != null || !canTakeMoodle(c)}
                onPress={() => run(`m${c.record_id}`, () => doResolveConflict(session.id, c.record_id, 'moodle'))} />
            </View>
          )}
        </View>
      ))}
      {info.canRetry ? (
        <View style={styles.btnRow}>
          <SmallBtn label={busy === 'retry' ? 'Sending…' : 'Retry now'} icon="refresh-outline" testID="sync-retry"
            disabled={busy != null} onPress={() => run('retry', () => doRetrySync(session.id))} />
        </View>
      ) : null}
    </View>
  )
}

export default function AttendanceDetail({ navigation }) {
  const { state, openModal, loadStudents } = useLecturer()
  const { students, selectedSession: session } = state
  const [search, setSearch] = useState('')
  const [sortAZ, setSortAZ] = useState(true)
  const [loading, setLoading] = useState(true)

  const sessionId = session?.id
  const status = session?.status
  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    loadStudents(sessionId, { sessionOpen: status === 'open' }).finally(() => setLoading(false))
  }, [sessionId, status])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    if (!sessionId) return
    setRefreshing(true)
    await loadStudents(sessionId, { sessionOpen: status === 'open' })
    setRefreshing(false)
  }, [loadStudents, sessionId, status])

  const sections = useMemo(() => {
    const q = search.trim().toLowerCase()
    const shown = students
      .filter(s => !q || s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q))
      .sort((a, b) => sortAZ ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name))
    return groupRoster(shown)
  }, [students, search, sortAZ])

  const counts = countStatuses(students)
  const open = status === 'open'
  const canOverride = status === 'open' || status === 'closed' || status === 'needs_confirmation'

  const title = session ? `${session.class_code} — ${session.month} ${session.day}` : 'Attendance Detail'
  const times = session?.starts_at && session?.ends_at ? timeRange(session.starts_at, session.ends_at) : session?.time
  const sub = session ? [times, open ? null : session.duration].filter(Boolean).join(' · ') : ''

  const renderItem = ({ item: s, index }) => (
    <TouchableOpacity
      style={styles.studentRow}
      testID="attendance-student"
      disabled={!canOverride}
      onPress={() => openModal('student', s)}
    >
      <View style={[styles.avatar, { backgroundColor: s.avatarBg ?? AVATAR_BG_CYCLE[index % 3] }]}>
        <Text style={[styles.avatarText, { color: s.avatarColor ?? AVATAR_CLR_CYCLE[index % 3] }]}>{s.initials}</Text>
      </View>
      <View style={styles.flex}>
        <Text style={styles.studentName}>{s.name}</Text>
        <Text style={styles.studentId}>{s.id}{s.arrivedAt ? ` · ${s.arrivedAt}` : ''}</Text>
      </View>
      <View style={styles.rowRight}>
        {s.overridden && <Text style={styles.overrideIcon}>✎ </Text>}
        <Badge variant={statusBadge(s.status)} dot>{statusLabel(s.status)}</Badge>
      </View>
    </TouchableOpacity>
  )

  const header = session ? (
    <View>
      <View style={styles.summary}>
        <View style={styles.rowBetween}>
          <Text style={styles.summaryTitle} numberOfLines={1}>{session.class_name}</Text>
          <Badge variant={sessionStateBadge(status)} dot>{sessionStateLabel(status)}</Badge>
        </View>
        <View style={styles.counts}>
          <Count n={counts.present} label="Present" color={C.green} testID="count-present" />
          <Count n={counts.late} label="Late" color={C.orange} testID="count-late" />
          <Count n={counts.excused} label="Excused" color={C.primary} testID="count-excused" />
          <Count n={counts.absent} label="Absent" color={C.red} testID="count-absent" />
          {open ? <Count n={counts.not_recorded} label="Not yet" color={C.gray500} testID="count-not-yet" /> : null}
        </View>
        {open ? (
          <View style={styles.liveRow}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>Live — updates as students are recognised</Text>
          </View>
        ) : null}
        {open ? <OpenControls session={session} /> : null}
      </View>
      {status === 'needs_confirmation' ? <ConfirmHeld session={session} /> : null}
      {status === 'closed' ? <SyncStatus session={session} /> : null}

      <View style={styles.searchBar}>
        <Ionicons name="search-outline" size={16} color={C.textHint} style={{ marginRight: 8 }} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search name or matric ID…"
          placeholderTextColor={C.textHint}
          value={search}
          onChangeText={setSearch}
        />
        {search ? (
          <TouchableOpacity onPress={() => setSearch('')} style={{ marginLeft: 8 }}>
            <Ionicons name="close-circle" size={16} color={C.textHint} />
          </TouchableOpacity>
        ) : null}
      </View>
      <View style={styles.sortRow}>
        <Text style={styles.sortLabel}>
          {students.length} enrolled{canOverride ? ' · tap a student to change their status' : ''}
        </Text>
        <TouchableOpacity style={styles.sortBtn} onPress={() => setSortAZ(v => !v)}>
          <Ionicons name="swap-vertical-outline" size={14} color={C.primary} />
          <Text style={styles.sortBtnText}>{sortAZ ? 'A–Z' : 'Z–A'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  ) : null

  return (
    <View style={styles.flex}>
      <Topbar
        title={title}
        sub={sub}
        onBack={() => navigation.goBack()}
        right={
          session && !open && status === 'closed' ? (
            <TouchableOpacity
              style={styles.exportBtn}
              onPress={() => openModal('export', {
                scope: 'session',
                id: session.id,
                filename: `attendance_${session.class_code}_${session.month}${session.day}.csv`,
                dateParams: {},
                subtitle: `${session.class_code} · ${session.day} ${session.month}`,
                sessionCount: 1,
                studentCount: students.length,
              })}
            >
              <Ionicons name="download-outline" size={14} color="#fff" />
              <Text style={styles.exportBtnText}>Export</Text>
            </TouchableOpacity>
          ) : null
        }
      />

      <SectionList
        sections={sections}
        keyExtractor={s => s.id}
        renderItem={renderItem}
        renderSectionHeader={({ section }) => section.title
          ? <Text style={styles.sectionTitle} testID={`section-${section.key}`}>{section.title}</Text>
          : null}
        stickySectionHeadersEnabled={false}
        initialNumToRender={60}
        ListHeaderComponent={header}
        ListEmptyComponent={loading
          ? <ActivityIndicator style={{ marginTop: 24 }} color={C.primary} />
          : <Text style={styles.emptyText}>{search ? 'No student matches your search.' : 'No students are enrolled in this class.'}</Text>}
        ListFooterComponent={<View style={{ height: 20 }} />}
        style={styles.list}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  list: { flex: 1 },
  exportBtn: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: C.primary,
    borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, gap: 4,
  },
  exportBtnText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  summary: {
    backgroundColor: C.card, margin: 16, marginBottom: 8, borderRadius: 12,
    borderWidth: 1, borderColor: C.border, padding: 14, gap: 10,
  },
  summaryTitle: { flex: 1, fontSize: 15, fontWeight: '700', color: C.text, marginRight: 8 },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  counts: { flexDirection: 'row', justifyContent: 'space-around' },
  count: { alignItems: 'center', minWidth: 52 },
  countNum: { fontSize: 22, fontWeight: '800' },
  countLbl: { fontSize: 11, color: C.textSub, marginTop: 1 },
  liveRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.green },
  liveText: { fontSize: 12, color: C.textSub },
  block: {
    backgroundColor: C.card, marginHorizontal: 16, marginBottom: 8, borderRadius: 12,
    borderWidth: 1, borderColor: C.border, padding: 14, gap: 8,
  },
  blockWarn: { backgroundColor: C.yellowLt, borderColor: C.yellow },
  blockTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  blockText: { fontSize: 13, color: C.textSub, lineHeight: 19 },
  btnRow: { flexDirection: 'row', gap: 8 },
  smallBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 5, paddingVertical: 10, borderRadius: 9,
  },
  smallBtnOutline: { borderWidth: 1.5, borderColor: C.border, backgroundColor: C.card },
  smallBtnPrimary: { backgroundColor: C.primary },
  smallBtnDanger: { backgroundColor: C.red },
  smallBtnOutlineText: { fontSize: 13, fontWeight: '600', color: C.text },
  smallBtnFilledText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  disabled: { opacity: 0.5 },
  conflict: { borderTopWidth: 1, borderTopColor: C.border, paddingTop: 8, gap: 6 },
  conflictName: { fontSize: 13, fontWeight: '600', color: C.text },
  conflictValues: { fontSize: 13, color: C.textSub },
  bold: { fontWeight: '700', color: C.text },
  searchBar: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: C.card,
    paddingHorizontal: 16, paddingVertical: 10, borderTopWidth: 1, borderTopColor: C.border,
    borderBottomWidth: 1, borderBottomColor: C.border, marginTop: 8,
  },
  searchInput: { flex: 1, fontSize: 14, color: C.text },
  sortRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 8, backgroundColor: C.gray50,
    borderBottomWidth: 1, borderBottomColor: C.border,
  },
  sortLabel: { fontSize: 11, color: C.textSub, flex: 1 },
  sortBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingLeft: 8 },
  sortBtnText: { fontSize: 12, color: C.primary, fontWeight: '600' },
  sectionTitle: {
    fontSize: 11, fontWeight: '700', color: C.textHint, textTransform: 'uppercase', letterSpacing: 0.8,
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 6, backgroundColor: C.bg,
  },
  studentRow: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: C.border, gap: 12, backgroundColor: C.card,
  },
  avatar: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 14, fontWeight: '600' },
  studentName: { fontSize: 14, fontWeight: '500', color: C.text },
  studentId: { fontSize: 12, color: C.textSub, marginTop: 1 },
  rowRight: { flexDirection: 'row', alignItems: 'center' },
  overrideIcon: { fontSize: 11, color: C.textHint, marginRight: 4 },
  emptyText: { fontSize: 13, color: C.textSub, textAlign: 'center', paddingVertical: 24 },
})
