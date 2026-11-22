// Notification centre helpers (FR-208, FR-209, FR-213; plan-shino.md S19). No React or storage
// here, so it runs under `npm test`. The same file (except the deep links) is in the student app.

// ─── Feed state ──────────────────────────────────────────────────────────────
// { items: newest first, nextCursor, unread, loaded }

export const initialFeed = { items: [], nextCursor: null, unread: 0, loaded: false }

// The API sends naive MYT times; read them as +08:00 wherever the phone is.
export function parseTime(iso) {
  if (!iso) return null
  const s = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}+08:00`
  const t = new Date(s)
  return Number.isNaN(t.getTime()) ? null : t
}

function newestFirst(a, b) {
  const ta = parseTime(a.created_at)?.getTime() ?? 0
  const tb = parseTime(b.created_at)?.getTime() ?? 0
  return tb - ta || b.id - a.id
}

// Incoming items replace known ones with the same id; the result is newest first, no repeats.
export function mergeItems(existing, incoming) {
  const byId = new Map(existing.map(n => [n.id, n]))
  for (const n of incoming) byId.set(n.id, n)
  return [...byId.values()].sort(newestFirst)
}

export function feedReducer(state, action) {
  switch (action.type) {
    case 'page': {
      // action.page = GET /notifications body; append = an older page ("load more"), else the
      // first page replaces the list (refresh, reconnect)
      const { items, next_cursor, unread_count } = action.page
      return {
        items: action.append ? mergeItems(state.items, items) : [...items].sort(newestFirst),
        nextCursor: next_cursor,
        unread: unread_count,
        loaded: true,
      }
    }
    case 'live':
      // {type:"notification", notification, unread_count} from the websocket
      return { ...state, items: mergeItems(state.items, [action.notification]), unread: action.unread }
    case 'count':
      return { ...state, unread: action.unread }
    case 'read':
      // POST /notifications/{id}/read → {notification, unread_count}
      return { ...state, items: mergeItems(state.items, [action.notification]), unread: action.unread }
    case 'read_all': {
      const readAt = action.readAt ?? new Date().toISOString()
      return {
        ...state,
        items: state.items.map(n => n.read ? n : { ...n, read: true, read_at: readAt }),
        unread: action.unread ?? 0,
      }
    }
    case 'reset':
      return initialFeed
    default:
      return state
  }
}

// ─── Display ─────────────────────────────────────────────────────────────────

export function countLabel(n) {
  if (!n || n < 0) return ''
  return n > 99 ? '99+' : String(n)
}

export function bellLabel(n) {
  if (!n) return 'Notifications, none unread'
  return `Notifications, ${n} unread`
}

const PRIORITY = {
  urgent:    { variant: 'red',    label: 'Urgent' },
  important: { variant: 'orange', label: 'Important' },
  general:   { variant: 'gray',   label: 'General' },
}
export function priorityBadge(priority) {
  return PRIORITY[priority] ?? PRIORITY.general
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "Just now", "5 min ago", "3 h ago", "Yesterday", "21 Nov" (MYT dates)
export function timeLabel(iso, now = new Date()) {
  const t = parseTime(iso)
  if (!t) return ''
  const mins = Math.floor((now.getTime() - t.getTime()) / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins} min ago`
  const myt = (d) => new Date(d.getTime() + 8 * 3600000)   // MYT calendar day, any phone time zone
  const day = (d) => Math.floor(myt(d).getTime() / 86400000)
  const days = day(now) - day(t)
  if (days === 0) return `${Math.floor(mins / 60)} h ago`
  if (days === 1) return 'Yesterday'
  const m = myt(t)
  return `${m.getUTCDate()} ${MONTHS[m.getUTCMonth()]}`
}

// ─── Deep links ──────────────────────────────────────────────────────────────
// Notification links are app-relative paths (S10). Each maps to a screen, or null when this app
// has no screen for it yet (the feed item shows the full text instead).

const LINK_ROUTES = [
  [/^\/attendance\/sessions\/(\d+)$/, m => ({ kind: 'session', sessionId: Number(m[1]) })],
  [/^\/face-verification$/,           () => ({ kind: 'screen', tab: 'Home', screen: 'FaceVerification' })],
  [/^\/analytics\/courses\/\d+$/,     () => ({ kind: 'screen', tab: 'Analytics', screen: 'AnalyticsScreen' })],
  [/^\/home$/,                        () => ({ kind: 'screen', tab: 'Home', screen: 'Dashboard' })],
]

export function linkTarget(link) {
  if (typeof link !== 'string') return null
  const path = link.split('?')[0]
  for (const [re, make] of LINK_ROUTES) {
    const m = path.match(re)
    if (m) return make(m)
  }
  return null
}

// The lecturer's session with this id (for AttendanceDetail)
export function findSessionById(sessions, sessionId) {
  return (sessions ?? []).find(s => String(s.id) === String(sessionId)) ?? null
}

// ─── Preferences (FR-214) ────────────────────────────────────────────────────

// Only `general` can change; urgent/important are always on (the API answers 422 otherwise).
export function prefsUpdate(channel, on) {
  return { [channel]: { general: Boolean(on) } }
}
