// A lecturer taps a class on Home or Profile and sees everyone enrolled in it.
// Uses the seeded devlecturer, who teaches the always-open class WIA0000 (five Moodle students).
const { test, expect } = require('@playwright/test')

const visible = (locator) => locator.filter({ visible: true }).first()

async function login(page) {
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(page.getByTestId('sidenav-Home')).toBeVisible()
}

async function expectStudentList(page) {
  const rows = page.getByTestId('class-student').filter({ visible: true })
  await expect(rows.first()).toBeVisible()
  const count = await rows.count()
  expect(count).toBeGreaterThan(0)
  await expect(visible(page.getByTestId('class-student-count'))).toHaveText(`${count} student${count === 1 ? '' : 's'}`)
  return count
}

test('Home class card opens the class details with its students', async ({ page }) => {
  await login(page)
  // The card can't be tapped until the classes have loaded
  await expect(visible(page.getByTestId('home-class-card'))).toContainText('WIA0000')
  await visible(page.getByTestId('home-class-card')).click()
  await expect(visible(page.getByText('Class details', { exact: true }))).toBeVisible()
  await expectStudentList(page)
  await visible(page.getByLabel('Back')).click()
  await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
})

test('Profile class card opens the same list, and search narrows it', async ({ page }) => {
  await login(page)
  await visible(page.getByLabel('Profile')).click()
  await visible(page.getByTestId('profile-class-card')).click()
  const count = await expectStudentList(page)

  const firstName = await page.getByTestId('class-student-name').filter({ visible: true }).first().textContent()
  const search = visible(page.getByPlaceholder('Search name or matric no.'))
  await search.fill(firstName)
  await expect(page.getByTestId('class-student').filter({ visible: true }).first()).toBeVisible()
  expect(await page.getByTestId('class-student').filter({ visible: true }).count()).toBeLessThanOrEqual(count)

  await search.fill('nobody-has-this-name')
  await expect(page.getByTestId('class-student').filter({ visible: true })).toHaveCount(0)
  await expect(visible(page.getByText('No student matches your search.'))).toBeVisible()
})

test('a course name that starts with its code is not shown twice', async ({ page }) => {
  await login(page)
  await visible(page.getByLabel('Profile')).click()
  await expect(visible(page.getByText('WIA0000 — WIA0000'))).toHaveCount(0)
  await visible(page.getByTestId('profile-class-card')).click()
  await expect(visible(page.getByTestId('class-detail-name'))).not.toHaveText(/^WIA0000/)
})
