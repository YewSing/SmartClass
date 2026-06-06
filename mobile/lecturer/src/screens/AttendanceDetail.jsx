import { useState, useEffect, useCallback } from 'react'
import {
  View, Text, FlatList, TouchableOpacity, TextInput, StyleSheet, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

const AVATAR_BG_CYCLE = [C.blueLt, C.greenLt, C.orangeLt]
const AVATAR_CLR_CYCLE = [C.blueDk, C.greenDk, C.orangeDk]

export default function AttendanceDetail({ navigation }) {
  const { state, openModal, loadStudents } = useLecturer()
  const { students, selectedSession } = state
  const [search, setSearch] = useState('')
  const [sortAZ, setSortAZ] = useState(true)

  useEffect(() => {
    if (selectedSession?.id) loadStudents(selectedSession.id)
  }, [selectedSession?.id])

  const [refreshing, setRefreshing] = useState(false)
  const onRefresh = useCallback(async () => {
    if (!selectedSession?.id) return
    setRefreshing(true)
    await loadStudents(selectedSession.id)
    setRefreshing(false)
  }, [loadStudents, selectedSession?.id])

  const filtered = [...students]
    .filter(s =>
      s.name.toLowerCase().includes(search.toLowerCase()) || s.id.includes(search)
    )
    .sort((a, b) => sortAZ ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name))

  const present = students.filter(s => s.status === 'present').length
  const absent  = students.filter(s => s.status === 'absent').length
  const unid    = students.filter(s => s.status === 'unidentified').length

  const sessionTitle = selectedSession
    ? `${selectedSession.class_code} — ${selectedSession.month} ${selectedSession.day}`
    : 'Attendance Detail'
  const sessionSub = selectedSession
    ? `${selectedSession.time}${selectedSession.open ? ' · Open' : selectedSession.duration ? ` · ${selectedSession.duration}` : ''}`
    : ''

  const renderItem = ({ item: s, index }) => {
    const bgColor = s.avatarBg ?? AVATAR_BG_CYCLE[index % 3]
    const fgColor = s.avatarColor ?? AVATAR_CLR_CYCLE[index % 3]
    const statusVariant = s.status === 'present' ? 'green' : s.status === 'absent' ? 'red' : 'orange'
    const statusLabel = s.status === 'present' ? 'Present' : s.status === 'absent' ? 'Absent' : 'Unidentified'
    return (
      <TouchableOpacity style={styles.studentRow} onPress={() => openModal('student', s)}>
        <View style={[styles.avatar, { backgroundColor: bgColor }]}>
          <Text style={[styles.avatarText, { color: fgColor }]}>{s.initials}</Text>
        </View>
        <View style={styles.flex}>
          <Text style={styles.studentName}>{s.name}</Text>
          <Text style={styles.studentId}>{s.id}</Text>
        </View>
        <View style={styles.rowRight}>
          {s.overridden && <Text style={styles.overrideIcon}>✎ </Text>}
          <Badge variant={statusVariant} dot>{statusLabel}</Badge>
        </View>
      </TouchableOpacity>
    )
  }

  return (
    <View style={styles.flex}>
      <Topbar
        title={sessionTitle}
        sub={sessionSub}
        onBack={() => navigation.goBack()}
        right={
          selectedSession?.open
            ? <Badge variant="green" dot>Open</Badge>
            : selectedSession
              ? (
                <TouchableOpacity
                  style={styles.exportBtn}
                  onPress={() => openModal('export', {
                    scope: 'session',
                    id: selectedSession.id,
                    filename: `attendance_${selectedSession.class_code}_${selectedSession.month}${selectedSession.day}.csv`,
                    dateParams: {},
                    subtitle: `${selectedSession.class_code} · ${selectedSession.day} ${selectedSession.month}`,
                    sessionCount: 1,
                    studentCount: students.length,
                  })}
                >
                  <Ionicons name="download-outline" size={14} color="#fff" />
                  <Text style={styles.exportBtnText}>Export</Text>
                </TouchableOpacity>
              )
              : null
        }
      />

      {/* Search bar */}
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

      {/* Sort row */}
      <View style={styles.sortRow}>
        <Text style={styles.sortLabel}>
          {students.length} enrolled · {present} present · {absent} absent{unid > 0 ? ` · ${unid} unidentified` : ''}
        </Text>
        <TouchableOpacity style={styles.sortBtn} onPress={() => setSortAZ(v => !v)}>
          <Ionicons name="swap-vertical-outline" size={14} color={C.primary} />
          <Text style={styles.sortBtnText}>{sortAZ ? 'A–Z' : 'Z–A'}</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={filtered}
        keyExtractor={s => s.id}
        renderItem={renderItem}
        ListFooterComponent={<View style={{ height: 20 }} />}
        style={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
      />

    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  exportBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    gap: 4,
  },
  exportBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
  list: { flex: 1, backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: C.text,
  },
  sortRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: C.gray50,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  sortLabel: {
    fontSize: 11,
    color: C.textSub,
    flex: 1,
  },
  sortBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingLeft: 8,
  },
  sortBtnText: {
    fontSize: 12,
    color: C.primary,
    fontWeight: '600',
  },
  studentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    gap: 12,
    backgroundColor: C.card,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 14,
    fontWeight: '600',
  },
  studentName: {
    fontSize: 14,
    fontWeight: '500',
    color: C.text,
  },
  studentId: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 1,
  },
  rowRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  overrideIcon: {
    fontSize: 11,
    color: C.textHint,
    marginRight: 4,
  },
})
