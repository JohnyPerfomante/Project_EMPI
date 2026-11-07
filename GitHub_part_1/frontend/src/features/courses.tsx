import { useQueryClient } from '@tanstack/react-query'
import { ArrowRight, BookOpen, Plus, Save, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import {
  Badge, Demo, Empty, Field, Header, Notice, Pagination, Panel, QueryState, SearchBox, SelectFilter, Table,
  useAction, useFilters,
} from '../components/ui'
import { api, useApi, usePage } from '../lib/api'
import { labels } from '../lib/format'
import type { Course, Group, Membership, Subject, TeacherAccess, User, Visibility } from '../lib/types'

const size = 12

export function Courses() {
  const user = useOutletContext<User>()
  const staff = user.role !== 'student'
  const filters = useFilters()
  const [creating, setCreating] = useState(false)
  const courses = usePage<Course>('/courses', { ...filters.values, offset: filters.offset, limit: size })
  const subjects = usePage<Subject>('/subjects', { limit: 100 })
  return <>
    <Header title="Дисципліни" eyebrow="НАВЧАЛЬНИЙ ПРОЦЕС" subtitle={staff ? 'Курси, групи та доступ до навчальних матеріалів.' : 'Дисципліни, до яких ви маєте доступ.'}
      action={staff && <button className="button primary" onClick={() => setCreating(!creating)}><Plus size={17}/>{creating ? 'Закрити форму' : 'Новий курс'}</button>}/>
    {creating && <CourseForm subjects={subjects.data?.items ?? []} onSaved={() => setCreating(false)}/>}
    <Panel>
      <div className="filterbar">
        <SearchBox value={filters.values.q} onChange={v => filters.set('q', v)} placeholder="Пошук за назвою"/>
        <SelectFilter label="Дисципліна" empty="Усі дисципліни" value={filters.values.subject_id} onChange={v => filters.set('subject_id', v)}
          options={subjects.data?.items.map(item => ({ value: item.id, label: item.name })) ?? []}/>
        {staff && <SelectFilter label="Активність" empty="Усі курси" value={filters.values.active} onChange={v => filters.set('active', v)}
          options={[{ value: 'true', label: 'Активні' }, { value: 'false', label: 'Неактивні' }]}/>}
      </div>
      <QueryState pending={courses.isPending} error={courses.error}/>
      {courses.data && (courses.data.items.length ? <Table headings={['Курс', 'Дисципліна', 'Спеціальність', 'Навчальний рік', 'Статус']}>
        {courses.data.items.map(item => <tr key={item.id}>
          <td><Link className="row-link" to={`/courses/${item.id}`}><BookOpen size={16}/>{item.name}</Link>{item.demo && <Demo/>}</td>
          <td>{item.subject_name}</td><td>{item.specialty}</td><td>{item.academic_year}</td>
          <td><Badge value={item.active ? 'active' : 'archived'} label={item.active ? 'Активний' : 'Неактивний'}/></td>
        </tr>)}
      </Table> : <Empty/>)}
      {courses.data && <Pagination offset={filters.offset} limit={size} total={courses.data.total} change={filters.setOffset}/>}
    </Panel>
  </>
}

function CourseForm({ course, subjects = [], onSaved }: { course?: Course; subjects?: Subject[]; onSaved?: () => void }) {
  const [name, setName] = useState(course?.name ?? '')
  const [subject, setSubject] = useState(String(course?.subject_id ?? ''))
  const [year, setYear] = useState(course?.academic_year ?? '')
  const [description, setDescription] = useState(course?.description ?? '')
  const [visibility, setVisibility] = useState<Visibility>(course?.result_visibility ?? 'automatic')
  const [active, setActive] = useState(course?.active ?? true)
  const [high, setHigh] = useState(String(course?.analysis_overrides.high_threshold ?? ''))
  const [low, setLow] = useState(String(course?.analysis_overrides.low_threshold ?? ''))
  const action = useAction()
  const queryClient = useQueryClient()
  function save(e: FormEvent) {
    e.preventDefault()
    void action.run(async () => {
      const base = { name, academic_year: year, description, result_visibility: visibility }
      const analysis_overrides = { ...(high ? { high_threshold: Number(high) } : {}), ...(low ? { low_threshold: Number(low) } : {}) }
      await api<Course>(course ? `/courses/${course.id}` : '/courses', course ? 'PATCH' : 'POST', course
        ? { ...base, active, analysis_overrides } : { ...base, subject_id: Number(subject) })
      await queryClient.invalidateQueries()
      onSaved?.()
    }, 'Курс збережено.')
  }
  return <Panel title={course ? 'Параметри курсу' : 'Новий курс'}>
    <form className="panel-body stack" onSubmit={save}>
      <div className="form-grid">
        <Field label="Назва курсу"><input value={name} required minLength={2} maxLength={160} onChange={e => setName(e.target.value)}/></Field>
        {!course && <Field label="Дисципліна"><select required value={subject} onChange={e => setSubject(e.target.value)}><option value="">Оберіть дисципліну</option>{subjects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>}
        <Field label="Навчальний рік"><input value={year} placeholder="2026/2027" pattern="[0-9]{4}/[0-9]{4}" required onChange={e => setYear(e.target.value)}/></Field>
        <Field label="Показ результату студенту"><select value={visibility} onChange={e => setVisibility(e.target.value as Visibility)}>
          {(['automatic', 'reviewed', 'hidden'] as const).map(v => <option key={v} value={v}>{labels[v]}</option>)}
        </select></Field>
      </div>
      <Field label="Опис"><textarea rows={3} value={description} maxLength={3000} onChange={e => setDescription(e.target.value)}/></Field>
      {course && <><div className="form-grid">
        <Field label="Високий поріг курсу" hint="Порожнє поле успадковує системне значення."><input type="number" min="0.05" max="1" step="0.01" value={high} onChange={e => setHigh(e.target.value)}/></Field>
        <Field label="Низький поріг курсу"><input type="number" min="0" max="0.95" step="0.01" value={low} onChange={e => setLow(e.target.value)}/></Field>
      </div><label className="check"><input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)}/> Активний курс</label></>}
      {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
      <div><button className="button primary" disabled={action.pending}><Save size={16}/> Зберегти курс</button></div>
    </form>
  </Panel>
}

function CourseAccess({ course, admin }: { course: Course; admin: boolean }) {
  const [memberOffset, setMemberOffset] = useState(0)
  const [teacherOffset, setTeacherOffset] = useState(0)
  const prefix = `/courses/${course.id}`
  const memberships = usePage<Membership>(`${prefix}/memberships`, { offset: memberOffset, limit: size })
  const groups = usePage<Group>(`${prefix}/groups`, { limit: 100 })
  const teachers = usePage<TeacherAccess>(`${prefix}/teachers`, { offset: teacherOffset, limit: size }, admin)
  const adminStudents = usePage<User>('/users', { limit: 100, role: 'student', active: true }, admin)
  const adminTeachers = usePage<User>('/users', { limit: 100, role: 'teacher', active: true }, admin)
  const [studentId, setStudentId] = useState('')
  const [group, setGroup] = useState('')
  const [teacherId, setTeacherId] = useState('')
  const action = useAction()
  const teacherAction = useAction()
  const queryClient = useQueryClient()
  const setMembership = (student_id: number, group_id: number, active: boolean) => void action.run(async () => {
    await api<Membership>(`${prefix}/memberships`, 'PUT', { student_id, group_id, active })
    await queryClient.invalidateQueries()
  }, 'Доступ студента оновлено.')
  const setTeacher = (teacher_id: number, active: boolean) => void teacherAction.run(async () => {
    await api<TeacherAccess>(`${prefix}/teachers`, 'PUT', { teacher_id, active })
    await queryClient.invalidateQueries()
  }, 'Доступ викладача оновлено.')
  return <>
    <Panel title="Студенти й навчальні групи" subtitle="Зараховуйте студентів до групи цього курсу та керуйте доступом">
      <form className="panel-body inline-form" onSubmit={e => { e.preventDefault(); setMembership(Number(studentId), Number(group), true) }}>
        {admin ? <Field label="Студент"><select required value={studentId} onChange={e => setStudentId(e.target.value)}><option value="">Оберіть студента</option>{adminStudents.data?.items.map(item => <option value={item.id} key={item.id}>{item.full_name}</option>)}</select></Field> : <Field label="Ідентифікатор студента" hint="ID надає адміністратор."><input required type="number" min="1" value={studentId} onChange={e => setStudentId(e.target.value)}/></Field>}
        <Field label="Група"><select required value={group} onChange={e => setGroup(e.target.value)}><option value="">Оберіть групу</option>{groups.data?.items.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></Field>
        <button className="button secondary" disabled={action.pending}><UserPlus size={16}/> Зарахувати</button>
      </form>
      {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
      <QueryState pending={memberships.isPending || groups.isPending} error={memberships.error ?? groups.error ?? adminStudents.error}/>
      {memberships.data && (memberships.data.items.length ? <Table headings={['Студент', 'Група', 'Доступ', 'Дія']}>{memberships.data.items.map(item => <tr key={item.id}>
        <td>{item.full_name}<small>ID {item.student_id}</small></td><td>{item.group_name}</td><td><Badge value={item.active ? 'active' : 'blocked'}/></td>
        <td><button className="button tertiary" disabled={action.pending} onClick={() => setMembership(item.student_id, item.group_id, !item.active)}>{item.active ? 'Відкликати' : 'Відновити'}</button></td>
      </tr>)}</Table> : <Empty text="У курсі ще немає студентів."/>)}
      {memberships.data && <Pagination offset={memberOffset} limit={size} total={memberships.data.total} change={setMemberOffset}/>}
    </Panel>
    {admin && <Panel title="Викладачі курсу">
      <form className="panel-body inline-form" onSubmit={e => { e.preventDefault(); setTeacher(Number(teacherId), true) }}>
        <Field label="Викладач"><select required value={teacherId} onChange={e => setTeacherId(e.target.value)}><option value="">Оберіть викладача</option>{adminTeachers.data?.items.map(item => <option value={item.id} key={item.id}>{item.full_name}</option>)}</select></Field>
        <button className="button secondary" disabled={teacherAction.pending}><UserPlus size={16}/> Надати доступ</button>
      </form>
      {teacherAction.error && <Notice>{teacherAction.error}</Notice>}{teacherAction.success && <Notice success>{teacherAction.success}</Notice>}
      <QueryState pending={teachers.isPending} error={teachers.error ?? adminTeachers.error}/>
      {teachers.data && (teachers.data.items.length ? <Table headings={['Викладач', 'Доступ', 'Дія']}>{teachers.data.items.map(item => <tr key={item.id}>
        <td>{item.full_name}</td><td><Badge value={item.active ? 'active' : 'blocked'}/></td>
        <td><button className="button tertiary" disabled={teacherAction.pending} onClick={() => setTeacher(item.teacher_id, !item.active)}>{item.active ? 'Відкликати' : 'Відновити'}</button></td>
      </tr>)}</Table> : <Empty text="У курсі ще немає викладачів."/>)}
      {teachers.data && <Pagination offset={teacherOffset} limit={size} total={teachers.data.total} change={setTeacherOffset}/>}
    </Panel>}
  </>
}

export function CourseDetail() {
  const { id } = useParams()
  const user = useOutletContext<User>()
  const query = useApi<Course>(`/courses/${id}`)
  if (!query.data) return <QueryState pending={query.isPending} error={query.error}/>
  const course = query.data
  return <>
    <Header title={course.name} subtitle={`${course.specialty} · ${course.academic_year} · ${course.subject_name}`} back={{ to: '/courses', label: 'Дисципліни' }}
      action={<Link className="button primary" to={`/questions?course_id=${course.id}`}>Питання курсу <ArrowRight size={16}/></Link>}/>
    {course.demo && <div><Demo/></div>}
    {user.role === 'student' ? <Panel title="Про курс"><div className="panel-body">{course.description || 'Опис курсу ще не додано.'}</div></Panel> : <>
      <CourseForm course={course}/><CourseAccess course={course} admin={user.role === 'admin'}/>
    </>}
  </>
}
