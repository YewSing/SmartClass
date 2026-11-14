// Classroom interaction in the browser (S26, FR-501-FR-508): open a live session from Home,
// post a live question, create and close a poll, then close the session from Home again.
// Uses the always-open dev class (WIA0000), so no Moodle sync is needed.
const { test, expect } = require('@playwright/test')

const visible = (locator) => locator.filter({ visible: true }).first()

test('lecturer opens a live session from Home, runs it and closes it from Home', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()

  // A previous run may have left a session open: close it first so this run starts clean.
  await expect(visible(page.getByTestId('home-interaction-toggle'))).toBeVisible()
  if (await page.getByTestId('home-interaction-close').count()) {
    await visible(page.getByTestId('home-interaction-close')).click()
    await expect(visible(page.getByText('Start interaction', { exact: true }))).toBeVisible()
  }

  // Open from Home (UC-501 step 1) and land on the live view.
  await visible(page.getByTestId('home-interaction-toggle')).click()
  await expect(visible(page.getByText('Session is open'))).toBeVisible()

  // Post a live question (FR-506) and see it on the screen.
  await visible(page.getByTestId('interaction-live-question-input')).fill('Is everyone following?')
  await visible(page.getByTestId('interaction-post-question-btn')).click()
  await expect(visible(page.getByText('Is everyone following?', { exact: true }))).toBeVisible()

  // Create a poll (FR-504) and close voting (FR-505); the session stays open.
  await visible(page.getByTestId('interaction-poll-question-input')).fill('Ready for the quiz?')
  await visible(page.getByTestId('interaction-poll-option-0')).fill('Yes')
  await visible(page.getByTestId('interaction-poll-option-1')).fill('No')
  await visible(page.getByTestId('interaction-create-poll-btn')).click()
  await expect(visible(page.getByText('Latest poll', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText('Ready for the quiz?', { exact: true }))).toBeVisible()
  await visible(page.getByTestId('interaction-close-poll-btn')).click()
  await expect(visible(page.getByText('Voting closed'))).toBeVisible()
  await expect(visible(page.getByText('Session is open'))).toBeVisible()

  // Back to Home and close the session there (UC-501).
  await page.getByTestId('sidenav-Home').click()
  await visible(page.getByTestId('home-interaction-close')).click()
  await expect(visible(page.getByText('Start interaction', { exact: true }))).toBeVisible()

  expect(errors).toEqual([])
})
