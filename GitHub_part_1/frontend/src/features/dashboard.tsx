import { ArrowDownRight, ArrowRight, BookOpen, ClipboardCheck, Clock3, FileStack, Layers, Plus, UsersRound } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { Badge, DateFilter, Empty, Header, Panel, QueryState, SelectFilter, Table, useFilters } from '../components/ui'
import { useApi, usePage, withParams } from '../lib/api'
import { date, labels } from '../lib/format'
import type { Course, Question, Submission, Summary, User } from '../lib/types'

const chartColor = '#278782'

function StudentDashboard({ user }: { user: User }) {
  const questions = usePage<Question>('/questions', { limit: 4 })
  const courses = usePage<Course>('/courses', { limit: 1 })
  const submissions = usePage<Submission>('/submissions', { limit: 4 })
  const summary = useApi<{ completed_questions: number; pending_reviews: number }>('/submissions/summary', true, 15_000)
  return <>
    <Header title={`Вітаємо, ${user.full_name.split(' ')[0]}!`} eyebrow="КАБІНЕТ СТУДЕНТА"
      subtitle="Ваші дисципліни, відкриті завдання й історія відповідей."
      action={<Link className="button primary" to="/questions">Відкрити завдання <ArrowRight size={17}/></Link>}/>
    <QueryState pending={summary.isPending} error={summary.error}/>
    <div className="stats student-stats">
      <Metric title="Дисципліни" count={courses.data?.total} icon={BookOpen} to="/courses"/>
      <Metric title="Доступні завдання" count={questions.data?.total} icon={FileStack} to="/questions"/>
      <Metric title="Виконані завдання" count={summary.data?.completed_questions} icon={ClipboardCheck} to="/submissions"/>
      <Metric title="Очікують перевірки" count={summary.data?.pending_reviews} icon={Clock3} to="/submissions?review_status=pending" tone="amber"/>
    </div>
    <Panel title="Доступні завдання" subtitle="Останні опубліковані питання" action={<Link className="subtle-link" to="/questions">Усі завдання <ArrowRight size={15}/></Link>}>
      <QueryState pending={questions.isPending} error={questions.error}/>
      {questions.data && (questions.data.total ? <Table headings={['Питання', 'Дисципліна', 'Складність']}>
        {questions.data.items.map(item => <tr key={item.id}><td><Link className="row-link" to={`/questions/${item.id}`}>{item.text}</Link></td><td>{item.subject_name}</td><td>{labels[item.difficulty]}</td></tr>)}
      </Table> : <Empty text="Поки немає опублікованих питань." />)}
    </Panel>
    <Panel title="Останні відповіді">
      <QueryState pending={submissions.isPending} error={submissions.error}/>
      {submissions.data && (submissions.data.total ? <Table headings={['Питання', 'Дата', 'Стан']}>
        {submissions.data.items.map(item => <tr key={item.id}><td><Link className="row-link" to={`/submissions/${item.id}`}>{item.question_text}</Link></td><td>{date(item.created_at)}</td><td><Badge value={item.status}/></td></tr>)}
      </Table> : <Empty text="Ви ще не надсилали відповідей." />)}
    </Panel>
  </>
}

function Metric({ title, count, icon: Icon, to, tone = 'teal' }: {
  title: string; count: number | undefined; icon: typeof BookOpen; to: string; tone?: string
}) {
  return <Link className="metric" to={to}><div className={`metric-icon ${tone}`}><Icon size={19}/></div>
    <div><span>{title}</span><strong>{count ?? '—'}</strong></div><ArrowDownRight className="metric-arrow" size={16}/></Link>
}

export function Dashboard() {
  const user = useOutletContext<User>()
  return user.role === 'student' ? <StudentDashboard user={user}/> : <StaffDashboard user={user}/>
}

function StaffDashboard({ user }: { user: User }) {
  const [params] = useSearchParams()
  const filters = useFilters({ course_id: params.get('course_id') ?? '' })
  const stats = useApi<Summary>(withParams('/reports/summary', filters.values), true, 20_000)
  const courses = usePage<Course>('/courses', { limit: 100 })
  const results = usePage<Submission>('/submissions', { limit: 5, ...filters.values }, true, 20_000)
  const counts = stats.data?.counts
  const categoryColors = { HIGH_MATCH: '#278782', NEEDS_REVIEW: '#c58b33', LOW_MATCH: '#bd6674' }
  const categories = (['HIGH_MATCH', 'NEEDS_REVIEW', 'LOW_MATCH'] as const).map(category => ({
    category, count: stats.data?.categories.find(item => item.category === category)?.count ?? 0,
  }))
  const total = categories.reduce((sum, item) => sum + item.count, 0)
  return <>
    <Header title={user.role === 'admin' ? 'Панель адміністратора' : 'Панель викладача'} eyebrow="РОБОЧИЙ ПРОСТІР"
      subtitle="Навчальні дисципліни, відповіді студентів і перебіг перевірки."
      action={user.role === 'admin'
        ? <Link className="button primary" to="/admin/users"><UsersRound size={17}/> Керувати користувачами</Link>
        : <Link className="button primary" to="/questions/new"><Plus size={18}/> Створити питання</Link>}/>
    <div className="filterbar dashboard-filter">
      <SelectFilter label="Дисципліна" empty="Усі дисципліни" value={filters.values.course_id} onChange={v => filters.set('course_id', v)}
        options={courses.data?.items.map(course => ({ value: course.id, label: course.name })) ?? []}/>
      <DateFilter label="Від" value={filters.values.date_from} onChange={v => filters.set('date_from', v)}/>
      <DateFilter label="До" value={filters.values.date_to} onChange={v => filters.set('date_to', v)}/>
    </div>
    <QueryState pending={stats.isPending} error={stats.error}/>
    <div className="stats staff-stats">
      <Metric title="Дисципліни" count={counts?.subjects} icon={BookOpen} to="/courses"/>
      <Metric title="Питання" count={counts?.questions} icon={FileStack} to="/questions" tone="blue"/>
      <Metric title="Відповіді" count={counts?.submissions} icon={ClipboardCheck} to="/submissions" tone="blue"/>
      <Metric title="Без рішення" count={counts?.pending_reviews} icon={ClipboardCheck} to="/submissions?review_status=pending" tone="amber"/>
      <Metric title="Нові варіації" count={counts?.proposed_variations} icon={Layers} to="/variations" tone="teal"/>
    </div>
    <div className="dashboard-grid">
      <Panel title="Динаміка відповідей" subtitle="Надходження за останні 30 днів вибраного періоду">
        {stats.data && <div className="chart" aria-label="Динаміка надсилання відповідей">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stats.data.activity} margin={{ left: -20, right: 10, top: 8 }}>
              <CartesianGrid vertical={false} stroke="#e9eef3" strokeDasharray="4 4"/>
              <XAxis dataKey="date" tickFormatter={value => value.slice(5).split('-').reverse().join('.')} tickLine={false} axisLine={false} minTickGap={32} tick={{ fontSize: 11, fill: '#607487' }}/>
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#607487' }}/>
              <Tooltip cursor={{ fill: '#eaf2f2' }} labelFormatter={value => date(String(value))}
                formatter={value => [value, 'Відповіді']}/>
              <Bar dataKey="count" isAnimationActive={false} fill={chartColor} radius={[4, 4, 0, 0]} maxBarSize={22}/>
            </BarChart>
          </ResponsiveContainer>
        </div>}
      </Panel>
      <Panel title="Розподіл результатів" subtitle="За останнім аналізом кожної відповіді">
        <div className="distribution">
          <div><strong>{stats.data ? total : '—'}</strong><span> проаналізовано</span></div>
          <div className="distribution-bar" aria-hidden="true">{categories.map(item => <div key={item.category}
            style={{ backgroundColor: categoryColors[item.category], width: total ? `${item.count * 100 / total}%` : '0%' }}/>)}</div>
          {categories.map(item => <div className="distribution-line" key={item.category}><i style={{ backgroundColor: categoryColors[item.category] }}/><span>{labels[item.category]}</span><b>{item.count}</b></div>)}
        </div>
      </Panel>
    </div>
    <Panel title="Останні відповіді" subtitle="Перейдіть до відповіді, щоб переглянути аналіз і ухвалити рішення"
      action={<Link className="subtle-link" to="/submissions">Усі відповіді <ArrowRight size={15}/></Link>}>
      <QueryState pending={results.isPending} error={results.error}/>
      {results.data && (results.data.total ? <Table headings={['Студент', 'Питання', 'Дата', 'Результат']}>
        {results.data.items.map(item => <tr key={item.id}><td>{item.student_name}<small>{item.group_name}</small></td>
          <td><Link className="row-link" to={`/submissions/${item.id}`}>{item.question_text}</Link></td>
          <td>{date(item.created_at)}</td><td><Badge value={item.category ?? item.status}/></td></tr>)}
      </Table> : <Empty text="За вибраний період відповідей немає."/>)}
    </Panel>
    <div className="dashboard-grid equal">
      <Panel title="Перевірка за дисциплінами">
        {stats.data && (stats.data.courses.length ? <Table headings={['Дисципліна', 'Відповіді', 'Перевірено']}>{stats.data.courses.map(course => <tr key={course.course_id}><td><Link className="row-link" to={`/courses/${course.course_id}`}>{course.name}</Link></td><td>{course.submissions}</td><td>{course.reviewed}</td></tr>)}</Table> : <Empty/>)}
      </Panel>
      <Panel title="Активність студентів" subtitle="До 10 студентів за кількістю відповідей">
        {stats.data && (stats.data.students.length ? <Table headings={['Студент', 'Відповіді']}>{stats.data.students.map(student => <tr key={student.student_id}><td>{student.name}</td><td>{student.submissions}</td></tr>)}</Table> : <Empty/>)}
      </Panel>
    </div>
  </>
}
