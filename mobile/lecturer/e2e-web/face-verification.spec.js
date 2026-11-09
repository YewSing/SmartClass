// Face verification queue in the browser (T19, FR-113): the review photos load (a browser can't send
// the token as an image header, so they come through blob URLs), and a rejection needs a reason.
// Seeds a pending submission by student7 (in devlecturer's WIA0000) with placeholder photos, and
// removes it again afterwards.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const STUDENT = 'student7@example.com'
const NAME = 'Jason Wong Kah Hoe'
const faceData = (action) =>
  execFileSync('python', ['scripts/e2e_face_review.py', action, '--student', STUDENT], { cwd: BACKEND, stdio: 'pipe' })

const visible = (locator) => locator.filter({ visible: true }).first()

test.beforeAll(() => { faceData('seed') })
test.afterAll(() => { faceData('clean') })

test('lecturer reviews the photos side by side and rejects with a reason', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()

  await visible(page.getByTestId('home-face-review')).click()
  const card = visible(page.getByTestId('face-submission').filter({ hasText: NAME }))
  await expect(card).toBeVisible()
  await expect(card.getByText('23004907 · WIA0000')).toBeVisible()
  await expect(card.getByText('Matric number on the card is different')).toBeVisible()

  // Three selfies and the card, all actually decoded from the API's PNGs
  const photos = card.locator('img')
  await expect(photos).toHaveCount(4)
  await expect.poll(() => photos.evaluateAll(imgs => imgs.filter(i => i.complete && i.naturalWidth > 0).length))
    .toBe(4)
  expect(await photos.first().getAttribute('src')).toMatch(/^blob:/)

  await card.getByText('Reject', { exact: true }).click()
  await card.getByText('Confirm reject', { exact: true }).click()
  await expect(card.getByText('Give a reason. The student sees it and can try again.')).toBeVisible()
  await card.getByTestId('face-reject-reason').fill('The card photo is someone else\'s card')
  await card.getByText('Confirm reject', { exact: true }).click()

  await expect(visible(page.getByText(`Rejected ${NAME}`, { exact: true }))).toBeVisible()
  await expect(page.getByTestId('face-submission').filter({ hasText: NAME })).toHaveCount(0)
  expect(errors).toEqual([])
})
