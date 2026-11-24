// Building blocks of the live interaction and after-class summary screens (S37, S38b)
import { useEffect, useState } from 'react'
import {
  View, Text, TouchableOpacity, TouchableWithoutFeedback, StyleSheet, ActivityIndicator, Modal, ScrollView,
  Keyboard, KeyboardAvoidingView,
} from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import Badge from './Badge'
import { pollBars, timelineBars, reactionRows, askerLabel, questionBadges } from '../services/interaction'
import { hhmm } from '../services/attendance'
import { useWideLayout } from '../hooks/useWideLayout'
import { C, TONES, reactionTone } from '../interactionTheme'

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

// A pop-up for history lists and compose forms: a bottom sheet on phones, a centred dialog when wide.
// The page behind never grows (S38b). With the keyboard open the sheet shrinks into the space above it
// and scrolls inside (S38f).
export function IxSheet({ visible, title, onClose, children, testID }) {
  const { bottom } = useSafeAreaInsets()
  const wide = useWideLayout()
  // The keyboard already covers the system bar, so its inset is only kept while the keyboard is closed
  const [typing, setTyping] = useState(false)
  useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => setTyping(true))
    const hide = Keyboard.addListener('keyboardDidHide', () => setTyping(false))
    return () => { show.remove(); hide.remove() }
  }, [])
  return (
    <Modal transparent statusBarTranslucent navigationBarTranslucent animationType={wide ? 'fade' : 'slide'}
      visible={visible} onRequestClose={onClose}>
      <KeyboardAvoidingView behavior="padding" style={[s.overlay, wide && s.overlayWide]}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={StyleSheet.absoluteFillObject} />
        </TouchableWithoutFeedback>
        <View style={[s.sheet, wide ? s.dialog : { paddingBottom: typing ? 0 : bottom + 12 }]} testID={testID}>
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
      </KeyboardAvoidingView>
    </Modal>
  )
}

// Reactions as emoji with counts (the live page's status card)
export function ReactionChips({ counts, testIDPrefix = 'ix-reaction' }) {
  return (
    <View style={s.chips}>
      {reactionRows(counts).map(r => {
        const t = TONES[reactionTone(r.kind)]
        return (
          <View key={r.kind} style={[s.chip, { backgroundColor: t.lt, borderColor: r.count ? t.solid : t.bd }]}
            accessibilityLabel={`${r.label}: ${r.count}`}>
            <Text style={s.emoji}>{r.emoji}</Text>
            <Text style={[s.chipCount, { color: t.dk }]} testID={`${testIDPrefix}-${r.kind}`}>{r.count}</Text>
            <Text style={[s.chipLabel, { color: t.dk }]} numberOfLines={1}>{r.label}</Text>
          </View>
        )
      })}
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

// Action button: `primary` (solid), `soft` (tinted), `link` (text only) or outlined; `tone` colours the
// first three, `wide` fills the row
export function Btn({
  label, icon, onPress, kind = 'outline', tone = 'blue', wide, disabled, testID, busy,
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
    <Card testID={testID} style={[s.qCard, q.answered && s.qAnswered, q.hidden && s.dimmed]}>
      <View style={s.qHead}>
        <Avatar name={q.anonymous ? null : q.author_name} />
        <View style={s.qWho}>
          <Text style={s.qAuthor} numberOfLines={1}>{askerLabel(q)}</Text>
          <Text style={s.meta}>{hhmm(q.created_at)}</Text>
        </View>
        {questionBadges(q).map(b => <Badge key={b.label} variant={b.variant}>{b.label}</Badge>)}
        <View style={s.upvotes}>
          <Ionicons name="arrow-up" size={13} color={C.blueDk} />
          <Text style={s.upvoteText} testID={`${testID}-upvotes`}>{q.upvotes}</Text>
        </View>
      </View>
      <Text style={s.qText}>{q.text}</Text>
      {actions ? <View style={s.actions}>{actions}</View> : null}
    </Card>
  )
}

// Each option with its votes and share, and a line filled to that share; the leading option is darker
export function PollResults({ poll, testID = 'ix-poll-option' }) {
  const bars = pollBars(poll)
  const top = Math.max(0, ...bars.map(o => o.votes))
  return (
    <View style={s.bars}>
      {bars.map(o => {
        const lead = top > 0 && o.votes === top
        return (
          <View key={o.id} testID={testID} style={[s.bar, lead && s.barLead]}>
            <View style={s.barRow}>
              <Text style={[s.barLabel, lead && s.barLabelLead]}>{o.text}</Text>
              <Text style={[s.barValue, lead && s.barLabelLead]}>{o.votes} · {o.pct}%</Text>
            </View>
            <View style={s.barTrack} testID="ix-poll-line">
              <View style={[s.barFill, lead && s.barFillLead, { width: `${Math.min(100, o.pct)}%` }]} />
            </View>
          </View>
        )
      })}
    </View>
  )
}

export function ReactionGrid({ counts, testIDPrefix = 'ix-reaction' }) {
  return (
    <View style={s.reactions}>
      {reactionRows(counts).map(r => {
        const t = TONES[reactionTone(r.kind)]
        return (
          <View key={r.kind} style={[s.reaction, { backgroundColor: t.lt, borderColor: t.bd }]}>
            <Text style={s.emojiSm}>{r.emoji}</Text>
            <Text style={[s.reactionLabel, { color: t.dk }]}>{r.label}</Text>
            <Text style={[s.reactionCount, { color: t.dk }]} testID={`${testIDPrefix}-${r.kind}`}>{r.count}</Text>
          </View>
        )
      })}
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
    paddingTop: 10, maxHeight: '88%', flexShrink: 1,
  },
  dialog: { width: '100%', maxWidth: 560, borderRadius: 14, paddingTop: 16, paddingBottom: 12, maxHeight: '85%' },
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
  chips: { flexDirection: 'row', gap: 8 },
  chip: { flex: 1, alignItems: 'center', gap: 1, borderWidth: 1, borderRadius: 12, paddingHorizontal: 2, paddingVertical: 8 },
  chipLabel: { fontSize: 11, fontWeight: '600' },
  chipCount: { fontSize: 16, fontWeight: '800' },
  emoji: { fontSize: 22, lineHeight: 29 },
  emojiSm: { fontSize: 16, lineHeight: 22 },
  card: {
    backgroundColor: C.card, borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 14, marginBottom: 12,
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
  btnWide: { alignSelf: 'stretch', paddingVertical: 11 },
  btnOutline: { borderWidth: 1, borderColor: C.border, backgroundColor: C.card },
  btnDisabled: { opacity: 0.45 },
  btnText: { fontSize: 13, fontWeight: '600' },
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
  qCard: { backgroundColor: C.tealLt, borderColor: C.tealBd, padding: 12 },
  qAnswered: { backgroundColor: C.gray50, borderColor: C.border },
  qHead: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  qWho: { flexGrow: 1, flexShrink: 1, minWidth: 90 },
  qAuthor: { fontSize: 13, fontWeight: '600', color: C.text },
  qText: { fontSize: 15, color: C.text, lineHeight: 21 },
  meta: { fontSize: 12, color: C.textSub },
  upvotes: {
    flexDirection: 'row', alignItems: 'center', gap: 2, backgroundColor: C.blueLt, borderRadius: 20,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  upvoteText: { fontSize: 12, fontWeight: '700', color: C.blueDk },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  bars: { gap: 8, marginTop: 10 },
  bar: {
    gap: 8, borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: C.card,
  },
  barLead: { borderColor: C.blueBd, backgroundColor: C.blueLt },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  barTrack: { height: 8, borderRadius: 4, backgroundColor: C.border, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 4, backgroundColor: C.blueBd },
  barFillLead: { backgroundColor: C.primary },
  barLabel: { flex: 1, fontSize: 14, color: C.text },
  barLabelLead: { fontWeight: '700', color: C.blueDk },
  barValue: { fontSize: 13, fontWeight: '600', color: C.textSub },
  reactions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  reaction: {
    flexGrow: 1, flexBasis: '45%', flexDirection: 'row', alignItems: 'center', gap: 6,
    borderWidth: 1, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8,
  },
  reactionLabel: { flex: 1, fontSize: 13 },
  reactionCount: { fontSize: 15, fontWeight: '700' },
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
