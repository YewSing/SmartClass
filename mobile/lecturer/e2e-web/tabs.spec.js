// Pressing a tab always shows that tab's main page, not the page last left open inside it.
const { test, expect } = require('@playwright/test')

const visible = (locator) => locator.filter({ visible: true }).first()

async function login(page) {
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(visible(page.getByTestId('home-class-card'))).toContainText('WIA0000')
}

async function expectHome(page) {
  await expect(visible(page.getByTestId('home-class-card'))).toBeVisible()
  await expect(page.getByText('My Profile', { exact: true }).filter({ visible: true })).toHaveCount(0)
}

async function openProfile(page) {
  await visible(page.getByLabel('Profile')).click()
  await expect(visible(page.getByText('My Profile', { exact: true }))).toBeVisible()
}

// Each layout has its own way to press a tab: the side menu, or the bottom tabs at phone width
const LAYOUTS = [
  { name: 'side menu', size: { width: 1280, height: 800 }, press: (page, tab) => page.getByTestId(`sidenav-${tab}`).click() },
  { name: 'bottom tabs', size: { width: 390, height: 844 }, press: (page, tab) => visible(page.getByRole('tab', { name: tab }).or(page.getByRole('link', { name: tab }))).click() },
]

for (const { name, size, press } of LAYOUTS) {
  test.describe(name, () => {
    test.use({ viewport: size })

    test('Home tab leaves the Profile page and shows Home', async ({ page }) => {
      await login(page)
      await openProfile(page)
      await press(page, 'Home')
      await expectHome(page)
    })

    test('coming back to Home from another tab shows Home, not Profile', async ({ page }) => {
      await login(page)
      await openProfile(page)
      await press(page, 'Attendance')
      await expect(visible(page.getByText('Attendance', { exact: true }))).toBeVisible()
      await press(page, 'Home')
      await expectHome(page)
    })

    test('the same holds for a page deeper inside another tab', async ({ page }) => {
      await login(page)
      // The quiz tab is a one-page placeholder now (plan-shino.md S02), so use the assistant's
      // "Before next class" page as the deeper page.
      await press(page, 'Assistant')
      await visible(page.getByTestId('assistant-before-class')).click()
      await expect(visible(page.getByLabel('Back'))).toBeVisible()
      await press(page, 'Analytics')
      await press(page, 'Assistant')
      await expect(visible(page.getByTestId('assistant-before-class'))).toBeVisible()
      await expect(page.getByLabel('Back').filter({ visible: true })).toHaveCount(0)
    })
  })
}
