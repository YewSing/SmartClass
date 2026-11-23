// Building blocks of the live interaction and after-class summary screens (S37, S38b)
import {
  View, Text, TouchableOpacity, TouchableWithoutFeedback, StyleSheet, ActivityIndicator, Modal, ScrollView,
  Dimensions,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import Badge from './Badge'
import { pollBars, timelineBars, reactionRows, askerLabel, questionBadges } from '../services/interaction'
import { hhmm } from '../services/attendance'
import { useWideLayout } from '../hooks/useWideLayout'
import { C } from '../theme'

// A pop-up for history lists and compose forms: a bottom sheet on phones, a centred dialog when wide.
// The page behind never grows (S38b).
export function IxSheet({ visible, title, onClose, children, testID }) {
  const { bottom } = useSafeAreaInsets()
  const wide = useWideLayout()
  return (
    <Modal transparent animationType={wide ? 'fade' : 'slide'} visible={visible} onRequestClose={onClose}>
      <View style={[s.overlay, wide && s.overlayWide]}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={StyleSheet.absoluteFillObject} />
        </TouchableWithoutFeedback>
        <View style={[s.sheet, wide ? s.dialog : { paddingBottom: bottom + 12 }]} testID={testID}>
          {!wide ? <View style={s.handle} /> : null}
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
      </View>
    </Modal>
  )
}

// Reactions as small chips with counts (the live page's status card)
export function ReactionChips({ counts, testIDPrefix = 'ix-reaction' }) {
  return (
    <View style={s.chips}>
      {reactionRows(counts).map(r => (
        <View key={r.kind} style={s.chip} accessibilityLabel={`${r.label}: ${r.count}`}>
          <Ionicons name={r.icon} size={13} color={C.primary} />
          <Text style={s.chipLabel}>{r.label}</Text>
          <Text style={s.chipCount} testID={`${testIDPrefix}-${r.kind}`}>{r.count}</Text>
        </View>
      ))}
    </View>
  )
}

export function Card({ children, style, testID }) {
  return <View style={[s.card, style]} testID={testID}>{children}</View>
}

export function Heading({ children, right }) {
  return (
    <View style={s.heading}>
      <Text style={s.headingText}>{children}</Text>
      {right ?? null}
    </View>
  )
}

export function Muted({ children, testID }) {
  return <Text style={s.muted} testID={testID}>{children}</Text>
}

export function Loading({ text = 'Loading…' }) {
  return (
    <Card style={s.center}>
      <ActivityIndicator color={C.primary} />
      <Muted>{text}</Muted>
    </Card>
  )
}

export function LoadError({ message, onRetry, testID = 'ix-error' }) {
  return (
    <Card style={s.errorCard} testID={testID}>
      <Ionicons name="cloud-offline-outline" size={18} color={C.redDk} />
      <View style={s.flex1}>
        <Text style={s.errorTitle}>Couldn't load the class interaction</Text>
        {message ? <Text style={s.errorText}>{message}</Text> : null}
      </View>
      <TouchableOpacity onPress={onRetry} style={s.retry} testID={`${testID}-retry`} accessibilityRole="button">
        <Text style={s.retryText}>Retry</Text>
      </TouchableOpacity>
    </Card>
  )
}

// Small action button: `primary` (blue), `danger` (red) or outlined
export function Btn({ label, icon, onPress, kind = 'outline', disabled, testID, busy }) {
  const solid = kind === 'primary' || kind === 'danger'
  const color = solid ? '#fff' : kind === 'subtle' ? C.textSub : C.text
  return (
    <TouchableOpacity
      style={[s.btn, kind === 'primary' && s.btnPrimary, kind === 'danger' && s.btnDanger,
        !solid && s.btnOutline, (disabled || busy) && s.btnDisabled]}
      onPress={onPress} disabled={disabled || busy} testID={testID} accessibilityRole="button"
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
          key={it.key} onPress={() => onChange(it.key)} testID={`ix-tab-${it.key}`}
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

// Category pills (S38d summary): one row that scrolls sideways on narrow screens
export function Pills({ items, value, onChange, testIDPrefix = 'ix-pill' }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.pillsScroll}
      contentContainerStyle={s.pills} accessibilityRole="tablist">
      {items.map(it => {
        const on = value === it.key
        return (
          <TouchableOpacity
            key={it.key} onPress={() => onChange(it.key)} testID={`${testIDPrefix}-${it.key}`}
            style={[s.pill, on && s.pillOn]} accessibilityRole="tab" accessibilityState={{ selected: on }}
          >
            <Text style={[s.pillText, on && s.pillTextOn]}>{it.label}</Text>
            <Text style={[s.pillCount, on && s.pillCountOn]}>{it.count ?? 0}</Text>
          </TouchableOpacity>
        )
      })}
    </ScrollView>
  )
}

// One question as the lecturer sees it; `actions` are the moderation buttons (live screen only)
export function QuestionRow({ q, actions, testID = 'ix-question' }) {
  return (
    <Card testID={testID} style={q.hidden && s.dimmed}>
      <Text style={s.qText}>{q.text}</Text>
      <View style={s.metaRow}>
        <Text style={s.meta}>{askerLabel(q)} · {hhmm(q.created_at)}</Text>
        <View style={s.upvotes}>
          <Ionicons name="arrow-up" size={12} color={C.textSub} />
          <Text style={s.meta} testID={`${testID}-upvotes`}>{q.upvotes}</Text>
        </View>
        {questionBadges(q).map(b => <Badge key={b.label} variant={b.variant}>{b.label}</Badge>)}
      </View>
      {actions ? <View style={s.actions}>{actions}</View> : null}
    </Card>
  )
}

export function PollResults({ poll, testID = 'ix-poll-option' }) {
  return (
    <View style={s.bars}>
      {pollBars(poll).map(o => (
        <View key={o.id} testID={testID}>
          <View style={s.barLabelRow}>
            <Text style={s.barLabel} numberOfLines={2}>{o.text}</Text>
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

export function ReactionGrid({ counts, testIDPrefix = 'ix-reaction' }) {
  return (
    <View style={s.reactions}>
      {reactionRows(counts).map(r => (
        <View key={r.kind} style={s.reaction}>
          <Ionicons name={r.icon} size={16} color={C.primary} />
          <Text style={s.reactionLabel}>{r.label}</Text>
          <Text style={s.reactionCount} testID={`${testIDPrefix}-${r.kind}`}>{r.count}</Text>
        </View>
      ))}
    </View>
  )
}

// Presses per minute, oldest on the left
export function ConfusionTimeline({ timeline, testID = 'ix-confusion-bar' }) {
  const bars = timelineBars(timeline)
  if (!bars.length) return <Muted testID="ix-confusion-empty">No "I don't understand" presses yet.</Muted>
  return (
    <View>
      <View style={s.timeline}>
        {bars.map(b => (
          <View key={b.start} style={s.tlCol} testID={testID} accessibilityLabel={`${b.label}: ${b.count}`}>
            <Text style={s.tlCount}>{b.count}</Text>
            <View style={[s.tlBar, { height: Math.max(4, Math.round(b.height * 60)) }]} />
          </View>
        ))}
      </View>
      <View style={s.tlAxis}>
        <Text style={s.meta}>{bars[0].label}</Text>
        {bars.length > 1 ? <Text style={s.meta}>{bars[bars.length - 1].label}</Text> : null}
      </View>
    </View>
  )
}

export function TopicList({ topics, testID = 'ix-confusion-topic' }) {
  if (!topics?.length) return null
  return (
    <View style={s.topics}>
      {topics.map(t => (
        <View key={t.topic} style={s.topic} testID={testID}>
          <Text style={s.topicText}>{t.topic}</Text>
          <Text style={s.topicCount}>{t.count}</Text>
        </View>
      ))}
    </View>
  )
}

export function Stat({ label, value, testID }) {
  return (
    <View style={s.stat}>
      <Text style={s.statValue} testID={testID}>{value}</Text>
      <Text style={s.statLabel}>{label}</Text>
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
})

const s = StyleSheet.create({
  flex1: { flex: 1 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  overlayWide: { justifyContent: 'center', alignItems: 'center', padding: 24 },
  sheet: {
    backgroundColor: C.bg, borderTopLeftRadius: 18, borderTopRightRadius: 18, paddingHorizontal: 16,
    paddingTop: 10, maxHeight: Dimensions.get('window').height * 0.85,
  },
  dialog: { width: '100%', maxWidth: 560, borderRadius: 14, paddingTop: 16, paddingBottom: 12, maxHeight: '85%' },
  handle: { width: 40, height: 4, backgroundColor: C.gray300, borderRadius: 2, alignSelf: 'center', marginBottom: 10 },
  sheetHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  sheetTitle: { fontSize: 16, fontWeight: '600', color: C.text },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderColor: C.border,
    borderRadius: 16, paddingHorizontal: 9, paddingVertical: 4, backgroundColor: C.card,
  },
  chipLabel: { fontSize: 12, color: C.text },
  chipCount: { fontSize: 12, fontWeight: '600', color: C.text },
  card: {
    backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, marginBottom: 10,
  },
  center: { alignItems: 'center', gap: 8 },
  dimmed: { opacity: 0.6 },
  heading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 6, marginBottom: 4 },
  headingText: { fontSize: 11, fontWeight: '600', color: C.textHint, textTransform: 'uppercase', letterSpacing: 0.8 },
  muted: { fontSize: 13, color: C.textSub, paddingVertical: 4 },
  errorCard: { flexDirection: 'row', alignItems: 'center', gap: 10, borderColor: C.redLt, backgroundColor: C.redLt },
  errorTitle: { fontSize: 13, fontWeight: '600', color: C.redDk },
  errorText: { fontSize: 12, color: C.redDk, marginTop: 2 },
  retry: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: C.card, borderWidth: 1, borderColor: C.border },
  retryText: { fontSize: 13, fontWeight: '600', color: C.text },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8,
  },
  btnPrimary: { backgroundColor: C.primary },
  btnDanger: { backgroundColor: C.red },
  btnOutline: { borderWidth: 1, borderColor: C.border, backgroundColor: C.card },
  btnDisabled: { opacity: 0.45 },
  btnText: { fontSize: 13, fontWeight: '500' },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  box: {
    width: 18, height: 18, borderRadius: 5, borderWidth: 1.5, borderColor: C.gray300,
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
  pillsScroll: { flexGrow: 0, marginBottom: 12 },
  pills: { flexDirection: 'row', gap: 8, paddingVertical: 2 },
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: C.border,
    borderRadius: 18, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: C.card,
  },
  pillOn: { backgroundColor: C.blueLt, borderColor: C.primary },
  pillText: { fontSize: 13, fontWeight: '500', color: C.textSub },
  pillTextOn: { color: C.primary },
  pillCount: { fontSize: 12, fontWeight: '600', color: C.textSub },
  pillCountOn: { color: C.primary },
  qText: { fontSize: 14, color: C.text, lineHeight: 20 },
  metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  meta: { fontSize: 12, color: C.textSub },
  upvotes: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  bars: { gap: 10, marginTop: 8 },
  barLabelRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8, marginBottom: 4 },
  barLabel: { flex: 1, fontSize: 13, color: C.text },
  barValue: { fontSize: 12, color: C.textSub },
  barTrack: { height: 8, borderRadius: 4, backgroundColor: C.gray100, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 4, backgroundColor: C.primary },
  reactions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  reaction: {
    flexGrow: 1, flexBasis: '45%', flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8,
  },
  reactionLabel: { flex: 1, fontSize: 13, color: C.text },
  reactionCount: { fontSize: 15, fontWeight: '600', color: C.text },
  timeline: { flexDirection: 'row', alignItems: 'flex-end', gap: 4, height: 84, marginTop: 8 },
  tlCol: { flex: 1, maxWidth: 28, alignItems: 'center', justifyContent: 'flex-end', gap: 2 },
  tlCount: { fontSize: 10, color: C.textSub },
  tlBar: { width: '100%', borderRadius: 3, backgroundColor: C.orange },
  tlAxis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  topics: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  topic: {
    flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.orangeLt,
    borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4,
  },
  topicText: { fontSize: 12, color: C.orangeDk },
  topicCount: { fontSize: 12, fontWeight: '600', color: C.orangeDk },
  stat: {
    flexGrow: 1, flexBasis: '22%', minWidth: 70, borderWidth: 1, borderColor: C.border, borderRadius: 10,
    paddingVertical: 10, alignItems: 'center', backgroundColor: C.card,
  },
  statValue: { fontSize: 18, fontWeight: '600', color: C.text },
  statLabel: { fontSize: 11, color: C.textSub, marginTop: 2 },
})
