import { z } from 'zod'

export const registrationSchema = z.object({
  full_name: z.string().trim().min(2, 'Введіть ім’я та прізвище.').max(160, 'Максимум 160 символів.')
    .regex(/^[^\u0000-\u001f\u007f]+$/, 'Введіть ім’я без керівних символів.'),
  email: z.string().trim().pipe(z.email('Введіть коректну електронну пошту.')),
  role: z.enum(['student', 'teacher']),
  password: z.string().min(12, 'Пароль має містити щонайменше 12 символів.').max(128, 'Максимум 128 символів.'),
  password_confirmation: z.string().min(1, 'Повторіть пароль.').max(128, 'Максимум 128 символів.'),
}).refine(data => data.password === data.password_confirmation, {
  path: ['password_confirmation'], message: 'Паролі мають збігатися.',
})

export type RegistrationValues = z.infer<typeof registrationSchema>
