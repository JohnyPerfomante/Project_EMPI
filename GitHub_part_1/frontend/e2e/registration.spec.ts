import { expect, test as base } from '@playwright/test'
import { randomUUID } from 'node:crypto'

const test = base.extend<{ createdUsers: number[] }>({
  createdUsers: async ({ request }, use) => {
    const users: number[] = []
    try {
      await use(users)
    } finally {
      if (users.length) {
        const headers = { 'X-EMPI-Request': '1' }
        const login = await request.post('/api/v1/auth/login', {
          headers, data: { email: 'admin@demo.edu.ua', password: process.env.E2E_PASSWORD },
        })
        expect(login.ok()).toBeTruthy()
        for (const id of users) {
          const response = await request.patch(`/api/v1/users/${id}`, { headers, data: { active: false } })
          expect(response.ok()).toBeTruthy()
        }
      }
    }
  },
})

for (const [role, heading] of [['student', /Вітаємо/], ['teacher', 'Панель викладача']] as const) {
  test(`реєстрація та повторний вхід нового користувача ${role}`, async ({ page, createdUsers }) => {
    const email = `registration-${randomUUID()}@example.org`
    const password = `Test-${randomUUID()}`
    if (role === 'student') await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/login')
    await page.getByRole('link', { name: 'Створити обліковий запис' }).click()
    await expect(page).toHaveURL(/\/register$/)
    await page.reload()
    await page.getByLabel('Ім’я та прізвище').fill('QA Реєстрація')
    await page.getByLabel('Електронна пошта').fill(email)
    await page.getByRole('combobox', { name: 'Роль' }).selectOption(role)
    await expect(page.getByRole('combobox', { name: 'Роль' }).locator('option')).toHaveCount(2)
    await page.getByLabel('Пароль', { exact: true }).fill(password)
    await page.getByLabel('Підтвердження пароля', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Показати пароль', exact: true }).click()
    await expect(page.getByLabel('Пароль', { exact: true })).toHaveAttribute('type', 'text')
    const saved = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/register'))
    await page.getByRole('button', { name: 'Зареєструватися', exact: true }).click()
    const response = await saved
    expect(response.status()).toBe(201)
    createdUsers.push((await response.json()).id)
    await expect(page.getByRole('status')).toContainText('Обліковий запис створено.')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByLabel('Електронна пошта')).toHaveValue(email)
    await page.getByLabel('Пароль', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Увійти', exact: true }).click()
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      page.viewportSize()!.width,
    )
    await page.getByRole('button', { name: 'Профіль користувача' }).click()
    await page.getByRole('button', { name: 'Вийти', exact: true }).click()
    await page.getByLabel('Електронна пошта').fill(email)
    await page.getByLabel('Пароль', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Увійти', exact: true }).click()
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  })
}

test('помилки паролів і повторної реєстрації з наявною поштою', async ({ page }) => {
  await page.goto('/register')
  await page.getByLabel('Ім’я та прізвище').fill('QA Реєстрація')
  await page.getByLabel('Електронна пошта').fill('student@demo.edu.ua')
  await page.getByLabel('Пароль', { exact: true }).fill('Registration-test-2026!')
  await page.getByLabel('Підтвердження пароля', { exact: true }).fill('Different-password-2026!')
  await page.getByRole('button', { name: 'Зареєструватися', exact: true }).click()
  await expect(page.getByText('Паролі мають збігатися.', { exact: true })).toBeVisible()
  await page.getByLabel('Підтвердження пароля', { exact: true }).fill('Registration-test-2026!')
  await page.getByRole('button', { name: 'Зареєструватися', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Обліковий запис із цією електронною поштою вже існує.')
  await expect(page).toHaveURL(/\/register$/)
})
