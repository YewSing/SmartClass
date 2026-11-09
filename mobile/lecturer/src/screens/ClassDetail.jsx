import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  View, Text, TextInput, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import { getClassStudents } from '../services/api'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

function StudentRow({ student }) {
  return (
    <View style={styles.row} testID="class-student">
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>{student.initials}</Text>
      </View>
      <View style={styles.rowText}>
        <Text style={styles.name} testID="class-student-name">{student.name}</Text>
        <Text style={styles.matric}>{student.matric}</Text>
      </View>
      <Badge variant={student.faceEnrolled ? 'green' : 'gray'}>
        {student.faceEnrolled ? 'Face registered' : 'No face data'}
      </Badge>
    </View>
  )
}

export default function ClassDetail({ route, navigation }) {
  const { classId } = route.params
  const { state, loadAllClasses } = useLecturer()
  const cls = state.allClasses.find(c => c.id === classId)

  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    try {
      setStudents(await getClassStudents(classId))
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [classId])

  useEffect(() => {
    load().finally(() => setLoading(false))
    if (!cls) loadAllClasses()
  }, [load])

  const onRefresh = async () => {
    setRefreshing(true)
    await load()
    setRefreshing(false)
  }

  const retry = () => {
    setLoading(true)
    load().finally(() => setLoading(false))
  }

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return students
    return students.filter(s => s.name.toLowerCase().includes(q) || s.matric.toLowerCase().includes(q))
  }, [students, search])

  const typeLabel = cls ? (cls.type === 'LECTURE' ? 'Lecture' : (cls.label ?? 'Tutorial')) : null
  const count = students.length

  const header = (
    <View>
      <View style={styles.card}>
        <Text style={styles.code}>{cls?.code ?? ''}</Text>
        <Text style={styles.courseName} testID="class-detail-name">{cls?.name ?? ''}</Text>
        {cls ? (
          <>
            <View style={styles.metaRow}>
              <Ionicons name="time-outline" size={14} color={C.textSub} />
              <Text style={styles.meta}>
                {typeLabel} · {cls.day_of_week} {cls.start_time}–{cls.end_time}
              </Text>
            </View>
            {cls.room ? (
              <View style={styles.metaRow}>
                <Ionicons name="location-outline" size={14} color={C.textSub} />
                <Text style={styles.meta}>{cls.room}</Text>
              </View>
            ) : null}
          </>
        ) : null}
      </View>

      <View style={styles.listHeader}>
        <Text style={styles.listTitle} testID="class-student-count">
          {count} student{count === 1 ? '' : 's'}
        </Text>
        <Text style={styles.listHint}>From SPeCTRUM</Text>
      </View>

      {count > 0 ? (
        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={16} color={C.textHint} />
          <TextInput
            style={styles.searchInput}
            value={search}
            onChangeText={setSearch}
            placeholder="Search name or matric no."
            placeholderTextColor={C.textHint}
            autoCorrect={false}
          />
        </View>
      ) : null}
    </View>
  )

  let empty = <Text style={styles.emptyText}>No students are enrolled in this class yet.</Text>
  if (count > 0) empty = <Text style={styles.emptyText}>No student matches your search.</Text>

  return (
    <View style={styles.flex}>
      <Topbar title="Class details" sub={cls?.code} onBack={() => navigation.goBack()} />
      {loading ? (
        <ActivityIndicator style={styles.spinner} color={C.primary} />
      ) : error ? (
        <View style={styles.errorBox}>
          <Text style={styles.emptyText}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={retry}>
            <Text style={styles.retryText}>Try again</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={shown}
          keyExtractor={s => String(s.id)}
          renderItem={({ item }) => <StudentRow student={item} />}
          ListHeaderComponent={header}
          ListEmptyComponent={empty}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.primary} colors={[C.primary]} />}
        />
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  spinner: { marginTop: 40 },
  list: { padding: 16, paddingBottom: 32 },
  card: {
    backgroundColor: C.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 14,
    gap: 4,
    marginBottom: 16,
  },
  code: { fontSize: 12, fontWeight: '600', color: C.textSub },
  courseName: { fontSize: 16, fontWeight: '700', color: C.text, marginBottom: 4 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  meta: { flex: 1, fontSize: 13, color: C.textSub },
  listHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  listTitle: { fontSize: 14, fontWeight: '700', color: C.text },
  listHint: { fontSize: 12, color: C.textHint },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: C.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.border,
    paddingHorizontal: 12,
    marginBottom: 10,
  },
  searchInput: { flex: 1, fontSize: 14, color: C.text, paddingVertical: 9 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: C.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.border,
    padding: 12,
    marginBottom: 8,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontSize: 13, fontWeight: '700', color: C.primary },
  rowText: { flex: 1 },
  name: { fontSize: 14, fontWeight: '600', color: C.text },
  matric: { fontSize: 12, color: C.textSub, marginTop: 1 },
  emptyText: { fontSize: 13, color: C.textSub, textAlign: 'center', paddingVertical: 24 },
  errorBox: { alignItems: 'center', padding: 24 },
  retryBtn: { backgroundColor: C.primary, borderRadius: 8, paddingHorizontal: 16, paddingVertical: 9 },
  retryText: { fontSize: 13, fontWeight: '700', color: '#fff' },
})
