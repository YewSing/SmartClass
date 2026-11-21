const events = new Set([
  'interaction.state',
  'interaction.session_status',
  'interaction.questions_changed',
  'interaction.polls_changed',
  'interaction.poll_results_changed',
  'interaction.quick_prompts_changed',
])

export function readInteractionEvent(data, sessionId) {
  let event
  try { event = JSON.parse(data) } catch { return null }
  return event?.attendance_session_id === sessionId && events.has(event.event) ? event : null
}

export function applyInteractionStatus(state, event) {
  if (!state || !['interaction.state', 'interaction.session_status'].includes(event.event)) return state
  if (!['closed', 'needs_confirmation', 'cancelled', 'scheduled'].includes(event.status)) return state
  return { ...state, status: event.status, can_participate: false }
}
