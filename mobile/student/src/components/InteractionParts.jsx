// Building blocks of the student live class and "My questions" screens (S38). Same look as the
// lecturer app's interaction parts: white section cards, one colour per kind of interaction.
import {
  View, Text, TouchableOpacity, TouchableWithoutFeedback, StyleSheet, ActivityIndicator, Modal, ScrollView,
  KeyboardAvoidingView,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { pollBars } from '../services/interaction'
import { C, TONES } from '../interactionTheme'

// A section card's title row: a solid icon tile, the title in the section's colour, `right` at the end
export function SectionHead({ icon, title, tone = 'blue', right }) {
  const t = TONES[tone] ?? TONES.blue
  return (
    <View style={s.sectionHead}>
      <View style={[s.sectionIcon, { backgroundColor: t.solid }]}>
        <Ionicons name={icon} size={16} color="#fff" />
      </View>
      <Text style={[s.sectionTitle, { color: t.dk }]}>{title}</Text>
      {right ?? null}
    </View>
  )
}

// Who asked: the first letter of the name, or an eye-off mark for an anonymous question
export function Avatar({ name }) {
  return (
    <View style={[s.avatar, !name && s.avatarAnon]}>
      {name
        ? <Text style={s.avatarText}>{name.trim().charAt(0).toUpperCase()}</Text>
        : <Ionicons name="eye-off-outline" size={14} color={C.gray600} />}
    </View>
  )
}

// A bottom sheet with a title and a close button (S38c: the full question list lives here, so the
// page doesn't grow)
export function IxSheet({ visible, title, onClose, children, testID }) {
  const { bottom } = useSafeAreaInsets()
  return (
    <Modal transparent statusBarTranslucent navigationBarTranslucent animationType="slide"
      visible={visible} onRequestClose={onClose}>
      <KeyboardAvoidingView behavior="padding" style={s.overlay}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={StyleSheet.absoluteFillObject} />
        </TouchableWithoutFeedback>
        <View style={[s.sheet, { paddingBottom: bottom + 12 }]} testID={testID}>
          <View style={s.handle} />
          <View style={s.sheetHead}>
            <Text style={s.sheetTitle}>{title}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close"
              testID={testID ? `${testID}-close` : undefined}>
              <Ionicons name="close" size={20} color={C.textSub} />
            </TouchableOpacity>
          </View>
          <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
            {children}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  )
}

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

// Action button: `primary` (solid), `soft` (tinted), `link` (text only) or outlined; `tone` colours the
// first three, `wide` fills the row
export function Btn({
  label, icon, onPress, kind = 'outline', tone = 'blue', wide, disabled, testID, busy, accessibilityLabel,
}) {
  const t = TONES[tone] ?? TONES.blue
  const color = kind === 'primary' || kind === 'danger' ? '#fff'
    : kind === 'soft' || kind === 'link' ? t.dk : kind === 'subtle' ? C.textSub : C.text
  const look = kind === 'primary' ? { backgroundColor: t.solid }
    : kind === 'danger' ? { backgroundColor: C.red }
      : kind === 'soft' ? { backgroundColor: t.lt, borderWidth: 1, borderColor: t.bd }
        : kind === 'link' ? null : s.btnOutline
  return (
    <TouchableOpacity
      style={[s.btn, look, wide && s.btnWide, (disabled || busy) && s.btnDisabled]}
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

// The options once the student voted (or the poll closed): the result sits on each option, with a
// line filled to its share. Without counts (the lecturer hides results) only the student's own choice is marked.
export function PollResults({ poll }) {
  const mine = poll?.my_option_ids ?? []
  const bars = pollBars(poll)
  const top = Math.max(0, ...bars.map(o => o.votes))
  const rows = bars.length ? bars
    : (poll?.options ?? []).map(o => ({ id: o.id, text: o.text, votes: null, mine: mine.includes(o.id) }))
  return (
    <View testID="live-poll-results">
      {rows.map((o, i) => {
        const counted = o.votes != null
        const lead = counted && top > 0 && o.votes === top
        return (
          <View
            key={o.id} style={[s.result, o.mine && s.resultMine]} accessible testID={`live-poll-result-${i}`}
            accessibilityLabel={`${o.text}${o.mine ? ' (your vote)' : ''}${counted ? `, ${o.pct}%` : ''}`}
          >
            <View style={s.resultRow}>
              <Text style={[s.optionText, (o.mine || lead) && s.resultStrong]}>{o.text}</Text>
              {o.mine ? (
                <View style={s.mineTag}>
                  <Ionicons name="checkmark" size={11} color="#fff" />
                  <Text style={s.mineTagText}>Your vote</Text>
                </View>
              ) : null}
              {counted ? <Text style={[s.resultPct, o.mine && s.resultPctMine]}>{o.pct}%</Text> : null}
            </View>
            {counted ? (
              <>
                <View style={s.track} testID="live-poll-line">
                  <View style={[s.fill, (o.mine || lead) && s.fillOn, { width: `${Math.min(100, o.pct)}%` }]} />
                </View>
                <Text style={s.resultVotes}>{o.votes} {o.votes === 1 ? 'vote' : 'votes'}</Text>
              </>
            ) : null}
          </View>
        )
      })}
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
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: C.bg, borderTopLeftRadius: 18, borderTopRightRadius: 18, paddingHorizontal: 16,
    paddingTop: 10, maxHeight: '88%', flexShrink: 1,
  },
  handle: { width: 40, height: 4, backgroundColor: C.gray300, borderRadius: 2, alignSelf: 'center', marginBottom: 10 },
  sheetHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  sheetTitle: { fontSize: 16, fontWeight: '600', color: C.text },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  sectionIcon: { width: 30, height: 30, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  sectionTitle: { flex: 1, fontSize: 15, fontWeight: '700' },
  avatar: {
    width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: C.teal,
  },
  avatarAnon: { backgroundColor: C.gray300 },
  avatarText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  card: {
    backgroundColor: C.card, borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 14, marginBottom: 12,
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
  btnWide: { alignSelf: 'stretch', paddingVertical: 11 },
  btnOutline: { borderWidth: 1, borderColor: C.border, backgroundColor: C.card },
  btnDisabled: { opacity: 0.45 },
  btnText: { fontSize: 13, fontWeight: '600' },
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
    borderRadius: 12, paddingHorizontal: 12, paddingVertical: 13, marginTop: 8, backgroundColor: C.card,
    overflow: 'hidden',
  },
  optionOn: { borderColor: C.primary, backgroundColor: C.blueLt },
  optionDisabled: { opacity: 0.6 },
  optionText: { flex: 1, fontSize: 15, color: C.text },
  result: {
    gap: 6, borderWidth: 1, borderColor: C.border, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 12,
    marginTop: 8, backgroundColor: C.card,
  },
  resultMine: { borderColor: C.primary, backgroundColor: C.blueLt },
  resultRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  resultStrong: { fontWeight: '700' },
  track: { height: 8, borderRadius: 4, backgroundColor: C.border, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: C.blueBd },
  fillOn: { backgroundColor: C.primary },
  mineTag: {
    flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: C.primary, borderRadius: 20,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  mineTagText: { fontSize: 11, fontWeight: '700', color: '#fff' },
  resultPct: { fontSize: 15, fontWeight: '800', color: C.text },
  resultPctMine: { color: C.blueDk },
  resultVotes: { fontSize: 11, color: C.textSub },
})
