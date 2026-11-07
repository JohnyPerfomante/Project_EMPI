import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { Field, Notice, useAction } from '../components/ui'
import { api } from '../lib/api'
import { registrationSchema, type RegistrationValues } from '../lib/registration'
import type { User } from '../lib/types'
import { AuthLayout, PasswordField } from './auth'

export function Register() {
  const navigate = useNavigate()
  const action = useAction()
  const { register, handleSubmit, formState: { errors } } = useForm<RegistrationValues>({
    resolver: zodResolver(registrationSchema),
    defaultValues: { full_name: '', email: '', role: 'student', password: '', password_confirmation: '' },
  })
  return <AuthLayout registration>
    <h2>Реєстрація</h2>
    <p>Створіть особистий обліковий запис для навчання або викладання.</p>
    <form className="stack" noValidate onSubmit={handleSubmit(data => action.run(async () => {
      const user = await api<User>('/auth/register', 'POST', data)
      navigate('/login', { replace: true, state: { registeredEmail: user.email } })
    }))}>
      {action.error && <Notice>{action.error}</Notice>}
      <Field label="Ім’я та прізвище" error={errors.full_name?.message}>
        <input autoComplete="name" maxLength={160} aria-invalid={Boolean(errors.full_name)} {...register('full_name')}/>
      </Field>
      <Field label="Електронна пошта" error={errors.email?.message}>
        <input type="email" autoComplete="email" placeholder="name@university.edu.ua"
          aria-invalid={Boolean(errors.email)} {...register('email')}/>
      </Field>
      <Field label="Роль" error={errors.role?.message}>
        <select aria-label="Роль" {...register('role')}>
          <option value="student">Студент</option>
          <option value="teacher">Викладач</option>
        </select>
      </Field>
      <PasswordField label="Пароль" registration={register('password')} autoComplete="new-password"
        hint="Від 12 до 128 символів." error={errors.password?.message}/>
      <PasswordField label="Підтвердження пароля" registration={register('password_confirmation')}
        autoComplete="new-password" error={errors.password_confirmation?.message}/>
      <button className="button primary login-submit" disabled={action.pending}>
        {action.pending ? 'Створення…' : 'Зареєструватися'}<ArrowRight size={18}/>
      </button>
    </form>
    <div className="auth-note">Доступ до навчальних курсів надає адміністратор.</div>
    <div className="auth-switch">Уже маєте обліковий запис? <Link to="/login">Увійти</Link></div>
  </AuthLayout>
}
