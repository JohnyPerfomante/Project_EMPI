import { expect, test, type Page } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'

const secret = process.env.E2E_PASSWORD
if (!secret) throw new Error('Set E2E_PASSWORD to the demo seed password.')

async function signIn(page: Page, account: string) {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Вхід до системи' })).toBeVisible()
  await page.getByLabel('Електронна пошта').fill(`${account}@demo.edu.ua`)
  await page.getByLabel('Пароль', { exact: true }).fill(secret!)
  await page.getByRole('button', { name: 'Увійти', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Профіль користувача' })).toBeVisible()
}

async function screenshot(page: Page, name: string) {
  const destination = process.env.EMPI_SCREENSHOTS
  if (!destination) return
  await mkdir(destination, { recursive: true })
  await page.screenshot({ path: join(destination, name + '.png'), animations: 'disabled' })
}

test('викладач, студент і повторне використання затвердженого формулювання', async ({ page, browser }) => {
  await signIn(page, 'teacher')
  await expect(page.getByRole('heading', { name: 'Панель викладача' })).toBeVisible()
  await expect(page.getByText('Динаміка відповідей', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Створити питання' }).click()
  await page.getByRole('combobox', { name: 'Курс', exact: true }).selectOption({ label: 'Операційні системи · Операційні системи' })
  const question = `Як операційна система керує ресурсами? QA ${Date.now()}`
  const reference = 'Операційна система керує апаратними ресурсами і запускає прикладні програми.'
  const answer = 'ОС управляє обладнанням комп’ютера та дозволяє виконувати застосунки.'
  await page.getByLabel('Текст питання').fill(question)
  await page.getByLabel('Текст еталона').fill(reference)
  await page.getByRole('button', { name: 'Додати поняття' }).click()
  await page.getByLabel('Поняття', { exact: true }).fill('апаратні ресурси')
  await page.getByLabel('Синоніми через кому').fill('обладнання')
  await page.getByRole('button', { name: 'Зберегти питання' }).click()
  await expect(page.getByRole('heading', { name: 'Картка питання' })).toBeVisible()
  await page.getByRole('button', { name: 'Опублікувати', exact: true }).click()
  await expect(page.getByText('Опубліковано', { exact: true })).toBeVisible()
  const questionUrl = new URL(page.url()).pathname

  const studentContext = await browser.newContext()
  const student = await studentContext.newPage()
  try {
    await signIn(student, 'student')
    await student.getByRole('link', { name: 'Завдання', exact: true }).click()
    await student.getByRole('searchbox', { name: 'Пошук' }).fill(question)
    await student.getByRole('link', { name: question }).click()
    await expect(student).toHaveURL(new RegExp(questionUrl + '$'))
    await expect(student.getByText(reference)).toHaveCount(0)
    await student.getByLabel('Текст відповіді').fill(answer)
    await student.getByRole('button', { name: 'Надіслати відповідь' }).click()
    await expect(student.getByText('Відповідь надіслано й збережено.')).toBeVisible()
    await expect(student.getByRole('heading', { name: 'Результат відповіді' })).toBeVisible()
    const submissionUrl = new URL(student.url()).pathname

    await page.goto(submissionUrl)
    await expect(page.getByText(reference, { exact: true })).toBeVisible({ timeout: 45_000 })
    await expect(page.getByRole('heading', { name: 'Рішення викладача' })).toBeVisible()
    await page.getByLabel('Коментар').fill('Відповідь зараховано.')
    await page.getByLabel('Зберегти як затверджену варіацію').check()
    await page.getByRole('button', { name: 'Зберегти рішення' }).click()
    await expect(page.getByText('Рішення викладача збережено.')).toBeVisible()
    await expect(student.getByText('Відповідь зараховано.')).toBeVisible()

    await student.goto(questionUrl)
    await student.getByLabel('Текст відповіді').fill(answer)
    await student.getByRole('button', { name: 'Надіслати відповідь' }).click()
    await expect(student.getByText('Відповідь надіслано й збережено.')).toBeVisible()
    await page.goto(new URL(student.url()).pathname)
    await expect(page.getByRole('heading', { name: 'Найближча затверджена варіація' })).toBeVisible({ timeout: 45_000 })
    await screenshot(page, 'review')
    await page.getByRole('link', { name: 'База варіацій', exact: true }).click()
    await page.getByRole('button', { name: 'Затверджені' }).click()
    await page.getByRole('searchbox').fill(question)
    await expect(page.getByRole('link', { name: answer })).toBeVisible()
  } finally {
    await studentContext.close()
  }
})

test('роль адміністратора, стан моделі та завершення сесії', async ({ page }) => {
  await signIn(page, 'admin')
  await expect(page.getByRole('heading', { name: 'Панель адміністратора' })).toBeVisible()
  await page.getByRole('link', { name: 'Користувачі', exact: true }).click()
  await page.getByRole('combobox', { name: 'Роль' }).selectOption('student')
  await expect(page.getByText('student@demo.edu.ua', { exact: false })).toBeVisible()
  await expect(page.getByText('teacher@demo.edu.ua', { exact: false })).toHaveCount(0)
  await page.getByRole('link', { name: 'Налаштування NLP' }).click()
  await expect(page.getByRole('heading', { name: 'Параметри класифікації' })).toBeVisible()
  await expect(page.getByText('Готовий', { exact: true })).toBeVisible({ timeout: 40_000 })
  await page.getByRole('button', { name: 'Профіль користувача' }).click()
  await page.getByRole('button', { name: 'Вийти', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Вхід до системи' })).toBeVisible()
  await screenshot(page, 'login')
})

test('мобільна навігація студента та захист адміністративних сторінок', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await signIn(page, 'student2')
  await expect(page.getByRole('heading', { name: /Вітаємо/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /Виконані завдання/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /Очікують перевірки/ })).toBeVisible()
  await screenshot(page, 'student-mobile')
  await page.getByRole('button', { name: 'Відкрити меню' }).click()
  await expect(page.getByRole('link', { name: 'Мої відповіді', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Мої відповіді', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Мої відповіді' })).toBeVisible()
  await page.goto('/admin/users')
  await expect(page.getByText('Сторінка відсутня або недоступна.')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
})

test('огляд викладача з даними PostgreSQL', async ({ page }) => {
  await signIn(page, 'teacher')
  await expect(page.getByRole('heading', { name: 'Останні відповіді' })).toBeVisible()
  await expect(page.getByRole('table').first().locator('tbody tr').first()).toBeVisible()
  await expect(page.locator('.recharts-bar-rectangle').first()).toBeAttached()
  await screenshot(page, 'dashboard')
})
