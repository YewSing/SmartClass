// Pure helpers for the AI Assistant screen (redesign 2026-11-13), kept here so they can be unit tested.

// The study tools menu (top right). `kind` is what the API calls each tool. "Study guide" was taken
// out of the menu on 2026-11-14 (too close to a normal answer); older chats can still hold one.
export const TOOLS = [
  { kind: 'summary', label: 'Summarise', icon: 'document-text-outline', placeholder: 'Topic to summarise…' },
  { kind: 'flashcards', label: 'Flashcards', icon: 'albums-outline', placeholder: 'Topic for flashcards…' },
  { kind: 'practice_questions', label: 'Practice', icon: 'help-circle-outline', placeholder: 'Topic to practise…' },
]
const OLD_TOOLS = [
  { kind: 'study_guide', label: 'Study guide', icon: 'book-outline', placeholder: 'Topic for a study guide…' },
]

export function toolFor(kind) {
  return TOOLS.find(t => t.kind === kind) ?? OLD_TOOLS.find(t => t.kind === kind) ?? null
}

// What the message box says: a question, or the topic for the chosen tool
export function inputPlaceholder(tool) {
  return toolFor(tool)?.placeholder ?? 'Ask a question…'
}

// "Last score 4 / 5" on a practice message, or nothing before the first try
export function scoreLabel(payload) {
  const s = payload?.last_score
  return s ? `Last score ${s.correct} / ${s.total}` : null
}

// Which option is right. The server stores the option text, but practice saved before 2026-11-14
// can hold a letter ("B"), which made every pick look wrong, so letters still work here.
export function answerIndex(q) {
  const options = q?.options ?? []
  const answer = String(q?.answer ?? '').trim()
  let i = options.indexOf(answer)
  if (i >= 0) return i
  i = options.findIndex(o => o.trim().toLowerCase() === answer.toLowerCase())
  if (i >= 0) return i
  const m = /^\(?([A-Ha-h])[).:]?$/.exec(answer)
  if (m) {
    i = m[1].toUpperCase().charCodeAt(0) - 65
    if (i < options.length) return i
  }
  return -1
}

// How many of the student's picks were right ({questionIndex: optionIndex})
export function countCorrect(questions, picks) {
  return questions.reduce((n, q, i) => (picks[i] !== undefined && picks[i] === answerIndex(q) ? n + 1 : n), 0)
}

// The chat shows a "jump to latest" button once the student has scrolled this far up
export function isNearBottom({ contentOffset, contentSize, layoutMeasurement }, slack = 120) {
  return contentSize.height - layoutMeasurement.height - contentOffset.y <= slack
}

// Videos are offered under answers that come from the course materials (FR-812)
export function canFindVideos(msg) {
  return msg.role === 'assistant' && msg.source_type === 'course'
    && (msg.kind === 'chat' || msg.kind === 'summary' || msg.kind === 'study_guide' || !msg.kind)
}

// The topic to search videos for: the stored topic label, else the tool's topic
export function videoTopic(msg) {
  return msg.topic || msg.payload?.topic || null
}

export function youtubeSearchUrl(keyword) {
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(keyword)}`
}

// "WIF3001" for the compact header; "WIF3001 · Software Testing" for the big dropdown
export function courseLabel(course, { long = false } = {}) {
  if (!course) return 'Pick a course'
  if (!long) return course.code
  const name = (course.name ?? '').replace(new RegExp(`^${course.code}\\s*`), '')
  return name ? `${course.code} · ${name}` : course.code
}

export function timeAgo(iso, now = Date.now()) {
  const mins = Math.round((now - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs} h ago`
  return new Date(iso).toLocaleDateString('en-MY', { day: 'numeric', month: 'short', timeZone: 'Asia/Kuala_Lumpur' })
}
