import { useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import ModalRouter from '../components/Modals'
import { C } from '../theme'

const INFO_FIELDS = (lecturer) => [
  { icon: 'card-outline',     bg: C.blueLt,   color: C.primary,  label: 'Staff ID',   value: lecturer?.staffId },
  { icon: 'mail-outline',     bg: C.blueLt,   color: C.primary,  label: 'Email',      value: lecturer?.email },
  { icon: 'business-outline', bg: C.greenLt,  color: C.green,    label: 'Department', value: lecturer?.faculty },
  { icon: 'shield-outline',   bg: C.orangeLt, color: C.orange,   label: 'Role',       value: 'Lecturer' },
]

const ACTIONS = [
  { icon: 'lock-closed-outline', bg: C.yellowLt, color: C.yellowDk, label: 'Change Password',         type: 'change-password', danger: false },
  { icon: 'time-outline',        bg: C.greenLt,  color: C.greenDk,  label: 'Session & Login Activity', type: 'session-info',    danger: false },
  { icon: 'log-out-outline',     bg: C.redLt,    color: C.red,       label: 'Sign Out',                 type: 'signout',         danger: true  },
]

export default function Profile({ navigation }) {
  const { state, openModal, loadAllClasses } = useLecturer()
  const { lecturer, allClasses } = state

  useEffect(() => { loadAllClasses() }, [])

  // Group by course code
  const courseMap = {}
  for (const c of allClasses) {
    if (!courseMap[c.code]) courseMap[c.code] = { name: c.name, occs: [] }
    courseMap[c.code].occs.push(c)
  }
  const courses = Object.entries(courseMap)
  const initials = lecturer?.initials ?? '??'

  return (
    <View style={styles.flex}>
      <Topbar title="My Profile" onBack={() => navigation.goBack()} />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <View style={styles.heroAvatar}>
            <Text style={styles.heroInitials}>{initials}</Text>
          </View>
          <Text style={styles.heroName}>{lecturer?.name ?? '—'}</Text>
          <Text style={styles.heroEmail}>{lecturer?.email ?? '—'}</Text>
          <View style={styles.heroRoleBadge}>
            <Ionicons name="school" size={12} color={C.primary} />
            <Text style={styles.heroRoleText}>Lecturer</Text>
          </View>
        </View>

        {/* Account info */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Account Information</Text>
          {INFO_FIELDS(lecturer).map(f => (
            <View key={f.label} style={styles.profileField}>
              <View style={[styles.fieldIcon, { backgroundColor: f.bg }]}>
                <Ionicons name={f.icon} size={16} color={f.color} />
              </View>
              <View style={styles.fieldContent}>
                <Text style={styles.fieldLabel}>{f.label}</Text>
                <Text style={styles.fieldValue}>{f.value ?? '—'}</Text>
              </View>
            </View>
          ))}
          <View style={styles.adminNote}>
            <Ionicons name="information-circle-outline" size={13} color={C.textHint} style={{ flexShrink: 0 }} />
            <Text style={styles.adminNoteText}>
              Profile details are managed by your system administrator. Contact IT Services to update your name, email, or department.
            </Text>
          </View>
        </View>

        {/* Assigned classes */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Assigned Classes — Current Semester</Text>
          {courses.length === 0 ? (
            <View style={styles.profileField}>
              <Text style={styles.noClassText}>No classes assigned</Text>
            </View>
          ) : courses.map(([code, { name, occs }]) => (
            <View key={code} style={[styles.profileField, { flexDirection: 'column', gap: 8 }]}>
              <View style={styles.courseHeader}>
                <View style={[styles.fieldIcon, { backgroundColor: C.blueLt }]}>
                  <Ionicons name="book-outline" size={16} color={C.primary} />
                </View>
                <View style={styles.fieldContent}>
                  <Text style={styles.fieldLabel}>{code}</Text>
                  <Text style={styles.fieldValue}>{name}</Text>
                </View>
              </View>
              <View style={styles.occsContainer}>
                {occs.map(o => (
                  <View key={o.id} style={styles.occRow}>
                    <Badge variant={o.type === 'LECTURE' ? 'blue' : 'green'} style={styles.occBadge}>
                      {o.type === 'LECTURE' ? 'Lec' : (o.label ?? 'Tut')}
                    </Badge>
                    <Text style={styles.occText} numberOfLines={1}>
                      {o.day_of_week} {o.start_time}–{o.end_time}{o.room ? ` · ${o.room}` : ''}
                    </Text>
                    <Badge variant="gray" style={styles.occBadge}>{o.enrolled_count} students</Badge>
                  </View>
                ))}
              </View>
            </View>
          ))}
        </View>

        {/* Account actions */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Account</Text>
          {ACTIONS.map(a => (
            <TouchableOpacity
              key={a.type}
              style={[styles.actionRow, a.danger && styles.actionRowDanger]}
              onPress={() => openModal(a.type)}
            >
              <View style={[styles.fieldIcon, { backgroundColor: a.bg }]}>
                <Ionicons name={a.icon} size={16} color={a.color} />
              </View>
              <Text style={[styles.actionLabel, a.danger && styles.actionLabelDanger]}>{a.label}</Text>
              <Ionicons name="chevron-forward" size={16} color={a.danger ? C.red : C.gray300} />
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.footer}>
          SmartClass Lecturer App · v1.0.0 · University of Malaya
        </Text>
      </ScrollView>
      <ModalRouter navigation={navigation} />
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  hero: {
    alignItems: 'center',
    paddingVertical: 28,
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    marginBottom: 12,
  },
  heroAvatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: C.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  heroInitials: {
    fontSize: 26,
    fontWeight: '800',
    color: '#fff',
  },
  heroName: {
    fontSize: 20,
    fontWeight: '700',
    color: C.text,
    marginBottom: 2,
  },
  heroEmail: {
    fontSize: 13,
    color: C.textSub,
    marginBottom: 10,
  },
  heroRoleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: C.blueLt,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  heroRoleText: {
    fontSize: 12,
    fontWeight: '700',
    color: C.primary,
  },
  section: {
    backgroundColor: C.card,
    borderRadius: 12,
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: C.border,
    gap: 4,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: C.textHint,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  profileField: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  fieldIcon: {
    width: 36,
    height: 36,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  fieldContent: {
    flex: 1,
  },
  fieldLabel: {
    fontSize: 11,
    color: C.textSub,
    marginBottom: 1,
  },
  fieldValue: {
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  adminNote: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
    marginTop: 10,
    padding: 10,
    backgroundColor: C.gray50,
    borderRadius: 8,
  },
  adminNoteText: {
    flex: 1,
    fontSize: 12,
    color: C.textHint,
    lineHeight: 18,
  },
  noClassText: {
    fontSize: 13,
    color: C.textHint,
  },
  courseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  occsContainer: {
    paddingLeft: 48,
    gap: 6,
  },
  occRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flexWrap: 'wrap',
  },
  occBadge: {
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  occText: {
    flex: 1,
    fontSize: 12,
    color: C.textSub,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
  },
  actionRowDanger: {
    // subtle highlight
  },
  actionLabel: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  actionLabelDanger: {
    color: C.red,
  },
  footer: {
    textAlign: 'center',
    padding: 16,
    paddingBottom: 32,
    fontSize: 11,
    color: C.textHint,
  },
})
