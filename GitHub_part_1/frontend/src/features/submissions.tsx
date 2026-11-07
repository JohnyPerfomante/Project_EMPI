import { useQueryClient } from '@tanstack/react-query'
import { Check, Clock3, GitCompareArrows, History, RefreshCw, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useOutletContext, useParams, useSearchParams } from 'react-router-dom'
import {
  Badge, DateFilter, Empty, Field, Header, Notice, Pagination, Panel, QueryState, SearchBox, SelectFilter,
  Table, useAction, useFilters,
} from '../components/ui'
import { api, useApi, usePage } from '../lib/api'
import { date, labels, percent } from '../lib/format'
import type { Analysis, Course, Group, Reference, Result, Review, Submission, User } from '../lib/types'

const size = 12
const listBack = { to: '/submissions', label: 'До списку відповідей' }

export function Submissions() {
  const user = useOutletContext<User>()
  const staff = user.role !== 'student'
  const [params] = useSearchParams()
  const filters = useFilters({ review_status: params.get('review_status') ?? '', course_id: params.get('course_id') ?? '' })
  const selectedCourse = filters.values.course_id
  const courses = usePage<Course>('/courses', { limit: 100 })
  const groups = usePage<Group>(`/courses/${selectedCourse}/groups`, { limit: 100 }, staff && Boolean(selectedCourse))
  const query = usePage<Submission>('/submissions', { ...filters.values, offset: filters.offset, limit: size }, true, 15_000)
  return <>
    <Header title={staff ? 'Перевірка відповідей' : 'Мої відповіді'} eyebrow="ПЕРЕВІРКА ЗНАНЬ"
      subtitle={staff ? 'Порівнюйте відповіді з еталонами та фіксуйте рішення.' : 'Історія ваших відповідей і доступні результати.'}/>
    <Panel>
      <div className="filterbar">
        <SearchBox value={filters.values.q} onChange={v => filters.set('q', v)} placeholder={staff ? 'Студент, питання або відповідь' : 'Питання або відповідь'}/>
        <SelectFilter label="Дисципліна" empty="Усі дисципліни" value={selectedCourse} onChange={v => { filters.set('course_id', v); filters.set('group_id', '') }}
          options={courses.data?.items.map(item => ({ value: item.id, label: item.name })) ?? []}/>
        {staff && selectedCourse && <SelectFilter label="Група" empty="Усі групи курсу" value={filters.values.group_id}
          onChange={v => filters.set('group_id', v)} options={groups.data?.items.map(item => ({ value: item.id, label: item.name })) ?? []}/>}
        <SelectFilter label="Стан аналізу" empty="Усі стани аналізу" value={filters.values.status} onChange={v => filters.set('status', v)}
          options={['queued', 'processing', 'analyzed', 'failed'].map(value => ({ value, label: labels[value] }))}/>
        {staff && <SelectFilter label="Категорія" empty="Усі категорії" value={filters.values.category} onChange={v => filters.set('category', v)}
          options={['HIGH_MATCH', 'NEEDS_REVIEW', 'LOW_MATCH'].map(value => ({ value, label: labels[value] }))}/>}
        <SelectFilter label="Рішення викладача" empty="Усі відповіді" value={filters.values.review_status} onChange={v => filters.set('review_status', v)}
          options={[{ value: 'pending', label: 'Без рішення' }, { value: 'reviewed', label: 'Перевірено' }]}/>
        <DateFilter label="Від" value={filters.values.date_from} onChange={v => filters.set('date_from', v)}/>
        <DateFilter label="До" value={filters.values.date_to} onChange={v => filters.set('date_to', v)}/>
      </div>
      <QueryState pending={query.isPending} error={query.error}/>
      {query.data && (query.data.items.length ? <Table headings={staff
        ? ['Студент', 'Питання', 'Дата', 'Аналіз', 'Рішення']
        : ['Питання', 'Дисципліна', 'Дата', 'Аналіз', 'Рішення']}>
        {query.data.items.map(item => <tr key={item.id}>
          {staff && <td>{item.student_name}<small>{item.group_name}</small></td>}
          <td><Link className="row-link" to={`/submissions/${item.id}`}>{item.question_text}</Link>{staff && <small>{item.course_name}</small>}</td>
          {!staff && <td>{item.course_name}</td>}
          <td>{date(item.created_at, true)}</td><td><Badge value={item.status === 'analyzed' ? item.category ?? item.status : item.status}/></td>
          <td>{item.decision ? <DecisionBadge decision={item.decision}/> : '—'}</td>
        </tr>)}
      </Table> : <Empty text="За вибраними параметрами відповідей немає."/>)}
      {query.data && <Pagination offset={filters.offset} limit={size} total={query.data.total} change={filters.setOffset}/>}
    </Panel>
  </>
}

function DecisionBadge({ decision }: { decision: Review['decision'] }) {
  const map = { approved: 'correct', partial: 'partial', rejected: 'incorrect' }
  return <Badge value={map[decision]}/>
}

function TeacherDecision({ submission, analysis, review }: { submission: Submission; analysis: Analysis; review: Review | null }) {
  const [comment, setComment] = useState(review?.comment ?? '')
  const [saveVariation, setSaveVariation] = useState(false)
  const [reference, setReference] = useState(analysis.reference_answer_id)
  const [decision, setDecision] = useState<'approve' | 'partial' | 'reject'>(review?.decision === 'rejected' ? 'reject' : review?.decision === 'partial' ? 'partial' : 'approve')
  const refs = useApi<Reference[]>(`/questions/${submission.question_id}/reference-answers`, saveVariation)
  const action = useAction()
  const queryClient = useQueryClient()
  const save = (e: FormEvent) => {
    e.preventDefault()
    void action.run(async () => {
      await api<Review>(`/reviews/${analysis.id}/${decision}`, 'POST', {
        comment, save_variation: decision === 'approve' && saveVariation,
        ...(decision === 'approve' && saveVariation ? { reference_answer_id: reference } : {}),
      })
      setSaveVariation(false)
      await queryClient.invalidateQueries()
    }, 'Рішення викладача збережено.')
  }
  return <Panel title="Рішення викладача" subtitle="Рішення зберігається в історії разом із версією аналізу"
    action={review && <DecisionBadge decision={review.decision}/>}>
    <form className="panel-body stack" onSubmit={save}>
      <div className="choice-row" role="group" aria-label="Оберіть рішення">
        <button type="button" aria-pressed={decision === 'approve'} className={`button choice ${decision === 'approve' ? 'selected' : ''}`}
          onClick={() => setDecision('approve')}><Check size={17}/> Правильно</button>
        <button type="button" aria-pressed={decision === 'partial'} className={`button choice ${decision === 'partial' ? 'selected' : ''}`}
          onClick={() => { setDecision('partial'); setSaveVariation(false) }}>Частково правильно</button>
        <button type="button" aria-pressed={decision === 'reject'} className={`button choice ${decision === 'reject' ? 'selected' : ''}`}
          onClick={() => { setDecision('reject'); setSaveVariation(false) }}><X size={17}/> Неправильно</button>
      </div>
      <Field label="Коментар"><textarea rows={3} value={comment} onChange={e => setComment(e.target.value)} maxLength={3000}/></Field>
      {decision === 'approve' && <label className="check"><input type="checkbox" checked={saveVariation}
        onChange={e => setSaveVariation(e.target.checked)}/> Зберегти як затверджену варіацію</label>}
      {saveVariation && <Field label="Еталон варіації"><select value={reference} onChange={e => setReference(Number(e.target.value))}>
        {!refs.data && <option value={reference}>Найближчий еталон №{reference}</option>}
        {refs.data?.map(item => <option value={item.id} key={item.id}>№{item.id} · {item.text.slice(0, 110)}</option>)}
      </select></Field>}
      {saveVariation && refs.error && <QueryState pending={false} error={refs.error}/>}
      {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
      <div><button className="button primary" disabled={action.pending}><Check size={17}/> Зберегти рішення</button></div>
    </form>
  </Panel>
}

function Scores({ analysis }: { analysis: Analysis }) {
  const measures = [
    ['Семантична подібність', analysis.semantic_similarity], ['Лексична подібність', analysis.lexical_similarity],
    ['Покриття понять', analysis.concept_coverage],
  ] as const
  return <div className="panel-body stack">
    <div className="score-total"><strong>{percent(analysis.final_similarity)}</strong><Badge value={analysis.category}/></div>
    {measures.map(([label, value]) => <div className="score-line" key={label}>
      <div><span>{label}</span><b>{percent(value)}</b></div>
      <progress aria-label={label} max={1} value={value ?? 0}/>
    </div>)}
    <p>{analysis.explanation}</p>
    {!!analysis.matches.length && <div><strong>Знайдені поняття</strong><p>{analysis.matches.join(', ')}</p></div>}
    {!!analysis.missing.length && <div><strong>Пропущені поняття</strong><p>{analysis.missing.join(', ')}</p></div>}
    {analysis.warnings.map((warning, index) => <Notice key={index}>{warning.critical && <strong>Критична ознака. </strong>}{warning.message}</Notice>)}
    <details className="technical"><summary>Відомості про аналіз</summary><p>{analysis.model_name}</p><code>{analysis.model_version}</code><p>{analysis.processing_ms} мс · {date(analysis.created_at, true)}</p></details>
  </div>
}

function HistoryPanels({ id }: { id: number }) {
  const [offset, setOffset] = useState(0)
  const [reviewOffset, setReviewOffset] = useState(0)
  const [selected, setSelected] = useState<Analysis | null>(null)
  const analyses = usePage<Analysis>(`/submissions/${id}/history`, { limit: size, offset })
  const reviews = usePage<Review>(`/submissions/${id}/reviews`, { limit: size, offset: reviewOffset })
  return <>
    <Panel title="Історія аналізів">
      <QueryState pending={analyses.isPending} error={analyses.error}/>
      {analyses.data && (analyses.data.items.length ? <Table headings={['Версія', 'Дата', 'Категорія', 'Подібність', 'Дія']}>
        {analyses.data.items.map(item => <tr key={item.id}><td>№{item.id}</td><td>{date(item.created_at, true)}</td><td><Badge value={item.category}/></td><td>{percent(item.final_similarity)}</td>
          <td><button className="button tertiary" onClick={() => setSelected(selected?.id === item.id ? null : item)}>{selected?.id === item.id ? 'Згорнути' : 'Деталі'}</button></td></tr>)}
      </Table> : <Empty text="Завершених аналізів ще немає."/>)}
      {analyses.data && <Pagination offset={offset} limit={size} total={analyses.data.total} change={setOffset}/>}
    </Panel>
    {selected && <Panel title={`Аналіз №${selected.id}`}><div className="panel-body preserve">
      <strong>Еталон на момент аналізу</strong><p>{selected.material_snapshot.reference_text}</p>
      {selected.material_snapshot.variation_text && <><strong>Варіація</strong><p>{selected.material_snapshot.variation_text}</p></>}
    </div><Scores analysis={selected}/></Panel>}
    <Panel title="Історія рішень">
      <QueryState pending={reviews.isPending} error={reviews.error}/>
      {reviews.data && (reviews.data.items.length ? <Table headings={['Дата', 'Викладач', 'Рішення', 'Коментар', 'Аналіз']}>
        {reviews.data.items.map(item => <tr key={item.id}><td>{date(item.created_at, true)}</td><td>{item.reviewer}</td><td><DecisionBadge decision={item.decision}/></td>
          <td className="preserve">{item.comment || '—'}</td><td>№{item.analysis_result_id}{item.variation_id && <small><Link to={`/variations/${item.variation_id}`}>Варіація №{item.variation_id}</Link></small>}</td></tr>)}
      </Table> : <Empty text="Викладач ще не ухвалював рішення."/>)}
      {reviews.data && <Pagination offset={reviewOffset} limit={size} total={reviews.data.total} change={setReviewOffset}/>}
    </Panel>
  </>
}

export function SubmissionDetail() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const user = useOutletContext<User>()
  const staff = user.role !== 'student'
  const query = useApi<Submission>(`/submissions/${id}`)
  const result = useApi<Result>(`/submissions/${id}/result`, true, 2500)
  const [history, setHistory] = useState(false)
  const action = useAction()
  const queryClient = useQueryClient()
  if (!query.data) return <QueryState pending={query.isPending} error={query.error}/>
  const item = query.data
  const details = result.data
  const status = details?.status ?? item.status
  const busy = status === 'queued' || status === 'processing'
  const analysis = details?.analysis
  const full = analysis && 'material_snapshot' in analysis ? analysis : null
  return <>
    <Header title={staff ? `Перевірка відповіді №${id}` : 'Результат відповіді'} subtitle={item.course_name} back={listBack}
      action={staff ? <button className="button secondary" aria-pressed={history} onClick={() => setHistory(!history)}><History size={17}/> {history ? 'Приховати історію' : 'Історія'}</button> : <Badge value={status}/>}/>
    {params.get('sent') === '1' && <Notice success>Відповідь надіслано й збережено.</Notice>}
    {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
    {staff && history && <HistoryPanels id={item.id}/>}
    <QueryState pending={result.isPending} error={result.error}/>
    {busy && <div className="queue-note" role="status"><Clock3 size={18}/> {status === 'queued' ? 'Відповідь очікує аналізу.' : 'Відповідь аналізується.'}</div>}
    {status === 'failed' && <Notice>Аналіз завершився помилкою. Відповідь збережено.</Notice>}
    <div className={staff ? 'review-grid' : 'dashboard-grid'}>
      <div className="stack">
        <Panel title={staff ? 'Дані відповіді' : 'Завдання'}><div className="panel-body">
          <dl className="description">
            {staff && <><div><dt>Студент</dt><dd>{item.student_name}</dd></div><div><dt>Група</dt><dd>{item.group_name}</dd></div></>}
            <div><dt>Надіслано</dt><dd>{date(item.created_at, true)}</dd></div>
            <div><dt>Питання</dt><dd>{item.question_text}</dd></div>
          </dl>
        </div></Panel>
        {!staff && <Panel title="Ваша відповідь"><div className="panel-body preserve">{item.answer_text}</div></Panel>}
      </div>
      {staff && <div className="stack">
        <Panel title="Відповідь студента"><div className="panel-body preserve">{item.answer_text}</div></Panel>
        {full && <Panel title="Еталон на момент аналізу"><div className="panel-body preserve">{full.material_snapshot.reference_text}</div></Panel>}
        {full?.material_snapshot.variation_text && <Panel title="Найближча затверджена варіація"
          action={full.variation_id && <Link className="subtle-link" to={`/variations/${full.variation_id}`}>Картка</Link>}>
          <div className="panel-body preserve">{full.material_snapshot.variation_text}</div></Panel>}
      </div>}
      <div className="stack">
        <Panel title="Автоматичний аналіз" action={<GitCompareArrows size={19} className="muted"/>}>
          {full ? <Scores analysis={full}/> : <div className="panel-body stack">
            {analysis ? <><div className="score-total"><strong>{percent(analysis.final_similarity)}</strong><Badge value={analysis.category}/></div><p>{analysis.explanation}</p></>
              : <p>{details?.visibility === 'hidden' ? 'Результат приховано налаштуваннями курсу.' : details?.visibility === 'reviewed'
                ? 'Результат стане доступним після рішення викладача.' : 'Результат ще не доступний.'}</p>}
          </div>}
          {staff && !busy && <div className="panel-body"><button className="button secondary" disabled={action.pending} onClick={() =>
            void action.run(async () => { await api(`/submissions/${id}/${status === 'failed' ? 'analyze' : 'reanalyze'}`, 'POST'); await queryClient.invalidateQueries() }, 'Аналіз додано до черги.')
          }><RefreshCw size={16}/> Повторити аналіз</button></div>}
        </Panel>
        {!staff && <Panel title="Перевірка викладачем"><div className="panel-body stack">
          <div>{details?.review ? <DecisionBadge decision={details.review.decision}/> : details?.review_status === 'reviewed' ? 'Перевірено' : 'Рішення ще не ухвалено'}</div>
          {details?.review?.comment && <p className="preserve">{details.review.comment}</p>}
        </div></Panel>}
      </div>
    </div>
    {staff && full && status === 'analyzed' && <TeacherDecision key={full.id} submission={item} analysis={full} review={details?.review ?? null}/>}
  </>
}
