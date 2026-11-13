import assert from 'node:assert/strict'
import test from 'node:test'
import {
  TOOLS, toolFor, inputPlaceholder, scoreLabel, countCorrect, canFindVideos, videoTopic,
  youtubeSearchUrl, courseLabel, timeAgo,
} from './assistantView.js'

test('the study tools menu has the four tools the API knows', () => {
  assert.deepEqual(TOOLS.map(t => t.kind), ['summary', 'study_guide', 'flashcards', 'practice_questions'])
  assert.equal(toolFor('flashcards').label, 'Flashcards')
  assert.equal(toolFor('nope'), null)
})

test('a chosen tool changes the message box placeholder', () => {
  assert.equal(inputPlaceholder(null), 'Ask a question…')
  assert.equal(inputPlaceholder('flashcards'), 'Topic for flashcards…')
})

const questions = [
  { options: ['a', 'b'], answer: 'b' },
  { options: ['x', 'y', 'z'], answer: 'x' },
  { options: ['p', 'q'], answer: 'q' },
]

test('practice counts right answers, ignoring unanswered ones', () => {
  assert.equal(countCorrect(questions, { 0: 1, 1: 2 }), 1)
  assert.equal(countCorrect(questions, { 0: 1, 1: 0, 2: 1 }), 3)
  assert.equal(countCorrect(questions, {}), 0)
})

test('the last practice score shows only once there is one', () => {
  assert.equal(scoreLabel({ last_score: null }), null)
  assert.equal(scoreLabel({ last_score: { correct: 4, total: 5 } }), 'Last score 4 / 5')
})

test('related videos are offered under course answers and summaries only', () => {
  assert.equal(canFindVideos({ role: 'assistant', source_type: 'course', kind: 'chat' }), true)
  assert.equal(canFindVideos({ role: 'assistant', source_type: 'course', kind: 'study_guide' }), true)
  assert.equal(canFindVideos({ role: 'assistant', source_type: 'general', kind: 'chat' }), false)
  assert.equal(canFindVideos({ role: 'assistant', source_type: 'course', kind: 'flashcards' }), false)
  assert.equal(canFindVideos({ role: 'user', source_type: 'course', kind: 'chat' }), false)
})

test('videos search the topic label, else the tool topic', () => {
  assert.equal(videoTopic({ topic: 'Boundary value analysis', payload: { topic: 'bva' } }), 'Boundary value analysis')
  assert.equal(videoTopic({ topic: null, payload: { topic: 'bva' } }), 'bva')
  assert.equal(videoTopic({}), null)
  assert.equal(youtubeSearchUrl('bva tutorial'), 'https://www.youtube.com/results?search_query=bva%20tutorial')
})

test('the course shows short or long, without repeating the code', () => {
  const c = { code: 'WIF3001', name: 'WIF3001 Software Testing' }
  assert.equal(courseLabel(c), 'WIF3001')
  assert.equal(courseLabel(c, { long: true }), 'WIF3001 · Software Testing')
  assert.equal(courseLabel(null), 'Pick a course')
})

test('chats say how long ago they were used', () => {
  const now = new Date('2026-11-13T10:00:00Z').getTime()
  assert.equal(timeAgo('2026-11-13T09:59:50Z', now), 'just now')
  assert.equal(timeAgo('2026-11-13T09:30:00Z', now), '30 min ago')
  assert.equal(timeAgo('2026-11-13T07:00:00Z', now), '3 h ago')
})
