// T13: the lecturer sign-in in the browser. SPeCTRUM (Moodle) username + password by
// default; administrators switch to the browser-only SmartClass email sign-in. The
// wrong-role check needs the local Moodle (student1).
const { test, expect } = require('@playwright/test')

test('SPeCTRUM sign-in is the default and asks for a username', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Welcome back')).toBeVisible()
  await expect(page.getByText('SPeCTRUM username', { exact: true })).toBeVisible()
  await expect(page.getByPlaceholder('Your SPeCTRUM username')).toHaveValue('')
  await expect(page.getByPlaceholder('Enter password')).toHaveValue('')

  // Empty form: no request, a hint instead
  await page.getByText('Sign In', { exact: true }).click()
  await expect(page.getByText('Enter your SPeCTRUM username and password.')).toBeVisible()
})

test('administrator sign-in: wrong password, student account refused, then back to SPeCTRUM', async ({ page }) => {
  await page.goto('/')
  await page.getByText('Administrator sign-in', { exact: true }).click()
  await expect(page.getByText('Email address', { exact: true })).toBeVisible()

  await page.getByPlaceholder('your@um.edu.my').fill('devlecturer@um.edu.my')
  await page.getByPlaceholder('Enter password').fill('not-the-password')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(page.getByText('Wrong email or password.')).toBeVisible()
  // A wrong password must not be treated as an expired session
  await expect(page.getByText('Session expired. Please log in again.')).toHaveCount(0)

  await page.getByText('Lecturer? Sign in with SPeCTRUM', { exact: true }).click()
  await expect(page.getByPlaceholder('Your SPeCTRUM username')).toBeVisible()

  // A Moodle student: right password, wrong app
  await page.getByPlaceholder('Your SPeCTRUM username').fill('student1')
  await page.getByPlaceholder('Enter password').fill('Student123!')
  await page.getByText('Sign In', { exact: true }).click()
  await expect(page.getByText('This app is for lecturers. Students use the SmartClass Student app.')).toBeVisible()
  await expect(page.getByTestId('sidenav-Home')).toHaveCount(0)
})
