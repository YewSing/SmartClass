import { useMemo } from 'react'
import { View, Text, StyleSheet, Platform } from 'react-native'
import { parseMarkdown } from '../services/markdown'
import { C } from '../theme'

function Spans({ spans }) {
  return spans.map((s, i) => (
    <Text key={i} style={[s.bold && styles.bold, s.italic && styles.italic, s.code && styles.inlineCode]}>
      {s.text}
    </Text>
  ))
}

function ListItem({ marker, indent, spans }) {
  return (
    <View style={[styles.item, { marginLeft: indent * 14 }]}>
      <Text style={styles.marker}>{marker}</Text>
      <Text style={styles.itemText}><Spans spans={spans} /></Text>
    </View>
  )
}

export default function MarkdownText({ children }) {
  const blocks = useMemo(() => parseMarkdown(children), [children])
  return (
    <View style={styles.wrap}>
      {blocks.map((b, i) => {
        if (b.type === 'heading') return <Text key={i} style={styles.heading}><Spans spans={b.spans} /></Text>
        if (b.type === 'bullet') return <ListItem key={i} marker="•" indent={b.indent} spans={b.spans} />
        if (b.type === 'numbered') return <ListItem key={i} marker={`${b.n}.`} indent={b.indent} spans={b.spans} />
        if (b.type === 'code') {
          return <View key={i} style={styles.codeBox}><Text style={styles.code}>{b.text}</Text></View>
        }
        return <Text key={i} style={styles.text}><Spans spans={b.spans} /></Text>
      })}
    </View>
  )
}

const mono = Platform.select({ ios: 'Menlo', default: 'monospace' })

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  text: { color: C.text, fontSize: 15, lineHeight: 22 },
  heading: { color: C.text, fontSize: 16, lineHeight: 22, fontWeight: '700', marginTop: 2 },
  bold: { fontWeight: '700' },
  italic: { fontStyle: 'italic' },
  inlineCode: { fontFamily: mono, fontSize: 13, backgroundColor: C.bg },
  item: { flexDirection: 'row', gap: 6 },
  marker: { color: C.text, fontSize: 15, lineHeight: 22, minWidth: 14 },
  itemText: { flex: 1, color: C.text, fontSize: 15, lineHeight: 22 },
  codeBox: { backgroundColor: C.bg, borderRadius: 8, padding: 10 },
  code: { fontFamily: mono, fontSize: 13, lineHeight: 19, color: C.text },
})
