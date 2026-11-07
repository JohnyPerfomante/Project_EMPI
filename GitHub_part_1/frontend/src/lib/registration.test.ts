import { describe, expect, it } from 'vitest'
import { registrationSchema } from './registration'

const account = {
  full_name: '  Олена Коваль  ', email: 'student@example.org', role: 'student',
  password: 'Registration-example-2026!', password_confirmation: 'Registration-example-2026!',
}

describe('registration validation', () => {
  it.each(['student', 'teacher'])('accepts a %s account and trims the name', role => {
    const result = registrationSchema.parse({ ...account, role })
    expect(result.full_name).toBe('Олена Коваль')
    expect(result.role).toBe(role)
  })

  it('attaches a mismatch error to the confirmation field', () => {
    const result = registrationSchema.safeParse({ ...account, password_confirmation: 'Different-password-2026!' })
    expect(result.success).toBe(false)
    if (!result.success) expect(result.error.issues[0].path).toEqual(['password_confirmation'])
  })

  it.each([
    { role: 'admin' }, { email: 'invalid-email' }, { full_name: ' ' },
    { password: 'short', password_confirmation: 'short' },
  ])('rejects invalid registration data %j', values => {
    expect(registrationSchema.safeParse({ ...account, ...values }).success).toBe(false)
  })
})
