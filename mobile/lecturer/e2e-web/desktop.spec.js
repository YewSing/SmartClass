// T05: the lecturer app works in a desktop browser. Logs the seeded dev lecturer in at
// 1280 px, checks the side navigation and that nothing overflows sideways, then opens
// every current screen and the dialogs with no runtime error.
const { test, expect } = require('@playwright/test')

const visible = (locator) => locator.filter({ visible: true }).first()

// Elements sticking out past the right edge of the window, ignoring content inside
// horizontal scroll areas (those scroll on purpose).
async function horizontalOverflow(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth
    const doc = document.scrollingElement || document.documentElement
    const out = []
    if (doc.scrollWidth > vw + 1) out.push(`document scrollWidth ${doc.scrollWidth} > ${vw}`)
    for (const el of document.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0 || r.right <= vw + 1) continue
      let p = el.parentElement
      let clipped = false
      while (p && p !== document.body) {
        const ox = getComputedStyle(p).overflowX
        if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') {
          if (p.getBoundingClientRect().right <= vw + 1) { clipped = true; break }
        }
        p = p.parentElement
      }
      if (!clipped) out.push(`${el.tagName} "${(el.textContent || '').trim().slice(0, 30)}" right=${Math.round(r.right)}`)
    }
    return out.slice(0, 5)
  })
}

async function expectScreen(page, title) {
  await expect(visible(page.getByText(title, { exact: true }))).toBeVisible()
  expect(await horizontalOverflow(page)).toEqual([])
}

// The seeded dev lecturer is a local SmartClass account (no Moodle), so it uses the
// browser-only email sign-in; Moodle login itself is covered by the Maestro login flows.
async function signInLocal(page) {
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('DevTest@1234')
  await page.getByText('Sign In', { exact: true }).click()
}

async function login(page) {
  await page.goto('/')
  await expect(page.getByText('Welcome back')).toBeVisible()
  await signInLocal(page)
  await expect(page.getByTestId('sidenav-Home')).toBeVisible()
}

test('desktop: login reaches the dashboard with side navigation and no sideways scroll', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/')
  await expect(page.getByText('Welcome back')).toBeVisible()
  expect(await horizontalOverflow(page)).toEqual([])
  // The sign-in card keeps a form width instead of stretching across the window.
  const card = await page.getByText('Welcome back').locator('..').boundingBox()
  expect(card.width).toBeLessThanOrEqual(440)

  await signInLocal(page)
  await expect(page.getByTestId('sidenav-Home')).toBeVisible()
  await expect(visible(page.getByTestId('home-start-now').or(page.getByTestId('home-live-session')))).toBeVisible()
  expect(await horizontalOverflow(page)).toEqual([])

  // Side navigation instead of bottom tabs; content in a centred column.
  for (const tab of ['Home', 'Attendance', 'Quiz', 'Analytics']) {
    await expect(page.getByTestId(`sidenav-${tab}`)).toBeVisible()
  }
  const nav = await page.getByTestId('sidenav-Home').boundingBox()
  expect(nav.x).toBeLessThan(40)
  // 960 px column centred in the 1048 px right of the 232 px nav → ~44 px margin each side.
  const header = await visible(page.getByLabel('Profile')).boundingBox()
  expect(header.x + header.width).toBeLessThanOrEqual(1280 - 40)
  // Dashboard's own header brand (the other "SmartClass" is in the side nav).
  const brands = page.getByText('SmartClass', { exact: true }).filter({ visible: true })
  const xs = await Promise.all((await brands.all()).map(async (b) => (await b.boundingBox()).x))
  expect(Math.max(...xs)).toBeGreaterThanOrEqual(232 + 40)

  expect(errors).toEqual([])
})

test('desktop: every screen and dialog opens without a runtime error', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  await login(page)

  // Home → Profile. A lecturer's password belongs to SPeCTRUM, so there's nothing to change here.
  await visible(page.getByLabel('Profile')).click()
  await expectScreen(page, 'My Profile')
  await expect(page.getByText('Change Password').filter({ visible: true })).toHaveCount(0)
  await visible(page.getByLabel('Back')).click()

  // Attendance list → detail (if the dev DB has any session for this lecturer)
  await page.getByTestId('sidenav-Attendance').click()
  await expectScreen(page, 'Attendance')
  const firstSession = page.getByText(/ Present$/).filter({ visible: true })
  if (await firstSession.count()) {
    await firstSession.first().click()
    await expect(visible(page.getByLabel('Back'))).toBeVisible()
    expect(await horizontalOverflow(page)).toEqual([])
    await visible(page.getByLabel('Back')).click()
  }

  // Quiz (UI mock): list → create → live results → closed results → breakdown
  await page.getByTestId('sidenav-Quiz').click()
  await expectScreen(page, 'Quiz & Poll')
  await visible(page.getByText('Create', { exact: true })).click()
  await expectScreen(page, 'Create Quiz / Poll')
  await visible(page.getByLabel('Back')).click()
  await visible(page.getByText(/fixed-length sprints/)).click()
  await visible(page.getByText('Live Results', { exact: true })).click()
  await expectScreen(page, 'Live Results')
  await visible(page.getByLabel('Back')).click()
  await visible(page.getByText(/SOLID stand for/)).click()
  await visible(page.getByText('View Results', { exact: true })).click()
  await expectScreen(page, 'Quiz Results')
  await visible(page.getByLabel('Back')).click()
  await visible(page.getByText(/SOLID stand for/)).click()
  await visible(page.getByText('Breakdown', { exact: true })).click()
  await expectScreen(page, 'Response Breakdown')
  await visible(page.getByLabel('Back')).click()

  // Analytics
  await page.getByTestId('sidenav-Analytics').click()
  await expectScreen(page, 'Analytics & Reports')

  // Sign out from the side navigation returns to the login page
  await page.getByLabel('Sign out').click()
  // The dialog title also says "Sign Out"; the button comes after it.
  await page.getByText('Sign Out', { exact: true }).filter({ visible: true }).last().click()
  await expect(page.getByText('Welcome back')).toBeVisible()

  expect(errors).toEqual([])
})

test('desktop: an administrator can change their password in a centred dialog', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Welcome back')).toBeVisible()
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await page.getByPlaceholder('your@um.edu.my').fill('admin@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('Admin@1234')
  await page.getByText('Sign In', { exact: true }).click()
  // Administrators land on the admin area (T22), which has the change-password button
  await expect(page.getByTestId('sidenav-Accounts')).toBeVisible()
  expect(await horizontalOverflow(page)).toEqual([])

  await visible(page.getByLabel('Change my password')).click()
  await expect(visible(page.getByPlaceholder('Enter current password'))).toBeVisible()
  const dialog = await visible(page.getByPlaceholder('Enter current password')).boundingBox()
  expect(dialog.width).toBeLessThan(480)   // centred dialog, not a full-width sheet
  await visible(page.getByText('Cancel', { exact: true })).click()
})

test('phone width keeps the bottom tabs', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await signInLocal(page)
  await expect(visible(page.getByTestId('home-start-now').or(page.getByTestId('home-live-session')))).toBeVisible()
  await expect(page.getByTestId('sidenav-Home')).toHaveCount(0)
  await expect(visible(page.getByText('Analytics', { exact: true }))).toBeVisible()   // bottom tab label
  expect(await horizontalOverflow(page)).toEqual([])
})
