// Smoke: the lecturer login page renders in a desktop browser.
const { test, expect } = require('@playwright/test')

test('login page renders', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/')

  await expect(page.getByText('Welcome back')).toBeVisible()
  await expect(page.getByText('Sign in with your university credentials')).toBeVisible()
  await expect(page.getByPlaceholder('your@um.edu.my')).toBeVisible()
  await expect(page.getByText('Sign In', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})
