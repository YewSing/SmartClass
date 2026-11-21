export function notificationRoute(link) {
  if (typeof link !== 'string' || !link.startsWith('/') || link.startsWith('//')) return null
  const interaction = link.match(/^\/interaction\/sessions\/([1-9]\d*)$/)
  if (interaction) {
    const sessionId = Number(interaction[1])
    return Number.isSafeInteger(sessionId) ? { screen: 'LiveClass', params: { sessionId } } : null
  }
  const attendance = link.match(/^\/attendance\/sessions\/(\d+)$/)
  if (attendance) return { tab: 'Attendance' }
  if (link === '/attendance') return { tab: 'Attendance' }
  return null
}

export function formatDashboardTime(value) {
  if (!value) return 'Not refreshed yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Refresh time unavailable' : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function attendanceLabel(status) {
  if (!status) return 'No attendance yet'
  return status.replace('_', ' ').replace(/^./, value => value.toUpperCase())
}

export function formatMoodleDate(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return 'Date unavailable'
  return new Date(numeric * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export function safeMoodleUrl(value) {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' ? url.toString() : null
  } catch { return null }
}

export function isDashboardStale(value, now = Date.now()) {
  const refreshed = new Date(value).getTime()
  return !Number.isFinite(refreshed) || now - refreshed > 24 * 60 * 60 * 1000
}
