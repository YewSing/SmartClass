// AI Assistant (Module 8), one screen (redesign 2026-11-13): no header; history at the top left,
// study tools at the top right, and a course dropdown under the logo until the chat starts.
// A study tool works once: pick it, type a topic, and its result arrives as a chat message
// that stays in the history (flashcards and practice open full screen from that message).
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, FlatList, ScrollView, StyleSheet, ActivityIndicator,
  KeyboardAvoidingView, Keyboard, Modal, Image, Linking, useWindowDimensions,
} from 'react-native'
import { useFocusEffect } from '@react-navigation/native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import MarkdownText from '../components/MarkdownText'
import {
  Sheet, ModalTitle, BtnOutline, BtnDanger, BtnPrimary, BtnRow, SheetOption, modalStyles,
} from '../components/Modals'
import { useStudent } from '../context/StudentContext'
import {
  getAssistantCourses, getChatSessions, getChatMessages, createChatSession, sendChatMessage,
  runChatTool, getRelatedVideos, renameChatSession, deleteChatSession,
} from '../services/api'
import {
  TOOLS, toolFor, inputPlaceholder, scoreLabel, canFindVideos, videoTopic, youtubeSearchUrl,
  courseLabel, timeAgo, isNearBottom,
} from '../services/assistantView'
import { bubbleTextWidth } from '../services/bubbleWidth'
import { openAtLabel, openCitation as openCitationFile } from '../services/openSource'
import { C } from '../theme'

// ── messages ────────────────────────────────────────────────────────────────

function CitationChips({ citations, onOpen }) {
  if (!citations?.length) return null
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

function UserMessage({ msg }) {
  const { width: windowWidth } = useWindowDimensions()
  const [measured, setMeasured] = useState(null)
  const tool = toolFor(msg.kind)
  return (
    <View style={[styles.bubble, styles.userBubble]}>
      {tool ? (
        <View style={styles.userToolRow}>
          <Ionicons name={tool.icon} size={13} color="#fff" />
          <Text style={styles.userToolText}>{tool.label}</Text>
        </View>
      ) : null}
      <Text
        style={[styles.userText, measured !== null && { width: bubbleTextWidth(measured, windowWidth) }]}
        onLayout={e => { if (measured === null) setMeasured(e.nativeEvent.layout.width) }}
      >
        {tool ? msg.content.replace(/^[^:]+:\s*/, '') : msg.content}
      </Text>
    </View>
  )
}

function GeneralTag() {
  return (
    <View style={styles.generalTag}>
      <Ionicons name="globe-outline" size={12} color={C.orangeDk} />
      <Text style={styles.generalText}>General knowledge · not from your course materials</Text>
    </View>
  )
}

function RelatedVideos({ state, onFind }) {
  if (!state) {
    return (
      <TouchableOpacity style={styles.findVideos} onPress={onFind} testID="find-videos">
        <Ionicons name="logo-youtube" size={15} color={C.red} />
        <Text style={styles.findVideosText}>Find related videos</Text>
      </TouchableOpacity>
    )
  }
  if (state.loading) {
    return (
      <View style={styles.findVideos}>
        <ActivityIndicator size="small" color={C.red} />
        <Text style={styles.findVideosText}>Finding videos…</Text>
      </View>
    )
  }
  const { videos = [], keywords = [] } = state.data ?? {}
  return (
    <View style={styles.videos} testID="related-videos">
      {videos.map(v => (
        <TouchableOpacity key={v.video_id} style={styles.video} onPress={() => Linking.openURL(v.url)}>
          {v.thumbnail_url
            ? <Image source={{ uri: v.thumbnail_url }} style={styles.thumb} />
            : <View style={[styles.thumb, styles.thumbEmpty]}><Ionicons name="play" size={16} color={C.red} /></View>}
          <View style={styles.flex}>
            <Text style={styles.videoTitle} numberOfLines={2}>{v.title}</Text>
            {v.channel ? <Text style={styles.videoChannel} numberOfLines={1}>{v.channel}</Text> : null}
          </View>
        </TouchableOpacity>
      ))}
      {keywords.length ? (
        <>
          <Text style={styles.keywordsLabel}>{videos.length ? 'Search YouTube for more:' : 'Search YouTube for:'}</Text>
          <View style={styles.keywords}>
            {keywords.map(k => (
              <TouchableOpacity key={k} style={styles.keyword} onPress={() => Linking.openURL(youtubeSearchUrl(k))}>
                <Text style={styles.keywordText}>{k}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </>
      ) : null}
    </View>
  )
}

function ToolCard({ msg, onOpen }) {
  const cards = msg.payload?.cards ?? []
  const questions = msg.payload?.questions ?? []
  const isCards = msg.kind === 'flashcards'
  const count = isCards ? cards.length : questions.length
  const score = scoreLabel(msg.payload)
  if (!count) return <Text style={styles.toolEmpty}>{msg.content}</Text>
  return (
    <View>
      <View style={styles.toolHead}>
        <Ionicons name={isCards ? 'albums-outline' : 'help-circle-outline'} size={18} color={C.primary} />
        <Text style={styles.toolTitle}>
          {count} {isCards ? (count === 1 ? 'flashcard' : 'flashcards') : (count === 1 ? 'practice question' : 'practice questions')}
        </Text>
      </View>
      <Text style={styles.toolTopic}>{msg.payload?.topic}{score ? ` · ${score}` : ''}</Text>
      <TouchableOpacity style={styles.toolBtn} onPress={onOpen} testID={isCards ? 'open-flashcards' : 'open-practice'}>
        <Text style={styles.toolBtnText}>{isCards ? 'Study cards' : score ? 'Try again' : 'Start practice'}</Text>
      </TouchableOpacity>
    </View>
  )
}

function AssistantMessage({ msg, onOpenCitation, onOpenTool, videos, onFindVideos }) {
  const tool = toolFor(msg.kind)
  const isDeck = msg.kind === 'flashcards' || msg.kind === 'practice_questions'
  return (
    <View style={[styles.bubble, styles.botBubble]}>
      {msg.source_type === 'general' ? <GeneralTag /> : null}
      {tool && !isDeck ? (
        <View style={styles.kindTag}>
          <Ionicons name={tool.icon} size={12} color={C.primary} />
          <Text style={styles.kindTagText}>{tool.label}</Text>
        </View>
      ) : null}
      {isDeck ? <ToolCard msg={msg} onOpen={() => onOpenTool(msg)} /> : <MarkdownText>{msg.content}</MarkdownText>}
      <CitationChips citations={msg.citations} onOpen={onOpenCitation} />
      {canFindVideos(msg) && videoTopic(msg) ? <RelatedVideos state={videos} onFind={() => onFindVideos(msg)} /> : null}
    </View>
  )
}

// ── pickers and panels ──────────────────────────────────────────────────────

function CoursePicker({ visible, courses, value, onPick, onClose }) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity style={styles.backdropCenter} activeOpacity={1} onPress={onClose}>
        <View style={styles.sheet}>
          <Text style={styles.sheetTitle}>Course</Text>
          <ScrollView style={{ maxHeight: 360 }}>
            {courses.map(c => {
              const active = c.course_id === value
              return (
                <TouchableOpacity
                  key={c.course_id}
                  style={[styles.sheetRow, active && styles.sheetRowActive]}
                  onPress={() => onPick(c.course_id)}
                  testID={`course-option-${c.code}`}
                >
                  <View style={styles.flex}>
                    <Text style={[styles.sheetRowText, active && { color: C.primary }]}>{courseLabel(c, { long: true })}</Text>
                    <Text style={styles.sheetRowMeta}>
                      {c.indexed_materials > 0 ? `${c.indexed_materials} materials from SPeCTRUM` : 'No materials yet'}
                    </Text>
                  </View>
                  {active ? <Ionicons name="checkmark" size={18} color={C.primary} /> : null}
                </TouchableOpacity>
              )
            })}
          </ScrollView>
        </View>
      </TouchableOpacity>
    </Modal>
  )
}

function ToolsMenu({ visible, top, onPick, onClose }) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity style={styles.flex} activeOpacity={1} onPress={onClose}>
        <View style={[styles.menu, { top }]}>
          {TOOLS.map(t => (
            <TouchableOpacity key={t.kind} style={styles.menuRow} onPress={() => onPick(t.kind)} testID={`tool-${t.kind}`}>
              <Ionicons name={t.icon} size={18} color={C.text} />
              <Text style={styles.menuText}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </TouchableOpacity>
    </Modal>
  )
}

function HistoryPanel({ visible, sessions, courses, currentId, loading, onOpen, onNew, onOptions, onClose }) {
  const insets = useSafeAreaInsets()
  const codeOf = (id) => courses.find(c => c.course_id === id)?.code ?? ''
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.panelBackdrop}>
        <View style={[styles.panel, { paddingTop: insets.top + 12 }]}>
          <View style={styles.panelHead}>
            <Text style={styles.panelTitle}>Chats</Text>
            <TouchableOpacity onPress={onClose} accessibilityLabel="Close chats" hitSlop={HIT}>
              <Ionicons name="close" size={22} color={C.text} />
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={styles.newChatBtn} onPress={onNew} testID="history-new-chat">
            <Ionicons name="add" size={18} color="#fff" />
            <Text style={styles.newChatText}>New chat</Text>
          </TouchableOpacity>
          {loading && !sessions.length ? <ActivityIndicator style={{ marginTop: 20 }} color={C.primary} /> : null}
          <ScrollView>
            {!loading && !sessions.length ? <Text style={styles.panelEmpty}>No chats yet.</Text> : null}
            {sessions.map(s => (
              <TouchableOpacity
                key={s.id}
                style={[styles.panelRow, s.id === currentId && styles.panelRowActive]}
                onPress={() => onOpen(s)}
                onLongPress={() => onOptions(s)}
                testID="history-row"
              >
                <Text style={styles.panelRowTitle} numberOfLines={1}>{s.title || 'Untitled chat'}</Text>
                <Text style={styles.panelRowMeta}>{codeOf(s.course_id)} · {timeAgo(s.updated_at)}</Text>
              </TouchableOpacity>
            ))}
            {sessions.length ? <Text style={styles.panelHint}>Long-press a chat to rename or delete it.</Text> : null}
          </ScrollView>
        </View>
        <TouchableOpacity style={styles.flex} activeOpacity={1} onPress={onClose} />
      </View>
    </Modal>
  )
}

const HIT = { top: 10, bottom: 10, left: 10, right: 10 }

// ── screen ──────────────────────────────────────────────────────────────────

export default function Assistant({ navigation }) {
  const { showToast } = useStudent()
  const insets = useSafeAreaInsets()
  const [courses, setCourses] = useState(null)
  const [courseId, setCourseId] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [loadingChat, setLoadingChat] = useState(false)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [tool, setTool] = useState(null)               // a study tool waiting for its topic (one-shot)
  const [videos, setVideos] = useState({})             // message id -> { loading } | { data }
  const [sessions, setSessions] = useState([])
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [chatSheet, setChatSheet] = useState(null)   // { mode: 'options' | 'rename' | 'delete', session }
  const [newTitle, setNewTitle] = useState('')
  const [atBottom, setAtBottom] = useState(true)     // false shows the jump-to-latest button
  const listRef = useRef(null)
  const nearBottomRef = useRef(true)
  const inputRef = useRef(null)

  const course = courses?.find(c => c.course_id === courseId) ?? null

  useEffect(() => {
    getAssistantCourses()
      .then(list => {
        setCourses(list)
        // Default to the first course that has materials to answer from
        setCourseId(prev => prev ?? (list.find(c => c.indexed_materials > 0) ?? list[0])?.course_id ?? null)
      })
      .catch(e => { setCourses([]); showToast(e.message, 'error') })
  }, [showToast])

  // Coming back from flashcards/practice: reload the chat, so a new practice score shows
  useFocusEffect(useCallback(() => {
    if (!sessionId) return
    getChatMessages(sessionId).then(setMessages).catch(() => {})
  }, [sessionId]))

  useEffect(() => {
    const sub = Keyboard.addListener('keyboardDidShow', () => listRef.current?.scrollToEnd({ animated: true }))
    return () => sub.remove()
  }, [])

  const scrollToLatest = () => {
    nearBottomRef.current = true
    setAtBottom(true)
    listRef.current?.scrollToEnd({ animated: true })
  }

  const loadSessions = async () => {
    setLoadingSessions(true)
    try { setSessions(await getChatSessions()) } catch (e) { showToast(e.message, 'error') } finally { setLoadingSessions(false) }
  }

  const newChat = () => {
    setSessionId(null)
    setMessages([])
    setVideos({})
    setTool(null)
    setDraft('')
    setHistoryOpen(false)
    nearBottomRef.current = true
    setAtBottom(true)
  }

  const openSession = async (s) => {
    setHistoryOpen(false)
    setCourseId(s.course_id)
    setSessionId(s.id)
    setMessages([])
    setVideos({})
    setTool(null)
    setLoadingChat(true)
    nearBottomRef.current = true
    setAtBottom(true)
    try { setMessages(await getChatMessages(s.id)) } catch (e) { showToast(e.message, 'error') } finally { setLoadingChat(false) }
  }

  const pickCourse = (id) => {
    setPickerOpen(false)
    if (id === courseId) return
    setCourseId(id)
    if (messages.length) newChat()   // a chat belongs to one course
  }

  const pickTool = (kind) => {
    setToolsOpen(false)
    setTool(kind)
    setTimeout(() => inputRef.current?.focus(), 150)
  }

  const send = async () => {
    const text = draft.trim()
    if (!text || sending || !courseId) return
    const usedTool = tool
    setSending(true)
    setDraft('')
    setTool(null)
    const pending = {
      id: `pending-${Date.now()}`, role: 'user', kind: usedTool ?? 'chat',
      content: usedTool ? `${toolFor(usedTool).label}: ${text}` : text,
    }
    setMessages(list => [...list, pending])
    nearBottomRef.current = true      // show the new question and its answer
    setAtBottom(true)
    try {
      let id = sessionId
      if (!id) {                       // a chat is only created once something is sent
        id = (await createChatSession(courseId)).id
        setSessionId(id)
      }
      const reply = usedTool ? await runChatTool(id, usedTool, text) : await sendChatMessage(id, text)
      setMessages(list => [...list, reply])
    } catch (e) {
      // Nothing was saved: take it back out and put it in the box again
      setMessages(list => list.filter(m => m.id !== pending.id))
      setDraft(text)
      setTool(usedTool)
      showToast(e.message, 'error')
    } finally {
      setSending(false)
    }
  }

  const findVideos = async (msg) => {
    setVideos(v => ({ ...v, [msg.id]: { loading: true } }))
    try {
      const data = await getRelatedVideos(courseId, videoTopic(msg))
      setVideos(v => ({ ...v, [msg.id]: { data } }))
    } catch (e) {
      setVideos(v => ({ ...v, [msg.id]: undefined }))
      showToast(e.message, 'error')
    }
  }

  const openCitation = (citation) => openCitationFile(citation, navigation).catch(e => showToast(e.message, 'error'))
  const openTool = (msg) => navigation.navigate(msg.kind === 'flashcards' ? 'Flashcards' : 'Practice', {
    messageId: msg.id, topic: msg.payload?.topic, courseCode: course?.code,
    cards: msg.payload?.cards ?? [], questions: msg.payload?.questions ?? [],
  })

  // Long-press a chat: the app's own sheets (same style as Sign Out) for options, rename and delete
  const chatOptions = (session) => setChatSheet({ mode: 'options', session })
  const closeSheet = () => setChatSheet(null)
  const deleteChat = async () => {
    const s = chatSheet.session
    try {
      await deleteChatSession(s.id)
      setSessions(list => list.filter(x => x.id !== s.id))
      if (s.id === sessionId) newChat()
      closeSheet()
    } catch (e) { showToast(e.message, 'error') }
  }
  const saveRename = async () => {
    const title = newTitle.trim()
    if (!title) return
    try {
      const updated = await renameChatSession(chatSheet.session.id, title)
      setSessions(list => list.map(s => (s.id === updated.id ? { ...s, title: updated.title } : s)))
      closeSheet()
    } catch (e) { showToast(e.message, 'error') }
  }


  const started = messages.length > 0 || loadingChat
  const topBarTop = insets.top + 6

  return (
    <KeyboardAvoidingView style={styles.screen} behavior="padding">
      <View style={[styles.topBar, { paddingTop: topBarTop }]}>
        <TouchableOpacity
          onPress={() => { setHistoryOpen(true); loadSessions() }}
          accessibilityLabel="Chat history"
          testID="assistant-history"
          hitSlop={HIT}
          style={styles.iconBtn}
        >
          <Ionicons name="time-outline" size={24} color={C.text} />
        </TouchableOpacity>
        {started ? (
          <TouchableOpacity style={styles.smallCourse} onPress={() => setPickerOpen(true)} testID="assistant-course-small">
            <Text style={styles.smallCourseText}>{courseLabel(course)}</Text>
            <Ionicons name="chevron-down" size={14} color={C.textSub} />
          </TouchableOpacity>
        ) : <View />}
        <TouchableOpacity
          onPress={() => setToolsOpen(true)}
          accessibilityLabel="Study tools"
          testID="assistant-tools"
          hitSlop={HIT}
          style={styles.iconBtn}
          disabled={!courseId}
        >
          <Ionicons name="albums-outline" size={23} color={courseId ? C.text : C.textHint} />
        </TouchableOpacity>
      </View>

      <View style={styles.flex}>
        {courses === null ? (
          <ActivityIndicator style={{ marginTop: 60 }} color={C.primary} />
        ) : courses.length === 0 ? (
          <View style={styles.center}>
            <Ionicons name="school-outline" size={36} color={C.textHint} />
            <Text style={styles.hint}>You aren't enrolled in any course yet.</Text>
          </View>
        ) : !started ? (
          <View style={styles.center}>
            <View style={styles.logo}><Ionicons name="sparkles" size={30} color={C.primary} /></View>
            <TouchableOpacity style={styles.bigCourse} onPress={() => setPickerOpen(true)} testID="assistant-course-picker">
              <Text style={styles.bigCourseText} numberOfLines={1}>{courseLabel(course, { long: true })}</Text>
              <Ionicons name="chevron-down" size={16} color={C.text} />
            </TouchableOpacity>
            <Text style={styles.hint}>
              {course?.indexed_materials > 0
                ? `Ask anything about ${course.code}. Answers come from ${course.indexed_materials} materials on SPeCTRUM.`
                : 'No materials yet for this course, so answers are general knowledge only.'}
            </Text>
          </View>
        ) : loadingChat ? (
          <ActivityIndicator style={{ marginTop: 60 }} color={C.primary} />
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={m => String(m.id)}
            renderItem={({ item }) => (item.role === 'user'
              ? <UserMessage msg={item} />
              : (
                <AssistantMessage
                  msg={item}
                  onOpenCitation={openCitation}
                  onOpenTool={openTool}
                  videos={videos[item.id]}
                  onFindVideos={findVideos}
                />
              ))}
            contentContainerStyle={[styles.list, sending && styles.listWhileSending]}
            keyboardShouldPersistTaps="handled"
            onScroll={e => {
              const near = isNearBottom(e.nativeEvent)
              nearBottomRef.current = near
              if (near !== atBottom) setAtBottom(near)
            }}
            scrollEventThrottle={100}
            // Follow new content only while at the bottom, so reading an older answer isn't interrupted
            onContentSizeChange={() => { if (nearBottomRef.current) listRef.current?.scrollToEnd({ animated: true }) }}
          />
        )}
        {started && !loadingChat && !atBottom ? (
          <TouchableOpacity
            style={styles.toBottom}
            onPress={scrollToLatest}
            accessibilityLabel="Jump to latest"
            testID="assistant-to-bottom"
          >
            <Ionicons name="arrow-down" size={20} color={C.text} />
          </TouchableOpacity>
        ) : null}
        {sending ? (
          <View style={styles.thinking} testID="assistant-thinking" pointerEvents="none">
            <ActivityIndicator size="small" color={C.primary} />
            <Text style={styles.thinkingText}>{messages[messages.length - 1]?.kind !== 'chat' ? 'Working on it…' : 'Drafting answer…'}</Text>
          </View>
        ) : null}
      </View>

      {tool ? (
        <View style={styles.toolTag} testID="assistant-tool-tag">
          <Ionicons name={toolFor(tool).icon} size={14} color={C.primary} />
          <Text style={styles.toolTagText}>{toolFor(tool).label}</Text>
          <TouchableOpacity onPress={() => setTool(null)} accessibilityLabel="Cancel study tool" hitSlop={HIT}>
            <Ionicons name="close" size={15} color={C.primary} />
          </TouchableOpacity>
        </View>
      ) : null}
      <View style={styles.inputBar}>
        <TextInput
          ref={inputRef}
          testID="assistant-input"
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder={inputPlaceholder(tool)}
          placeholderTextColor={C.textHint}
          multiline
          maxLength={tool ? 200 : 2000}
          editable={!!courseId}
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

      <CoursePicker
        visible={pickerOpen}
        courses={courses ?? []}
        value={courseId}
        onPick={pickCourse}
        onClose={() => setPickerOpen(false)}
      />
      <ToolsMenu visible={toolsOpen} top={topBarTop + 40} onPick={pickTool} onClose={() => setToolsOpen(false)} />
      <HistoryPanel
        visible={historyOpen}
        sessions={sessions}
        courses={courses ?? []}
        currentId={sessionId}
        loading={loadingSessions}
        onOpen={openSession}
        onNew={newChat}
        onOptions={chatOptions}
        onClose={() => setHistoryOpen(false)}
      />
      <Sheet visible={!!chatSheet} onClose={closeSheet}>
        {chatSheet?.mode === 'options' ? (
          <>
            <ModalTitle>{chatSheet.session.title || 'Untitled chat'}</ModalTitle>
            <SheetOption
              label="Rename" icon="create-outline" testID="chat-rename"
              onPress={() => { setNewTitle(chatSheet.session.title ?? ''); setChatSheet({ ...chatSheet, mode: 'rename' }) }}
            />
            <SheetOption
              label="Delete" icon="trash-outline" danger testID="chat-delete"
              onPress={() => setChatSheet({ ...chatSheet, mode: 'delete' })}
            />
            <View style={{ height: 8 }} />
          </>
        ) : chatSheet?.mode === 'rename' ? (
          <>
            <ModalTitle>Rename chat</ModalTitle>
            <TextInput
              testID="rename-input"
              style={[modalStyles.input, { marginTop: 8 }]}
              value={newTitle}
              onChangeText={setNewTitle}
              maxLength={255}
              autoFocus
              selectTextOnFocus
              placeholder="Chat name"
              placeholderTextColor={C.textHint}
              onSubmitEditing={saveRename}
            />
            <BtnRow>
              <BtnOutline label="Cancel" onPress={closeSheet} />
              <BtnPrimary label="Save" onPress={saveRename} disabled={!newTitle.trim()} testID="rename-save" />
            </BtnRow>
          </>
        ) : chatSheet?.mode === 'delete' ? (
          <>
            <ModalTitle>Delete chat?</ModalTitle>
            <Text style={[modalStyles.bodyText, { marginBottom: 18 }]}>
              "{chatSheet.session.title || 'Untitled chat'}" and everything in it will be deleted.
            </Text>
            <BtnRow>
              <BtnOutline label="Cancel" onPress={closeSheet} />
              <BtnDanger label="Delete" icon="trash-outline" onPress={deleteChat} testID="chat-delete-confirm" />
            </BtnRow>
          </>
        ) : null}
      </Sheet>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex: { flex: 1 },
  topBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 12, paddingBottom: 6,
    backgroundColor: C.bg, zIndex: 1,   // so chat bubbles never show through while scrolling
  },
  iconBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  smallCourse: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: C.card,
    borderWidth: 1, borderColor: C.border,
  },
  smallCourseText: { fontSize: 13, fontWeight: '600', color: C.text },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 28, gap: 14 },
  logo: {
    width: 64, height: 64, borderRadius: 32, backgroundColor: C.blueLt,
    alignItems: 'center', justifyContent: 'center',
  },
  bigCourse: {
    flexDirection: 'row', alignItems: 'center', gap: 8, maxWidth: '100%',
    paddingHorizontal: 16, paddingVertical: 11, borderRadius: 12,
    backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
  },
  bigCourseText: { fontSize: 15, fontWeight: '600', color: C.text, flexShrink: 1 },
  hint: { fontSize: 13, color: C.textSub, textAlign: 'center', lineHeight: 19 },
  list: { padding: 12, paddingBottom: 20, flexGrow: 1 },
  listWhileSending: { paddingBottom: 64 },
  bubble: { maxWidth: '88%', borderRadius: 14, padding: 12, marginBottom: 10 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: C.primary, borderBottomRightRadius: 4 },
  userText: { color: '#fff', fontSize: 15, lineHeight: 21 },
  userToolRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 2, opacity: 0.9 },
  userToolText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  // A fixed width, not shrink-to-fit: on some Android phones a shrink-to-fit bubble was measured
  // too narrow after the tool tag changed the layout, and the answer spilled out of it (2026-11-14)
  botBubble: {
    alignSelf: 'flex-start', width: '88%', backgroundColor: C.card, borderBottomLeftRadius: 4,
    borderWidth: 1, borderColor: C.border,
  },
  generalTag: {
    flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start',
    backgroundColor: C.orangeLt, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 3, marginBottom: 8,
  },
  generalText: { fontSize: 11, fontWeight: '600', color: C.orangeDk },
  kindTag: {
    flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start',
    backgroundColor: C.blueLt, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 3, marginBottom: 6,
  },
  kindTagText: { fontSize: 11, fontWeight: '600', color: C.primary },
  chips: { marginTop: 10, gap: 6 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.blueLt, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6,
  },
  chipNum: { fontSize: 12, fontWeight: '700', color: C.primary },
  chipText: { flex: 1, fontSize: 12, color: C.blueDk },
  toolHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  toolTitle: { fontSize: 15, fontWeight: '700', color: C.text },
  toolTopic: { fontSize: 13, color: C.textSub, marginTop: 2 },
  toolEmpty: { fontSize: 14, color: C.textSub },
  toolBtn: {
    marginTop: 10, borderRadius: 10, borderWidth: 1, borderColor: C.primary,
    paddingVertical: 9, alignItems: 'center',
  },
  toolBtnText: { fontSize: 14, fontWeight: '600', color: C.primary },
  findVideos: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
    marginTop: 10, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16,
    borderWidth: 1, borderColor: C.border,
  },
  findVideosText: { fontSize: 12, fontWeight: '600', color: C.textSub },
  videos: { marginTop: 10, gap: 8 },
  video: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  thumb: { width: 96, height: 54, borderRadius: 6, backgroundColor: C.gray100 },
  thumbEmpty: { alignItems: 'center', justifyContent: 'center' },
  videoTitle: { fontSize: 13, fontWeight: '600', color: C.text },
  videoChannel: { fontSize: 11, color: C.textSub, marginTop: 2 },
  keywordsLabel: { fontSize: 12, color: C.textSub },
  keywords: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  keyword: { borderRadius: 12, backgroundColor: C.gray100, paddingHorizontal: 9, paddingVertical: 4 },
  keywordText: { fontSize: 12, color: C.text },
  thinking: {
    position: 'absolute', bottom: 12, alignSelf: 'center',
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: C.card, borderRadius: 20, borderWidth: 1, borderColor: C.border,
    paddingHorizontal: 16, paddingVertical: 9, elevation: 4,
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
  },
  toBottom: {
    position: 'absolute', right: 14, bottom: 12, width: 40, height: 40, borderRadius: 20,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: C.card, borderWidth: 1, borderColor: C.border, elevation: 4,
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
  },
  thinkingText: { fontSize: 14, fontWeight: '600', color: C.text },
  toolTag: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
    marginLeft: 12, marginBottom: 6, paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 14, backgroundColor: C.blueLt,
  },
  toolTagText: { fontSize: 12, fontWeight: '600', color: C.primary },
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
  backdropCenter: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'center', padding: 24,
  },
  sheet: { backgroundColor: C.card, borderRadius: 14, padding: 16 },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: C.text, marginBottom: 10 },
  sheetRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, paddingHorizontal: 8, borderRadius: 8 },
  sheetRowActive: { backgroundColor: C.blueLt },
  sheetRowText: { fontSize: 14, fontWeight: '600', color: C.text },
  sheetRowMeta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  menu: {
    position: 'absolute', right: 12, width: 190, backgroundColor: C.card, borderRadius: 12,
    borderWidth: 1, borderColor: C.border, paddingVertical: 6, elevation: 6,
    shadowColor: '#000', shadowOpacity: 0.15, shadowRadius: 10, shadowOffset: { width: 0, height: 4 },
  },
  menuRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 11 },
  menuText: { fontSize: 15, color: C.text },
  panelBackdrop: { flex: 1, flexDirection: 'row', backgroundColor: 'rgba(0,0,0,0.35)' },
  panel: { width: '82%', maxWidth: 360, backgroundColor: C.card, paddingHorizontal: 14 },
  panelHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  panelTitle: { fontSize: 18, fontWeight: '700', color: C.text },
  newChatBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 10, marginBottom: 10,
  },
  newChatText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  panelEmpty: { fontSize: 13, color: C.textSub, textAlign: 'center', marginTop: 20 },
  panelRow: { paddingVertical: 10, paddingHorizontal: 8, borderRadius: 8 },
  panelRowActive: { backgroundColor: C.blueLt },
  panelRowTitle: { fontSize: 14, fontWeight: '600', color: C.text },
  panelRowMeta: { fontSize: 12, color: C.textSub, marginTop: 2 },
  panelHint: { fontSize: 11, color: C.textHint, textAlign: 'center', marginVertical: 12 },
})
