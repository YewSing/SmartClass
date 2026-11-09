import { useEffect, useRef, useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet, ActivityIndicator,
  KeyboardAvoidingView, Keyboard,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import MarkdownText from '../components/MarkdownText'
import Topbar from '../components/Topbar'
import { useStudent } from '../context/StudentContext'
import { createChatSession, getChatMessages, sendChatMessage } from '../services/api'
import { openAtLabel } from '../services/openSource'
import { C } from '../theme'

function CitationChips({ citations, onOpen }) {
  return (
    <View style={styles.chips}>
      {citations.map(c => (
        <TouchableOpacity key={c.n} style={styles.chip} onPress={() => onOpen(c)}>
          <Text style={styles.chipNum}>[{c.n}]</Text>
          <Text style={styles.chipText} numberOfLines={1}>{c.title} · {openAtLabel(c)}</Text>
          <Ionicons name="open-outline" size={13} color={C.primary} />
        </TouchableOpacity>
      ))}
    </View>
  )
}

function Message({ msg, onOpenCitation }) {
  if (msg.role === 'user') {
    return (
      <View style={[styles.bubble, styles.userBubble]}>
        {/* This bubble shrinks to its text. Android's default line breaking can measure it too
            narrow with some phone fonts, and the last word then wraps out of sight. */}
        <Text style={styles.userText} textBreakStrategy="simple">{msg.content}</Text>
      </View>
    )
  }
  return (
    <View style={[styles.bubble, styles.botBubble]}>
      {msg.source_type === 'general' ? (
        <View style={styles.generalTag}>
          <Ionicons name="globe-outline" size={12} color={C.orangeDk} />
          <Text style={styles.generalText}>General knowledge · not from your course materials</Text>
        </View>
      ) : null}
      <MarkdownText>{msg.content}</MarkdownText>
      {msg.citations?.length ? <CitationChips citations={msg.citations} onOpen={onOpenCitation} /> : null}
    </View>
  )
}

export default function AssistantChat({ route, navigation }) {
  const { courseId, courseCode } = route.params
  const { showToast } = useStudent()
  const [sessionId, setSessionId] = useState(route.params.sessionId ?? null)
  const [title, setTitle] = useState(route.params.title ?? null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(!!route.params.sessionId)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const listRef = useRef(null)

  useEffect(() => {
    if (!route.params.sessionId) return
    getChatMessages(route.params.sessionId)
      .then(setMessages)
      .catch(e => showToast(e.message, 'error'))
      .finally(() => setLoading(false))
  }, [route.params.sessionId, showToast])

  // Keep the latest message on screen when the keyboard takes up the bottom half
  useEffect(() => {
    const sub = Keyboard.addListener('keyboardDidShow', () => listRef.current?.scrollToEnd({ animated: true }))
    return () => sub.remove()
  }, [])

  const send = async () => {
    const question = draft.trim()
    if (!question || sending) return
    setSending(true)
    setDraft('')
    const pending = { id: `pending-${Date.now()}`, role: 'user', content: question }
    setMessages(list => [...list, pending])
    try {
      // A new chat is only created once the first question is sent
      let id = sessionId
      if (!id) {
        id = (await createChatSession(courseId)).id
        setSessionId(id)
      }
      const reply = await sendChatMessage(id, question)
      setMessages(list => [...list, reply])
      if (!title) setTitle(question.slice(0, 60))
    } catch (e) {
      // Nothing was saved: take the question back out and put it in the box again
      setMessages(list => list.filter(m => m.id !== pending.id))
      setDraft(question)
      showToast(e.message, 'error')
    } finally {
      setSending(false)
    }
  }

  const openCitation = (citation) => navigation.navigate('AssistantSource', { citation, courseCode })

  return (
    // Android needs this too: with edge-to-edge the window no longer resizes for the keyboard
    <KeyboardAvoidingView style={styles.screen} behavior="padding">
      <Topbar title={title || 'New chat'} sub={courseCode} onBack={() => navigation.goBack()} />
      <View style={styles.body}>
        {loading ? (
          <ActivityIndicator style={{ marginTop: 40 }} color={C.primary} />
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={m => String(m.id)}
            renderItem={({ item }) => <Message msg={item} onOpenCitation={openCitation} />}
            contentContainerStyle={[styles.list, sending && styles.listWhileSending]}
            keyboardShouldPersistTaps="handled"
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
            ListEmptyComponent={(
              <View style={styles.empty}>
                <Ionicons name="sparkles-outline" size={32} color={C.primary} />
                <Text style={styles.emptyTitle}>Ask about {courseCode}</Text>
                <Text style={styles.emptyText}>
                  Answers come from your lecturer's materials on SPeCTRUM. Tap a source under an answer to open it.
                </Text>
              </View>
            )}
          />
        )}
        {sending ? (
          <View style={styles.thinking} testID="assistant-thinking" pointerEvents="none">
            <ActivityIndicator size="small" color={C.primary} />
            <Text style={styles.thinkingText}>Drafting answer…</Text>
          </View>
        ) : null}
      </View>
      <View style={styles.inputBar}>
        <TextInput
          testID="assistant-input"
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder="Ask a question…"
          placeholderTextColor={C.textHint}
          multiline
          maxLength={2000}
        />
        <TouchableOpacity
          style={[styles.sendBtn, (!draft.trim() || sending) && styles.sendDisabled]}
          onPress={send}
          disabled={!draft.trim() || sending}
          accessibilityLabel="Send"
          testID="assistant-send"
        >
          <Ionicons name="send" size={18} color="#fff" />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  body: { flex: 1 },
  list: { padding: 12, paddingBottom: 20, flexGrow: 1 },
  listWhileSending: { paddingBottom: 64 },
  bubble: { maxWidth: '88%', borderRadius: 14, padding: 12, marginBottom: 10 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: C.primary, borderBottomRightRadius: 4 },
  userText: { color: '#fff', fontSize: 15, lineHeight: 21 },
  botBubble: {
    alignSelf: 'flex-start', backgroundColor: C.card, borderBottomLeftRadius: 4,
    borderWidth: 1, borderColor: C.border,
  },
  generalTag: {
    flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start',
    backgroundColor: C.orangeLt, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 3, marginBottom: 8,
  },
  generalText: { fontSize: 11, fontWeight: '600', color: C.orangeDk },
  chips: { marginTop: 10, gap: 6 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.blueLt, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6,
  },
  chipNum: { fontSize: 12, fontWeight: '700', color: C.primary },
  chipText: { flex: 1, fontSize: 12, color: C.blueDk },
  thinking: {
    position: 'absolute', bottom: 12, alignSelf: 'center',
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: C.card, borderRadius: 20, borderWidth: 1, borderColor: C.border,
    paddingHorizontal: 16, paddingVertical: 9, elevation: 4,
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
  },
  thinkingText: { fontSize: 14, fontWeight: '600', color: C.text },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, gap: 8 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: C.text },
  emptyText: { fontSize: 13, color: C.textSub, textAlign: 'center', lineHeight: 19 },
  inputBar: {
    flexDirection: 'row', alignItems: 'flex-end', gap: 8, padding: 10,
    backgroundColor: C.card, borderTopWidth: 1, borderTopColor: C.border,
  },
  input: {
    flex: 1, maxHeight: 120, fontSize: 15, color: C.text, backgroundColor: C.bg,
    borderRadius: 18, borderWidth: 1, borderColor: C.border, paddingHorizontal: 14, paddingVertical: 9,
  },
  sendBtn: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  sendDisabled: { opacity: 0.4 },
})
