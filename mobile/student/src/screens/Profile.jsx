import { useEffect } from 'react'
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import Badge from '../components/Badge'
import { C } from '../theme'

const ACCOUNT_FIELDS = (s) => [
  { icon: 'card-outline',     bg: C.blueLt,   color: C.primary,   label: 'Matric Number',   value: s?.matricNo },
  { icon: 'mail-outline',     bg: C.blueLt,   color: C.primary,   label: 'Email',           value: s?.email },
  { icon: 'school-outline',   bg: C.greenLt,  color: C.green,     label: 'Programme',       value: s?.programme },
  { icon: 'business-outline', bg: C.yellowLt, color: C.yellowDk,  label: 'Faculty',         value: s?.faculty },
  { icon: 'layers-outline',   bg: C.orangeLt, color: C.orange,    label: 'Year / Semester', value: s?.yearSem },
]

export default function Profile() {
  const { state, loadClasses, openModal } = useStudent()
  const { student, classes } = state
  const insets = useSafeAreaInsets()

  useEffect(() => { loadClasses() }, [loadClasses])

  const initials = student?.initials ?? '??'

  const confirmSignOut = () => openModal('signout')
  const handleChangePassword = () => openModal('change-password')

  return (
    <View style={styles.flex}>
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <Text style={styles.headerTitle}>My Profile</Text>
        <Text style={styles.headerSub}>Student Portal · University of Malaya</Text>
      </View>

      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <View style={styles.heroAvatar}>
            <Text style={styles.heroInitials}>{initials}</Text>
          </View>
          <Text style={styles.heroName}>{student?.name ?? '—'}</Text>
          <Text style={styles.heroEmail}>{student?.email ?? '—'}</Text>
          <View style={styles.heroRoleBadge}>
            <Text style={styles.heroRoleText}>STUDENT</Text>
          </View>
        </View>

        {/* Account details */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Account Details</Text>
          {ACCOUNT_FIELDS(student).map(f => (
            <View key={f.label} style={styles.profileField}>
              <View style={[styles.fieldIcon, { backgroundColor: f.bg }]}>
                <Ionicons name={f.icon} size={16} color={f.color} />
              </View>
              <View style={styles.fieldContent}>
                <Text style={styles.fieldLabel}>{f.label}</Text>
                <Text style={styles.fieldValue}>{f.value || '—'}</Text>
              </View>
            </View>
          ))}
        </View>

        {/* Enrolled classes */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Enrolled Classes — Current Semester</Text>
          {classes.length === 0 ? (
            <View style={styles.profileField}>
              <Text style={styles.noClassText}>No enrolled classes</Text>
            </View>
          ) : classes.map(cls => (
            <View key={cls.id} style={styles.classCard}>
              <View style={styles.classRow1}>
                <Text style={styles.classCode}>{cls.code}</Text>
                <Badge
                  variant={cls.type === 'LECTURE' ? 'blue' : 'green'}
                  style={styles.classBadge}
                  textStyle={styles.classBadgeText}
                >
                  {cls.type === 'LECTURE' ? 'Lecture' : (cls.label ?? 'Tut')}
                </Badge>
              </View>
              <Text style={styles.className}>{cls.name}</Text>
              <Text style={styles.classTime}>
                {cls.day_of_week} {cls.start_time}–{cls.end_time}
                {cls.venue ? ` · ${cls.venue}` : ''}
              </Text>
            </View>
          ))}
        </View>

        {/* Account actions */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Account</Text>
          <TouchableOpacity style={styles.actionRow} onPress={handleChangePassword}>
            <View style={[styles.fieldIcon, { backgroundColor: C.yellowLt }]}>
              <Ionicons name="lock-closed-outline" size={16} color={C.yellowDk} />
            </View>
            <Text style={styles.actionLabel}>Change Password</Text>
            <Ionicons name="chevron-forward" size={16} color={C.gray300} />
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionRow, { borderBottomWidth: 0 }]} onPress={confirmSignOut}>
            <View style={[styles.fieldIcon, { backgroundColor: C.redLt }]}>
              <Ionicons name="log-out-outline" size={16} color={C.red} />
            </View>
            <Text style={[styles.actionLabel, { color: C.red }]}>Sign Out</Text>
            <Ionicons name="chevron-forward" size={16} color={C.red} />
          </TouchableOpacity>
        </View>

        <Text style={styles.footer}>SmartClass Student App · v1.0.0 · University of Malaya</Text>
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  header: {
    backgroundColor: C.card,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    paddingHorizontal: 16,
    paddingBottom: 10,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: C.text,
  },
  headerSub: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 2,
  },
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
    backgroundColor: C.blueLt,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  heroRoleText: {
    fontSize: 11,
    fontWeight: '700',
    color: C.primary,
    letterSpacing: 0.6,
  },
  section: {
    backgroundColor: C.card,
    borderRadius: 12,
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: C.border,
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
  noClassText: {
    fontSize: 13,
    color: C.textHint,
  },
  classCard: {
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: C.border,
    gap: 6,
  },
  classRow1: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  classCode: {
    fontSize: 12,
    fontWeight: '600',
    color: C.textSub,
  },
  classBadge: {
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  classBadgeText: {
    fontWeight: '500',
  },
  className: {
    fontSize: 15,
    fontWeight: '600',
    color: C.text,
  },
  classTime: {
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
  actionLabel: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: C.text,
  },
  footer: {
    textAlign: 'center',
    padding: 16,
    paddingBottom: 32,
    fontSize: 11,
    color: C.textHint,
  },
})
