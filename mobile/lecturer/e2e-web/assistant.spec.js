// AI Assistant in the browser (T102, FR-815/FR-816): a lecturer asks their own materials and sees a
// citation (which opens the source), then reads the seeded "before next class" summary.
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

test('a lecturer asks their materials, opens a citation, and reads the before-class summary', async ({ page }) => {
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

  // The citation opens the source
  await visible(page.getByTestId('lecturer-citation')).click()
  await expect(page.getByText('Cited passage', { exact: true })).toBeVisible()
  await expect(page.getByText(/Open file at (slide|page|section) \d+/)).toBeVisible()
  await visible(page.getByLabel('Back')).click()

  // Back on the assistant screen, read the before-next-class summary (FR-816)
  await visible(page.getByLabel('Back')).click()
  await expect(page.getByTestId('assistant-before-class')).toBeVisible()
  await page.getByTestId('assistant-before-class').click()
  await expect(visible(page.getByText('Revisit', { exact: true }))).toBeVisible()
  await expect(page.getByText('Boundary value analysis is covered in the notes [1].')).toBeVisible()
  await expect(page.getByText('Not covered by the materials', { exact: true })).toBeVisible()

  expect(errors).toEqual([])
})
