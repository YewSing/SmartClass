import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useLecturer } from '../context/LecturerContext'
import Topbar from '../components/Topbar'
import Badge from '../components/Badge'
import { C } from '../theme'

const SENSORS = [
  { icon: 'thermometer-outline', iconColor: C.red,     name: 'Temperature', val: '26.4', unit: '°C',  status: 'Normal', variant: 'green', warn: false },
  { icon: 'water-outline',       iconColor: C.primary, name: 'Humidity',    val: '61',   unit: '%',   status: 'Normal', variant: 'green', warn: false },
  { icon: 'cloud-outline',       iconColor: C.yellow,  name: 'CO₂ Level',   val: '1240', unit: 'ppm', status: 'Elevated', variant: 'yellow', warn: true },
  { icon: 'sunny-outline',       iconColor: '#E87722', name: 'Light Level', val: '420',  unit: 'lux', status: 'Normal', variant: 'green', warn: false },
]

export default function Environment({ navigation }) {
  const { openModal } = useLecturer()

  return (
    <View style={styles.flex}>
      <Topbar
        title="Environment Control"
        sub="DK 6, BLI Building · Live sensors"
        right={
          <View style={styles.liveRow}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>Live</Text>
          </View>
        }
      />
      <ScrollView style={styles.flex} showsVerticalScrollIndicator={false}>
        {/* CO2 alert */}
        <View style={styles.alertBanner}>
          <Ionicons name="warning-outline" size={16} color={C.yellowDk} style={{ flexShrink: 0, marginTop: 1 }} />
          <Text style={styles.alertMsg}>
            CO₂ level elevated at 1240 ppm — ventilation recommended. Threshold: 1000 ppm.
          </Text>
        </View>

        {/* Section header */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Sensor Readings</Text>
          <Text style={styles.sectionSub}>Updated 10:14 AM</Text>
        </View>

        {/* 2x2 sensor grid */}
        <View style={styles.sensorGrid}>
          {SENSORS.map(s => (
            <View key={s.name} style={[styles.sensorCard, s.warn && styles.sensorCardWarn]}>
              <Ionicons name={s.icon} size={24} color={s.iconColor} style={{ marginBottom: 6 }} />
              <Text style={styles.sensorName}>{s.name}</Text>
              <Text style={styles.sensorVal}>
                {s.val}<Text style={styles.sensorUnit}> {s.unit}</Text>
              </Text>
              <View style={{ marginTop: 8 }}>
                <Badge variant={s.variant}>{s.status}</Badge>
              </View>
            </View>
          ))}
        </View>

        {/* Occupancy full-width */}
        <View style={styles.occupancyCard}>
          <View style={styles.occupancyLeft}>
            <Ionicons name="people-outline" size={24} color={C.gray500} style={{ marginBottom: 4 }} />
            <Text style={styles.sensorName}>Occupancy</Text>
            <Text style={styles.sensorVal}>
              23<Text style={styles.sensorUnit}> / 30 seats</Text>
            </Text>
          </View>
          <Badge variant="green">Normal</Badge>
        </View>

        {/* Actuation Control */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Actuation Control</Text>
        </View>

        {/* Lights */}
        <View style={styles.actuationCard}>
          <View style={[styles.actIcon, { backgroundColor: C.yellowLt }]}>
            <Ionicons name="bulb-outline" size={20} color={C.yellow} />
          </View>
          <View style={styles.actInfo}>
            <Text style={styles.actName}>Lights</Text>
            <Text style={styles.actStatus}>
              Auto Mode · <Text style={{ color: C.green, fontWeight: '700' }}>ON</Text>
            </Text>
          </View>
          <Badge variant="green" style={{ marginRight: 8 }}>Auto</Badge>
          <TouchableOpacity style={styles.overrideBtn} onPress={() => openModal('override-lights')}>
            <Text style={styles.overrideBtnText}>Override</Text>
          </TouchableOpacity>
        </View>

        {/* AC */}
        <View style={styles.actuationCard}>
          <View style={[styles.actIcon, { backgroundColor: C.blueLt }]}>
            <Ionicons name="snow-outline" size={20} color={C.primary} />
          </View>
          <View style={styles.actInfo}>
            <Text style={styles.actName}>Air Conditioning</Text>
            <Text style={styles.actStatus}>
              Auto Mode · <Text style={{ color: C.green, fontWeight: '700' }}>ON</Text> · Set 23°C
            </Text>
          </View>
          <Badge variant="green" style={{ marginRight: 8 }}>Auto</Badge>
          <TouchableOpacity style={styles.overrideBtn} onPress={() => openModal('override-ac')}>
            <Text style={styles.overrideBtnText}>Override</Text>
          </TouchableOpacity>
        </View>

        <View style={{ height: 20 }} />
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: C.bg },
  liveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: C.green,
  },
  liveText: {
    fontSize: 12,
    color: C.greenDk,
    fontWeight: '700',
  },
  alertBanner: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
    backgroundColor: C.yellowLt,
    borderLeftWidth: 4,
    borderLeftColor: C.yellow,
    padding: 12,
    margin: 16,
    marginBottom: 8,
    borderRadius: 8,
  },
  alertMsg: {
    flex: 1,
    fontSize: 13,
    color: C.yellowDk,
    lineHeight: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: C.textSub,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  sectionSub: {
    fontSize: 11,
    color: C.textHint,
  },
  sensorGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 16,
    gap: 10,
  },
  sensorCard: {
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: C.border,
    width: '47%',
    alignItems: 'center',
  },
  sensorCardWarn: {
    borderColor: C.yellow,
    backgroundColor: C.yellowLt,
  },
  sensorName: {
    fontSize: 12,
    color: C.textSub,
    marginBottom: 4,
    textAlign: 'center',
  },
  sensorVal: {
    fontSize: 22,
    fontWeight: '800',
    color: C.text,
    textAlign: 'center',
  },
  sensorUnit: {
    fontSize: 13,
    fontWeight: '400',
    color: C.textSub,
  },
  occupancyCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginHorizontal: 16,
    marginTop: 10,
    borderWidth: 1,
    borderColor: C.border,
  },
  occupancyLeft: {
    flex: 1,
  },
  actuationCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: C.card,
    borderRadius: 12,
    padding: 14,
    marginHorizontal: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.border,
    gap: 10,
  },
  actIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actInfo: {
    flex: 1,
  },
  actName: {
    fontSize: 14,
    fontWeight: '700',
    color: C.text,
  },
  actStatus: {
    fontSize: 12,
    color: C.textSub,
    marginTop: 2,
  },
  overrideBtn: {
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  overrideBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: C.text,
  },
})
