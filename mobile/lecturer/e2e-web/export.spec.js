// CSV export in the browser really downloads a file with the backend's CSV in it.
const fs = require('fs')
const { test, expect } = require('@playwright/test')

const visible = (locator) => locator.filter({ visible: true }).first()

test('Analytics export downloads the attendance CSV and says so', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()

  await page.getByTestId('sidenav-Analytics').click()
  // The button does nothing until the class's analytics have loaded.
  await expect(async () => {
    await visible(page.getByText('Export', { exact: true })).click()
    await expect(visible(page.getByText('Export Attendance', { exact: true }))).toBeVisible({ timeout: 1000 })
  }).toPass({ timeout: 60_000 })
  // Phones choose a save folder; a browser uses its own download folder.
  await expect(page.getByText(/Saves to|choose where to save/)).toHaveCount(0)

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    visible(page.getByText('Export CSV', { exact: true })).click(),
  ])

  const name = download.suggestedFilename()
  expect(name).toMatch(/^attendance_report_.+\.csv$/)
  const csv = fs.readFileSync(await download.path(), 'utf8')
  expect(csv.split('\n')[0]).toMatch(/matric/i)

  await expect(visible(page.getByText(`Downloaded ${name}`, { exact: true }))).toBeVisible()
  await expect(page.getByText('Export Attendance', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})
