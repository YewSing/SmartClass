// Pure helpers for the AI Assistant screen (redesign 2026-11-13), kept here so they can be unit tested.

// The study tools menu (top right). `kind` is what the API calls each tool.
export const TOOLS = [
  { kind: 'summary', label: 'Summarise', icon: 'document-text-outline', placeholder: 'Topic to summarise…' },
  { kind: 'study_guide', label: 'Study guide', icon: 'book-outline', placeholder: 'Topic for a study guide…' },
  { kind: 'flashcards', label: 'Flashcards', icon: 'albums-outline', placeholder: 'Topic for flashcards…' },
  { kind: 'practice_questions', label: 'Practice', icon: 'help-circle-outline', placeholder: 'Topic to practise…' },
]

export function toolFor(kind) {
  return TOOLS.find(t => t.kind === kind) ?? null
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

// How many of the student's picks were right ({questionIndex: optionIndex})
export function countCorrect(questions, picks) {
  return questions.reduce((n, q, i) => (picks[i] !== undefined && q.options[picks[i]] === q.answer ? n + 1 : n), 0)
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
