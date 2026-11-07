import { useQueryClient } from '@tanstack/react-query'
import { Archive, Check, RotateCcw, X } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  Badge, DateFilter, Demo, Empty, Header, Notice, Pagination, Panel, QueryState, SearchBox, SelectFilter,
  Table, useAction, useFilters,
} from '../components/ui'
import { api, useApi, usePage } from '../lib/api'
import { date } from '../lib/format'
import type { Course, Variation, VariationStatus } from '../lib/types'

const tabs: { value: VariationStatus; label: string }[] = [
  { value: 'proposed', label: 'Очікують перевірки' }, { value: 'approved', label: 'Затверджені' },
  { value: 'rejected', label: 'Відхилені' }, { value: 'archived', label: 'Архів' },
]
const pageSize = 12

export function Variations() {
  const [params] = useSearchParams()
  const filters = useFilters({ status: 'proposed', question_id: params.get('question_id') ?? '' })
  const query = usePage<Variation>('/variations', { ...filters.values, limit: pageSize, offset: filters.offset })
  const courses = usePage<Course>('/courses', { limit: 100 })
  return <>
    <Header title="База варіацій" eyebrow="НАВЧАЛЬНІ МАТЕРІАЛИ"
      subtitle="Переглядайте та затверджуйте альтернативні формулювання еталонних відповідей."/>
    <Panel>
      <div className="tabs" aria-label="Статус варіацій">{tabs.map(tab => <button key={tab.value} type="button"
        aria-pressed={filters.values.status === tab.value} className={filters.values.status === tab.value ? 'selected' : ''}
        onClick={() => filters.set('status', tab.value)}>{tab.label}</button>)}</div>
      <div className="filterbar">
        <SearchBox value={filters.values.q} onChange={v => filters.set('q', v)} placeholder="Текст варіації або питання"/>
        <SelectFilter label="Дисципліна" empty="Усі дисципліни" value={filters.values.course_id} onChange={v => filters.set('course_id', v)}
          options={courses.data?.items.map(item => ({ value: item.id, label: item.name })) ?? []}/>
        <DateFilter label="Від" value={filters.values.date_from} onChange={v => filters.set('date_from', v)}/>
        <DateFilter label="До" value={filters.values.date_to} onChange={v => filters.set('date_to', v)}/>
        {filters.values.question_id && <button className="button tertiary" onClick={() => filters.set('question_id', '')}>Усі питання <X size={15}/></button>}
      </div>
      <QueryState pending={query.isPending} error={query.error}/>
      {query.data && (query.data.items.length ? <Table headings={['Формулювання', 'Питання', 'Автор', 'Статус']}>
        {query.data.items.map(item => <tr key={item.id}>
          <td><Link className="row-link" to={`/variations/${item.id}`}>{item.text}</Link>{item.demo && <Demo/>}</td>
          <td>{item.question_text}<small>{item.course_name}</small></td><td>{item.author}<small>{date(item.created_at)}</small></td>
          <td><Badge value={item.status}/>{item.reviewer && <small>{item.reviewer}</small>}</td>
        </tr>)}
      </Table> : <Empty text="У цій вкладці немає варіацій за вибраними параметрами."/>)}
      {query.data && <Pagination offset={filters.offset} limit={pageSize} total={query.data.total} change={filters.setOffset}/>}
    </Panel>
  </>
}

export function VariationDetail() {
  const { id } = useParams()
  const query = useApi<Variation>(`/variations/${id}`)
  const action = useAction()
  const queryClient = useQueryClient()
  if (!query.data) return <QueryState pending={query.isPending} error={query.error}/>
  const item = query.data
  const transition = (kind: string) => void action.run(async () => {
    await api<Variation>(`/variations/${id}/${kind}`, 'POST')
    await queryClient.invalidateQueries()
  }, 'Статус варіації оновлено.')
  return <>
    <Header title={`Варіація №${id}`} subtitle={item.course_name} back={{ to: '/variations', label: 'База варіацій' }}
      action={<Badge value={item.status}/>}/>
    {item.demo && <Notice>Демонстраційний приклад. Перевірте його зміст перед затвердженням.</Notice>}
    <Panel title="Формулювання"><div className="panel-body stack">
      <p className="preserve">{item.text}</p>
      <dl className="description"><div><dt>Питання</dt><dd><Link className="subtle-link" to={`/questions/${item.question_id}`}>{item.question_text}</Link></dd></div>
        <div><dt>Автор</dt><dd>{item.author} · {date(item.created_at, true)}</dd></div>
        {item.reviewer && <div><dt>Остання перевірка</dt><dd>{item.reviewer} · {date([item.approved_at, item.rejected_at].filter(Boolean).sort().at(-1)!, true)}</dd></div>}
      </dl>
    </div></Panel>
    <Panel title="Еталон для зіставлення"><div className="panel-body preserve">{item.reference_text}</div></Panel>
    {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
    <div className="form-actions">
      {item.status === 'proposed' && <>
        <button className="button primary" disabled={action.pending} onClick={() => transition('approve')}><Check size={17}/> Затвердити варіацію</button>
        <button className="button danger" disabled={action.pending} onClick={() => transition('reject')}><X size={17}/> Відхилити</button>
      </>}
      {item.status !== 'archived' && <button className="button secondary" disabled={action.pending} onClick={() => transition('archive')}><Archive size={17}/> Архівувати</button>}
      {(item.status === 'rejected' || item.status === 'archived') && <button className="button secondary" disabled={action.pending}
        onClick={() => transition('reopen')}><RotateCcw size={17}/> Повернути на перевірку</button>}
    </div>
  </>
}
