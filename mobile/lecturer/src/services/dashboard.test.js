import test from 'node:test'
import assert from 'node:assert/strict'
import { notificationRoute } from './dashboard.js'

test('routes only known lecturer notification links', () => {
  assert.deepEqual(notificationRoute('/classes/9'), { screen: 'ClassDetail', params: { classId: 9 } })
  assert.deepEqual(notificationRoute('/quizzes/7'), { tab: 'Quiz', screen: 'QuizList' })
  assert.equal(notificationRoute('/attendance/sessions/12'), null)
  assert.equal(notificationRoute('https://evil.example'), null)
  assert.equal(notificationRoute('/quiz/1'), null)
})
