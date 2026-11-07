import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, BookOpenCheck, Eye, EyeOff, GraduationCap, Layers, ShieldCheck } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'
import { Link, useLocation } from 'react-router-dom'
import { z } from 'zod'
import { Field, Notice, useAction } from '../components/ui'
import { api } from '../lib/api'
import type { User } from '../lib/types'

const credentials = z.object({
  email: z.email('Введіть коректну електронну пошту.'),
  password: z.string().min(1, 'Введіть пароль.').max(128),
  remember: z.boolean(),
})

export function Brand() {
  return <div className="brand"><div className="brand-mark"><GraduationCap size={24}/></div>
    <div><strong>Освітній процес</strong><span>Університетська система</span></div></div>
}

export function AuthLayout({ children, registration = false }: { children: ReactNode; registration?: boolean }) {
  return <main className="login">
    <section className="login-story">
      <Brand/>
      <div className="login-copy">
        <div className="eyebrow">НАВЧАЛЬНИЙ КАБІНЕТ</div>
        <h1>Перевірка відкритих відповідей</h1>
        <p>Створюйте завдання, надсилайте відповіді й переглядайте результати перевірки в одному кабінеті.</p>
        <div className="login-features">
          <span><Layers size={18}/> Банк питань та еталонів</span>
          <span><BookOpenCheck size={18}/> Перевірка викладачем</span>
          <span><ShieldCheck size={18}/> Доступ за навчальними ролями</span>
        </div>
      </div>
      <small>Національний транспортний університет</small>
    </section>
    <section className={`login-form-side ${registration ? 'registration-side' : ''}`}>
      <div className={`login-card ${registration ? 'registration-card' : ''}`}>
        <div className="login-mobile-brand"><Brand/></div>
        <div className="eyebrow">ОСОБИСТИЙ КАБІНЕТ</div>
        {children}
      </div>
      <footer>Освітній процес <span>·</span> Версія 1.0</footer>
    </section>
  </main>
}

export function PasswordField({ label, registration, autoComplete, hint, error }: {
  label: string; registration: UseFormRegisterReturn; autoComplete: 'current-password' | 'new-password'
  hint?: string; error?: string
}) {
  const [visible, setVisible] = useState(false)
  const target = label === 'Пароль' ? 'пароль' : 'підтвердження пароля'
  return <Field label={label} hint={hint} error={error}><span className="password-input">
    <input type={visible ? 'text' : 'password'} aria-label={label} aria-invalid={Boolean(error)}
      autoComplete={autoComplete} {...registration}/>
    <button type="button" className="icon-button" aria-label={`${visible ? 'Приховати' : 'Показати'} ${target}`}
      onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18}/> : <Eye size={18}/>}</button>
  </span></Field>
}

export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const location = useLocation()
  const state = location.state as { registeredEmail?: string } | null
  const action = useAction()
  const { register, handleSubmit, formState: { errors } } = useForm<z.infer<typeof credentials>>({
    resolver: zodResolver(credentials), defaultValues: { email: state?.registeredEmail ?? '', password: '', remember: false },
  })
  return <AuthLayout>
    <h2>Вхід до системи</h2>
    <p>Увійдіть за допомогою університетського облікового запису.</p>
    <form className="stack" onSubmit={handleSubmit(data => action.run(async () => {
      onLogin(await api<User>('/auth/login', 'POST', data))
    }))}>
      {state?.registeredEmail && <Notice success>Обліковий запис створено. Увійдіть із вашою поштою та паролем.</Notice>}
      {action.error && <Notice>{action.error}</Notice>}
      <Field label="Електронна пошта" error={errors.email?.message}><input type="email" placeholder="name@university.edu.ua" autoComplete="username" {...register('email')}/></Field>
      <PasswordField label="Пароль" registration={register('password')} autoComplete="current-password" error={errors.password?.message}/>
      <label className="check"><input type="checkbox" {...register('remember')}/> Запам’ятати сесію</label>
      <button className="button primary login-submit" disabled={action.pending}>{action.pending ? 'Вхід…' : 'Увійти'}<ArrowRight size={18}/></button>
    </form>
    <div className="auth-switch">Новий користувач? <Link to="/register">Створити обліковий запис</Link></div>
  </AuthLayout>
}
