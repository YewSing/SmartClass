// Building blocks of the student live class and "My questions" screens (S38). Same look as the
// lecturer app's interaction parts (S37): white cards, subtle borders, one primary blue.
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { pollBars } from '../services/interaction'
import { C } from '../theme'

export function Card({ children, style, testID }) {
  return <View style={[s.card, style]} testID={testID}>{children}</View>
}

export function Muted({ children, testID, style }) {
  return <Text style={[s.muted, style]} testID={testID}>{children}</Text>
}

export function Loading({ text = 'Loading…' }) {
  return (
    <Card style={s.center}>
      <ActivityIndicator color={C.primary} />
      <Muted>{text}</Muted>
    </Card>
  )
}

export function LoadError({ title = "Couldn't load the class", message, onRetry, testID = 'live-error' }) {
  return (
    <Card style={s.errorCard} testID={testID}>
      <Ionicons name="cloud-offline-outline" size={18} color={C.redDk} />
      <View style={s.flex1}>
        <Text style={s.errorTitle}>{title}</Text>
        {message ? <Text style={s.errorText}>{message}</Text> : null}
      </View>
      <TouchableOpacity onPress={onRetry} style={s.retry} testID={`${testID}-retry`} accessibilityRole="button">
        <Text style={s.retryText}>Retry</Text>
      </TouchableOpacity>
    </Card>
  )
}

// Small action button: `primary` (blue) or outlined; `subtle` is grey text
export function Btn({ label, icon, onPress, kind = 'outline', disabled, testID, busy, accessibilityLabel }) {
  const solid = kind === 'primary'
  const color = solid ? '#fff' : kind === 'subtle' ? C.textSub : C.text
  return (
    <TouchableOpacity
      style={[s.btn, solid && s.btnPrimary, !solid && s.btnOutline, (disabled || busy) && s.btnDisabled]}
      onPress={onPress} disabled={disabled || busy} testID={testID} accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled: !!(disabled || busy) }}
    >
      {icon ? <Ionicons name={icon} size={14} color={color} /> : null}
      <Text style={[s.btnText, { color }]}>{busy ? '…' : label}</Text>
    </TouchableOpacity>
  )
}

export function Toggle({ label, value, onChange, disabled, testID }) {
  return (
    <TouchableOpacity
      style={[s.toggle, disabled && s.btnDisabled]} onPress={() => onChange(!value)} disabled={disabled}
      testID={testID} accessibilityRole="checkbox" accessibilityState={{ checked: !!value, disabled: !!disabled }}
    >
      <View style={[s.box, value && s.boxOn]}>
        {value ? <Ionicons name="checkmark" size={12} color="#fff" /> : null}
      </View>
      <Text style={s.toggleText}>{label}</Text>
    </TouchableOpacity>
  )
}

export function Segments({ items, value, onChange }) {
  return (
    <View style={s.segments} accessibilityRole="tablist">
      {items.map(it => (
        <TouchableOpacity
          key={it.key} onPress={() => onChange(it.key)} testID={`live-tab-${it.key}`}
          style={[s.segment, value === it.key && s.segmentOn]} accessibilityRole="tab"
          accessibilityState={{ selected: value === it.key }}
        >
          <Text style={[s.segmentText, value === it.key && s.segmentTextOn]}>
            {it.label}{it.count ? ` (${it.count})` : ''}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  )
}

// One poll option to pick: a round mark for single choice, a box for multiple choice
export function OptionPick({ text, selected, multiple, disabled, onPress, testID }) {
  return (
    <TouchableOpacity
      style={[s.option, selected && s.optionOn, disabled && s.optionDisabled]} onPress={onPress} disabled={disabled}
      testID={testID} accessibilityRole={multiple ? 'checkbox' : 'radio'}
      accessibilityState={{ checked: !!selected, disabled: !!disabled }} accessibilityLabel={text}
    >
      <View style={[multiple ? s.box : s.radio, selected && s.boxOn]}>
        {selected ? <Ionicons name="checkmark" size={12} color="#fff" /> : null}
      </View>
      <Text style={s.optionText}>{text}</Text>
    </TouchableOpacity>
  )
}

// Poll results as bars; the student's own choice is marked
export function PollResults({ poll }) {
  const bars = pollBars(poll)
  if (!bars.length) return null
  return (
    <View style={s.bars} testID="live-poll-results">
      {bars.map(o => (
        <View key={o.id}>
          <View style={s.barLabelRow}>
            <Text style={[s.barLabel, o.mine && s.barLabelMine]} numberOfLines={2}>
              {o.text}{o.mine ? ' (your vote)' : ''}
            </Text>
            <Text style={s.barValue}>{o.votes} · {o.pct}%</Text>
          </View>
          <View style={s.barTrack}>
            <View style={[s.barFill, { width: `${o.pct}%` }]} />
          </View>
        </View>
      ))}
    </View>
  )
}

export const ixStyles = StyleSheet.create({
  input: {
    borderWidth: 1, borderColor: C.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8,
    fontSize: 14, color: C.text, backgroundColor: C.card,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  formError: { fontSize: 12, color: C.redDk },
  label: { fontSize: 12, fontWeight: '500', color: C.textSub },
  title: { fontSize: 14, fontWeight: '600', color: C.text },
  meta: { fontSize: 12, color: C.textSub },
  heading: {
    fontSize: 11, fontWeight: '600', color: C.textHint, textTransform: 'uppercase', letterSpacing: 0.8,
    paddingVertical: 6, marginBottom: 4,
  },
})

const s = StyleSheet.create({
  flex1: { flex: 1 },
  card: {
    backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, marginBottom: 10,
  },
  center: { alignItems: 'center', gap: 8 },
  muted: { fontSize: 13, color: C.textSub, paddingVertical: 4 },
  errorCard: { flexDirection: 'row', alignItems: 'center', gap: 10, borderColor: C.redLt, backgroundColor: C.redLt },
  errorTitle: { fontSize: 13, fontWeight: '600', color: C.redDk },
  errorText: { fontSize: 12, color: C.redDk, marginTop: 2 },
  retry: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: C.card, borderWidth: 1, borderColor: C.border },
  retryText: { fontSize: 13, fontWeight: '600', color: C.text },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8,
  },
  btnPrimary: { backgroundColor: C.primary },
  btnOutline: { borderWidth: 1, borderColor: C.border, backgroundColor: C.card },
  btnDisabled: { opacity: 0.45 },
  btnText: { fontSize: 13, fontWeight: '500' },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  box: {
    width: 18, height: 18, borderRadius: 5, borderWidth: 1.5, borderColor: C.gray300,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.card,
  },
  radio: {
    width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, borderColor: C.gray300,
    alignItems: 'center', justifyContent: 'center', backgroundColor: C.card,
  },
  boxOn: { backgroundColor: C.primary, borderColor: C.primary },
  toggleText: { fontSize: 13, color: C.text },
  segments: {
    flexDirection: 'row', backgroundColor: C.gray100, borderRadius: 10, padding: 3, marginBottom: 12, gap: 2,
  },
  segment: { flex: 1, alignItems: 'center', paddingVertical: 7, borderRadius: 8 },
  segmentOn: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border },
  segmentText: { fontSize: 13, fontWeight: '500', color: C.textSub },
  segmentTextOn: { color: C.primary },
  option: {
    flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: C.border,
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, marginTop: 8,
  },
  optionOn: { borderColor: C.primary, backgroundColor: C.blueLt },
  optionDisabled: { opacity: 0.6 },
  optionText: { flex: 1, fontSize: 14, color: C.text },
  bars: { gap: 10, marginTop: 10 },
  barLabelRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8, marginBottom: 4 },
  barLabel: { flex: 1, fontSize: 13, color: C.text },
  barLabelMine: { color: C.primary, fontWeight: '500' },
  barValue: { fontSize: 12, color: C.textSub },
  barTrack: { height: 8, borderRadius: 4, backgroundColor: C.gray100, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 4, backgroundColor: C.primary },
})
