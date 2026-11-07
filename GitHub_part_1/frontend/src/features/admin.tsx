import { useQueryClient } from '@tanstack/react-query'
import { Activity, Plus, Save } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  Badge, Demo, Empty, Field, Header, Notice, Pagination, Panel, QueryState, SearchBox, SelectFilter, Table,
  useAction, useFilters,
} from '../components/ui'
import { api, useApi, usePage } from '../lib/api'
import { date, roleLabels } from '../lib/format'
import type { Audit, Configuration, Group, Role, Specialty, Subject, User } from '../lib/types'

const size = 15
const roles = Object.entries(roleLabels).map(([value, label]) => ({ value, label }))

function UserForm({ record, self, onSaved }: { record: User | null; self: User; onSaved: () => void }) {
  const [name, setName] = useState(record?.full_name ?? '')
  const [email, setEmail] = useState(record?.email ?? '')
  const [role, setRole] = useState<Role>(record?.role ?? 'student')
  const [password, setPassword] = useState('')
  const [active, setActive] = useState(record?.active ?? true)
  const [currentRole, setCurrentRole] = useState(record?.role)
  const action = useAction()
  const queryClient = useQueryClient()
  function save(e: FormEvent) {
    e.preventDefault()
    void action.run(async () => {
      if (!record) {
        await api<User>('/users', 'POST', { full_name: name, email, role, password })
      } else {
        await api<User>(`/users/${record.id}`, 'PATCH', { full_name: name, email, active, ...(password ? { password } : {}) })
        setPassword('')
        await queryClient.invalidateQueries()
        if (role !== currentRole) {
          await api<User>(`/users/${record.id}/role`, 'PATCH', { role })
          setCurrentRole(role)
        }
      }
      await queryClient.invalidateQueries()
      onSaved()
    })
  }
  return <Panel title={record ? `Обліковий запис №${record.id}` : 'Новий користувач'}>
    <form className="panel-body stack" onSubmit={save}>
      <div className="form-grid">
        <Field label="Ім’я та прізвище"><input value={name} required minLength={2} maxLength={160} onChange={e => setName(e.target.value)}/></Field>
        <Field label="Електронна пошта"><input value={email} required type="email" onChange={e => setEmail(e.target.value)}/></Field>
        <Field label="Роль"><select value={role} disabled={record?.id === self.id} onChange={e => setRole(e.target.value as Role)}>{roles.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>
        <Field label={record ? 'Новий пароль' : 'Пароль'} hint={record ? 'Залиште порожнім, щоб зберегти поточний пароль.' : 'Щонайменше 12 символів.'}>
          <input value={password} type="password" autoComplete="new-password" minLength={12} maxLength={128} required={!record} onChange={e => setPassword(e.target.value)}/>
        </Field>
      </div>
      {record && <label className="check"><input type="checkbox" checked={active} disabled={record.id === self.id} onChange={e => setActive(e.target.checked)}/> Активний обліковий запис</label>}
      {action.error && <Notice>{action.error}</Notice>}
      <div><button className="button primary" disabled={action.pending}><Save size={16}/> Зберегти користувача</button></div>
    </form>
  </Panel>
}

export function Users() {
  const self = useOutletContext<User>()
  const filters = useFilters()
  const [editing, setEditing] = useState<User | null | undefined>(undefined)
  const query = usePage<User>('/users', { ...filters.values, limit: size, offset: filters.offset })
  return <>
    <Header title="Користувачі" eyebrow="АДМІНІСТРУВАННЯ" subtitle="Створюйте облікові записи, призначайте ролі та керуйте доступом."
      action={<button className="button primary" onClick={() => setEditing(editing === undefined ? null : undefined)}><Plus size={17}/>{editing === undefined ? 'Новий користувач' : 'Закрити форму'}</button>}/>
    {editing !== undefined && <UserForm record={editing} self={self} key={editing?.id ?? 'new'} onSaved={() => setEditing(undefined)}/>}
    <Panel>
      <div className="filterbar">
        <SearchBox value={filters.values.q} onChange={v => filters.set('q', v)} placeholder="Ім’я або електронна пошта"/>
        <SelectFilter label="Роль" empty="Усі ролі" value={filters.values.role} onChange={v => filters.set('role', v)} options={roles}/>
        <SelectFilter label="Статус" empty="Усі статуси" value={filters.values.active} onChange={v => filters.set('active', v)}
          options={[{ value: 'true', label: 'Активні' }, { value: 'false', label: 'Заблоковані' }]}/>
      </div>
      <QueryState pending={query.isPending} error={query.error}/>
      {query.data && (query.data.items.length ? <Table headings={['Користувач', 'Роль', 'Статус', 'Останній вхід', 'Дія']}>
        {query.data.items.map(item => <tr key={item.id}><td><strong>{item.full_name}</strong>{item.demo && <Demo/>}
          <small>{item.email} · ID {item.id}</small></td><td>{roleLabels[item.role]}</td><td><Badge value={item.active ? 'active' : 'blocked'}/></td>
          <td>{item.last_login_at ? date(item.last_login_at, true) : '—'}</td><td><button className="button tertiary" onClick={() => setEditing(item)}>Редагувати</button></td></tr>)}
      </Table> : <Empty/>)}
      {query.data && <Pagination offset={filters.offset} limit={size} total={query.data.total} change={filters.setOffset}/>}
    </Panel>
  </>
}

const catalogs = [
  { path: '/specialties', title: 'Спеціальності', singular: 'Спеціальність' },
  { path: '/subjects', title: 'Дисципліни', singular: 'Дисципліна' },
  { path: '/student-groups', title: 'Навчальні групи', singular: 'Навчальна група' },
] as const

type CatalogRecord = Specialty | Group | Subject

export function Catalog() {
  const [index, setIndex] = useState(0)
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<CatalogRecord | null | undefined>(undefined)
  const category = catalogs[index]
  const query = usePage<CatalogRecord>(category.path, { limit: size, offset })
  const specialties = usePage<Specialty>('/specialties', { limit: 100 })
  const getSpecialty = (id: number) => specialties.data?.items.find(item => item.id === id)?.code ?? id
  return <>
    <Header title="Довідники" eyebrow="АДМІНІСТРУВАННЯ" subtitle="Навчальні дисципліни, спеціальності та студентські групи."
      action={<button className="button primary" onClick={() => setEditing(editing === undefined ? null : undefined)}><Plus size={17}/>{editing === undefined ? 'Додати запис' : 'Закрити форму'}</button>}/>
    {editing !== undefined && <CatalogForm key={`${category.path}-${editing?.id ?? 'new'}`} index={index}
      record={editing} specialties={specialties.data?.items ?? []} onSaved={() => setEditing(undefined)}/>}
    <Panel>
      <div className="tabs" aria-label="Вид довідника">{catalogs.map((item, i) => <button key={item.path}
        aria-pressed={index === i} className={index === i ? 'selected' : ''} onClick={() => { setIndex(i); setOffset(0); setEditing(undefined) }}>{item.title}</button>)}</div>
      <QueryState pending={query.isPending} error={query.error ?? specialties.error}/>
      {query.data && (query.data.items.length ? <Table headings={['Назва', index === 0 ? 'Код' : 'Спеціальність', 'Дія']}>
        {query.data.items.map(item => <tr key={item.id}><td><strong>{item.name}</strong>
          {'academic_year' in item && <small>{item.academic_year}</small>}{'description' in item && <small>{item.description}</small>}</td>
          <td>{'code' in item ? item.code : getSpecialty(item.specialty_id)}</td><td><button className="button tertiary" onClick={() => setEditing(item)}>Редагувати</button></td></tr>)}
      </Table> : <Empty/>)}
      {query.data && <Pagination offset={offset} limit={size} total={query.data.total} change={setOffset}/>}
    </Panel>
  </>
}

function CatalogForm({ index, record, specialties, onSaved }: {
  index: number; record: CatalogRecord | null; specialties: Specialty[]; onSaved: () => void
}) {
  const category = catalogs[index]
  const [name, setName] = useState(record?.name ?? '')
  const [code, setCode] = useState(record && 'code' in record ? record.code : '')
  const [specialty, setSpecialty] = useState(record && 'specialty_id' in record ? String(record.specialty_id) : '')
  const [description, setDescription] = useState(record && 'description' in record ? record.description : '')
  const [year, setYear] = useState(record && 'academic_year' in record ? record.academic_year : '')
  const queryClient = useQueryClient()
  const action = useAction()
  return <Panel title={category.singular}><form className="panel-body stack" onSubmit={e => {
    e.preventDefault()
    const body = index === 0 ? { name, code } : index === 1
      ? { name, specialty_id: Number(specialty), description } : { name, specialty_id: Number(specialty), academic_year: year }
    void action.run(async () => {
      await api<CatalogRecord>(record ? `${category.path}/${record.id}` : category.path, record ? 'PUT' : 'POST', body)
      await queryClient.invalidateQueries()
      onSaved()
    })
  }}>
    <div className="form-grid">
      <Field label="Назва"><input required minLength={index === 2 ? 1 : 2} maxLength={index === 2 ? 80 : 160} value={name} onChange={e => setName(e.target.value)}/></Field>
      {index === 0 ? <Field label="Код"><input required minLength={2} maxLength={20} value={code} onChange={e => setCode(e.target.value)}/></Field>
        : <Field label="Спеціальність"><select required value={specialty} onChange={e => setSpecialty(e.target.value)}>
          <option value="">Оберіть спеціальність</option>{specialties.map(item => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}
        </select></Field>}
      {index === 2 && <Field label="Навчальний рік"><input required pattern="[0-9]{4}/[0-9]{4}" placeholder="2026/2027" value={year} onChange={e => setYear(e.target.value)}/></Field>}
    </div>
    {index === 1 && <Field label="Опис"><textarea rows={3} maxLength={3000} value={description} onChange={e => setDescription(e.target.value)}/></Field>}
    {action.error && <Notice>{action.error}</Notice>}
    <div><button className="button primary" disabled={action.pending}><Save size={16}/> Зберегти запис</button></div>
  </form></Panel>
}

type NumericConfiguration = Omit<Configuration, 'detect_negation' | 'calibrated' | 'model_name' | 'model_revision' | 'provider'>
const configurationFields: { key: keyof NumericConfiguration; label: string; min: number; max: number; step: number }[] = [
  { key: 'high_threshold', label: 'Високий поріг', min: .05, max: 1, step: .01 },
  { key: 'low_threshold', label: 'Низький поріг', min: 0, max: .95, step: .01 },
  { key: 'semantic_weight', label: 'Вага семантики', min: .1, max: 1, step: .01 },
  { key: 'lexical_weight', label: 'Вага лексики', min: 0, max: 1, step: .01 },
  { key: 'concept_weight', label: 'Вага понять', min: 0, max: 1, step: .01 },
  { key: 'min_answer_length', label: 'Мінімум символів', min: 1, max: 300, step: 1 },
  { key: 'max_answer_length', label: 'Максимум символів', min: 50, max: 4000, step: 1 },
]

function SettingsForm({ data }: { data: Configuration }) {
  const [values, setValues] = useState(() => Object.fromEntries(configurationFields.map(({ key }) => [key, String(data[key])])))
  const [negation, setNegation] = useState(data.detect_negation)
  const action = useAction()
  const queryClient = useQueryClient()
  return <Panel title="Параметри класифікації" subtitle="Пороги та ваги задаються від 0 до 1. Сума ваг має дорівнювати 1.">
    <form className="panel-body stack" onSubmit={e => {
      e.preventDefault()
      void action.run(async () => {
        await api<Configuration>('/settings', 'PATCH', {
          ...Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value)])), detect_negation: negation,
        })
        await queryClient.invalidateQueries()
      }, 'Параметри збережено для наступних аналізів.')
    }}>
      {!data.calibrated && <Notice>Поточні пороги попередні. Калібрування на перевіреному корпусі ще не зафіксовано.</Notice>}
      <div className="form-grid">{configurationFields.map(({ key, label, min, max, step }) => <Field key={key} label={label}>
        <input type="number" min={min} max={max} step={step} required value={values[key]}
          onChange={e => setValues({ ...values, [key]: e.target.value })}/>
      </Field>)}</div>
      <label className="check"><input type="checkbox" checked={negation} onChange={e => setNegation(e.target.checked)}/> Позначати відмінні заперечення</label>
      {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
      <div><button className="button primary" disabled={action.pending}><Save size={16}/> Зберегти параметри</button></div>
    </form>
  </Panel>
}

export function Settings() {
  const config = useApi<Configuration>('/settings')
  const worker = useApi<{ state: string; detail: string; updated_at: string | null }>('/health/worker', true, 15000)
  return <>
    <Header title="Налаштування NLP" eyebrow="АДМІНІСТРУВАННЯ" subtitle="Стан локального аналізу, пороги й правила класифікації."/>
    <Panel title="Стан воркера" action={<Activity size={20} className="muted"/>}><div className="panel-body stack">
      <QueryState pending={worker.isPending || config.isPending} error={worker.error ?? config.error}/>
      {worker.data && <><Badge value={worker.data.state === 'ready' ? 'active' : 'queued'}
        label={({ ready: 'Готовий', starting: 'Запускається', offline: 'Офлайн', degraded: 'Помилка завантаження' })[worker.data.state] ?? worker.data.state}/>
        <p>{worker.data.detail}</p>{worker.data.updated_at && <small>Сигнал · {date(worker.data.updated_at, true)}</small>}</>}
      {config.data && <dl className="description"><div><dt>Модель</dt><dd>{config.data.model_name}</dd></div>
        <div><dt>Версія</dt><dd className="preserve">{config.data.model_revision || 'Визначається воркером'}</dd></div></dl>}
    </div></Panel>
    {config.data && <SettingsForm data={config.data}/>}
  </>
}

export function AuditLog() {
  const filters = useFilters()
  const query = usePage<Audit>('/audit-log', { ...filters.values, offset: filters.offset, limit: size })
  const actions: Record<string, string> = {
    login: 'Вхід', logout: 'Вихід', register: 'Реєстрація', create: 'Створення', update: 'Оновлення', role_change: 'Зміна ролі',
    submit: 'Надсилання', status_change: 'Зміна статусу', review: 'Рішення викладача', propose: 'Пропозиція',
    set_teacher_access: 'Доступ викладача', set_membership: 'Зарахування', archive: 'Архівування',
    analyze: 'Запуск аналізу', reanalyze: 'Повторний аналіз',
  }
  return <>
    <Header title="Журнал аудиту" eyebrow="АДМІНІСТРУВАННЯ" subtitle="Історія важливих операцій із навчальними даними та доступом."/>
    <Panel>
      <div className="filterbar"><SearchBox value={filters.values.q} onChange={v => filters.set('q', v)} placeholder="Код дії або тип об’єкта"/></div>
      <QueryState pending={query.isPending} error={query.error}/>
      {query.data && (query.data.items.length ? <Table headings={['Дата', 'Дія', 'Користувач', 'Об’єкт', 'Деталі']}>
        {query.data.items.map(item => <tr key={item.id}><td>{date(item.created_at, true)}</td><td>{actions[item.action] ?? item.action}</td>
          <td>{item.user_id ? `№${item.user_id}` : 'Система'}</td><td><code>{item.entity_type}</code>{item.entity_id ? ` №${item.entity_id}` : ''}</td>
          <td>{Object.keys(item.details).length ? <details className="technical"><summary>Переглянути</summary><pre>{JSON.stringify(item.details, null, 2)}</pre></details> : '—'}</td></tr>)}
      </Table> : <Empty/>)}
      {query.data && <Pagination offset={filters.offset} limit={size} total={query.data.total} change={filters.setOffset}/>}
    </Panel>
  </>
}
