// AI Assistant in the browser (T102, FR-815/FR-816): a lecturer asks their own materials, opens a
// citation (the file itself, in a new tab), finds the chat again after leaving, opens the collapsed
// Materials list, then reads the seeded "before next class" summary.
// Seeds a material + question history for devlecturer's WIA0000 and removes them again afterwards.
const path = require('path')
const { execFileSync } = require('child_process')
const { test, expect } = require('@playwright/test')

const BACKEND = path.join(__dirname, '..', '..', '..', 'backend')
const seed = (action) =>
  execFileSync('python', ['scripts/e2e_assistant.py', action, '--course', 'WIA0000'], { cwd: BACKEND, stdio: 'pipe' })

const visible = (locator) => locator.filter({ visible: true }).first()

async function login(page) {
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
}

test.beforeAll(() => { seed('seed') })
test.afterAll(() => { seed('teardown') })

test('a lecturer asks their materials, opens a citation, keeps the chat, and reads the before-class summary', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await login(page)
  await page.getByTestId('sidenav-Assistant').click()
  await expect(page.getByTestId('assistant-course-picker')).toBeVisible()

  // Ask my materials (FR-815): the fake LLM cites passage [1]
  await page.getByTestId('assistant-ask').click()
  await expect(page.getByTestId('lecturer-ask-input')).toBeVisible()
  await page.getByTestId('lecturer-ask-input').fill('What is boundary value analysis?')
  await page.getByTestId('lecturer-ask-send').click()
  await expect(visible(page.getByText(/This is a test answer from your course materials \[1\]\./))).toBeVisible()

  // The citation opens the file itself in a new tab (no in-between screen). The file comes from
  // Moodle, which the E2E backend doesn't reach, so the download is answered here with a tiny PDF.
  // (the app and the API are on different ports, so the stand-in answers CORS like the backend does)
  await page.route('**/lecturer/assistant/materials/*/file', (route) => {
    const cors = {
      'Access-Control-Allow-Origin': route.request().headers().origin ?? '*',
      'Access-Control-Allow-Headers': 'authorization, content-type',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
    }
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
    return route.fulfill({ status: 200, headers: cors, contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF\n' })
  })
  // (headless Chromium has no PDF viewer, so the check is: a tab opened and the file was fetched)
  const popup = page.waitForEvent('popup')
  const fileFetch = page.waitForResponse((r) => /\/lecturer\/assistant\/materials\/\d+\/file$/.test(r.url())
    && r.request().method() === 'GET')
  await visible(page.getByTestId('lecturer-citation')).click()
  const [tab, fileResponse] = await Promise.all([popup, fileFetch])
  expect(fileResponse.status()).toBe(200)
  await tab.close()
  await expect(page.getByText('Cited passage', { exact: true })).toHaveCount(0)

  // Leaving and coming back continues the same chat
  await visible(page.getByLabel('Back')).click()
  await page.getByTestId('assistant-ask').click()
  await expect(visible(page.getByText('What is boundary value analysis?', { exact: true }))).toBeVisible()
  await expect(visible(page.getByText(/This is a test answer from your course materials \[1\]\./))).toBeVisible()
  // and "New chat" starts an empty one
  await visible(page.getByTestId('lecturer-new-chat')).click()
  await expect(page.getByText('What is boundary value analysis?', { exact: true })).toHaveCount(0)
  await visible(page.getByLabel('Back')).click()

  // The Materials list starts collapsed and opens on tap
  await expect(page.getByTestId('assistant-materials')).toHaveCount(0)
  await page.getByTestId('assistant-materials-toggle').click()
  await expect(visible(page.getByTestId('assistant-materials'))).toBeVisible()

  // Read the before-next-class summary (FR-816)
  await expect(page.getByTestId('assistant-before-class')).toBeVisible()
  await page.getByTestId('assistant-before-class').click()
  await expect(visible(page.getByText('Revisit', { exact: true }))).toBeVisible()
  await expect(page.getByText('Boundary value analysis is covered in the notes [1].')).toBeVisible()
  await expect(page.getByText('Not covered by the materials', { exact: true })).toBeVisible()

  expect(errors).toEqual([])
})
