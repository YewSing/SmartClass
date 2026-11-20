export function notificationRoute(link) {
  if (typeof link !== 'string' || !link.startsWith('/') || link.startsWith('//')) return null
  if (link === '/face-verification') return { screen: 'FaceVerification' }
  if (/^\/quizzes\/\d+$/.test(link)) return { tab: 'Quiz', screen: 'QuizList' }
  const classLink = link.match(/^\/classes\/(\d+)$/)
  if (classLink) return { screen: 'ClassDetail', params: { classId: Number(classLink[1]) } }
  return null
}

export function formatDashboardTime(value) {
  if (!value) return 'Not refreshed yet'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Refresh time unavailable' : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}
