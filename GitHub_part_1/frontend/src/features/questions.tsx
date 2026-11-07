import { useQueryClient } from '@tanstack/react-query'
import { Archive, ArrowRight, CirclePlus, Plus, Save, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useOutletContext, useParams, useSearchParams } from 'react-router-dom'
import {
  Badge, Demo, Empty, Field, Header, Notice, Pagination, Panel, QueryState, SearchBox, SelectFilter, Table, useAction, useFilters,
} from '../components/ui'
import { api, useApi, usePage } from '../lib/api'
import { date, labels } from '../lib/format'
import type { Course, Difficulty, Question, Reference, ReferenceFields, Submission, User, Variation } from '../lib/types'

const pageSize = 12
const difficultyOptions = ['easy', 'medium', 'hard'] as const
const freshReference = (): ReferenceFields => ({ text: '', concepts: [], conflict_rules: [] })
const back = { to: '/questions', label: 'Банк питань' }

export function Questions() {
  const user = useOutletContext<User>()
  const staff = user.role !== 'student'
  const [params] = useSearchParams()
  const filters = useFilters({ course_id: params.get('course_id') ?? '', sort: 'newest' })
  const courses = usePage<Course>('/courses', { limit: 100 })
  const questions = usePage<Question>('/questions', { ...filters.values, offset: filters.offset, limit: pageSize })
  return <>
    <Header title={staff ? 'Банк питань' : 'Завдання'} eyebrow="НАВЧАЛЬНІ МАТЕРІАЛИ"
      subtitle={staff ? 'Створюйте питання, еталони й критерії перевірки.' : 'Оберіть питання, щоб надіслати відповідь.'}
      action={staff && <Link to="/questions/new" className="button primary"><Plus size={17}/> Створити питання</Link>}/>
    <Panel>
      <div className="filterbar">
        <SearchBox value={filters.values.q} onChange={v => filters.set('q', v)} placeholder="Пошук за текстом питання"/>
        <SelectFilter label="Дисципліна" value={filters.values.course_id} onChange={v => filters.set('course_id', v)}
          empty="Усі дисципліни" options={courses.data?.items.map(item => ({ value: item.id, label: item.name })) ?? []}/>
        {staff && <SelectFilter label="Статус" value={filters.values.status} onChange={v => filters.set('status', v)}
          empty="Усі статуси" options={['draft', 'published', 'archived'].map(value => ({ value, label: labels[value] }))}/>}
        <SelectFilter label="Сортування" value={filters.values.sort} onChange={v => filters.set('sort', v)}
          options={[{ value: 'newest', label: 'Спочатку нові' }, { value: 'oldest', label: 'Спочатку давні' }, { value: 'text', label: 'За алфавітом' }]}/>
      </div>
      <QueryState pending={questions.isPending} error={questions.error}/>
      {questions.data && (questions.data.items.length ? <Table headings={staff
        ? ['Питання', 'Дисципліна', 'Матеріали', 'Статус', 'Створено']
        : ['Питання', 'Дисципліна', 'Складність']}>
        {questions.data.items.map(item => <tr key={item.id}>
          <td><Link className="row-link" to={`/questions/${item.id}`}>{item.text}</Link>{item.demo && <Demo/>}</td>
          <td>{item.subject_name}</td>
          {staff ? <><td>{item.reference_count} етал. <small>{item.variation_count} варіац.</small></td>
            <td><Badge value={item.status}/></td><td>{date(item.created_at)}<small>{item.author}</small></td></>
            : <td>{labels[item.difficulty]}</td>}
        </tr>)}
      </Table> : <Empty/>)}
      {questions.data && <Pagination total={questions.data.total} offset={filters.offset} limit={pageSize} change={filters.setOffset}/>}
    </Panel>
  </>
}

function ReferenceEditor({ value, change, disabled = false }: {
  value: ReferenceFields; change: (value: ReferenceFields) => void; disabled?: boolean
}) {
  const [synonyms, setSynonyms] = useState(() => value.concepts.map(item => item.synonyms.join(', ')))
  return <fieldset className="reference-editor stack" disabled={disabled}>
    <Field label="Текст еталона"><textarea value={value.text} required minLength={5} maxLength={4000} rows={4}
      onChange={event => change({ ...value, text: event.target.value })} placeholder="Опишіть повну правильну відповідь."/></Field>
    <div className="section-label"><strong>Ключові поняття</strong><button type="button" className="button tertiary"
      disabled={value.concepts.length >= 24} onClick={() => {
        setSynonyms([...synonyms, ''])
        change({ ...value, concepts: [...value.concepts, { concept: '', synonyms: [], importance_weight: 1, is_required: true }] })
      }}><Plus size={15}/> Додати поняття</button></div>
    {value.concepts.map((item, index) => {
      const update = (fields: Partial<typeof item>) => change({ ...value, concepts: value.concepts.map((old, i) => i === index ? { ...old, ...fields } : old) })
      return <div className="concept-row" key={index}>
        <Field label="Поняття"><input required maxLength={180} value={item.concept} onChange={e => update({ concept: e.target.value })}/></Field>
        <Field label="Синоніми через кому"><input value={synonyms[index] ?? ''} onChange={e => {
          setSynonyms(previous => previous.map((old, i) => i === index ? e.target.value : old))
          update({ synonyms: e.target.value.split(',').map(v => v.trim()).filter(Boolean) })
        }}/></Field>
        <Field label="Вага"><input required type="number" min="0.1" max="10" step="0.1" value={item.importance_weight || ''} onChange={e => update({ importance_weight: Number(e.target.value) })}/></Field>
        <label className="check concept-check"><input type="checkbox" checked={item.is_required} onChange={e => update({ is_required: e.target.checked })}/> Обов’язкове</label>
        <button type="button" className="icon-button danger" aria-label="Вилучити поняття" onClick={() => {
          setSynonyms(synonyms.filter((_, i) => i !== index))
          change({ ...value, concepts: value.concepts.filter((_, i) => i !== index) })
        }}><Trash2 size={17}/></button>
      </div>
    })}
    <div className="section-label"><strong>Змістові конфлікти</strong><button type="button" className="button tertiary"
      disabled={value.conflict_rules.length >= 16} onClick={() => change({ ...value, conflict_rules: [...value.conflict_rules, { phrase: '', kind: 'contradiction', message: '' }] })}>
      <Plus size={15}/> Додати правило</button></div>
    {value.conflict_rules.map((rule, index) => {
      const update = (fields: Partial<typeof rule>) => change({ ...value, conflict_rules: value.conflict_rules.map((old, i) => i === index ? { ...old, ...fields } : old) })
      return <div className="conflict-row" key={index}>
        <Field label="Фраза"><input required maxLength={180} value={rule.phrase} onChange={e => update({ phrase: e.target.value })}/></Field>
        <Field label="Тип"><select value={rule.kind} onChange={e => update({ kind: e.target.value as typeof rule.kind })}><option value="contradiction">Суперечність</option><option value="terminology">Термінологія</option></select></Field>
        <Field label="Пояснення"><input required minLength={3} maxLength={300} value={rule.message} onChange={e => update({ message: e.target.value })}/></Field>
        <button type="button" className="icon-button danger" aria-label="Вилучити правило" onClick={() => change({ ...value, conflict_rules: value.conflict_rules.filter((_, i) => i !== index) })}><Trash2 size={17}/></button>
      </div>
    })}
  </fieldset>
}

export function NewQuestion() {
  const courses = usePage<Course>('/courses', { active: true, limit: 100 })
  const [params] = useSearchParams()
  const [course, setCourse] = useState(params.get('course_id') ?? '')
  const [text, setText] = useState('')
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [status, setStatus] = useState<'draft' | 'published'>('draft')
  const [references, setReferences] = useState([freshReference()])
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const action = useAction()
  const save = (event: FormEvent) => {
    event.preventDefault()
    void action.run(async () => {
      const item = await api<Question>('/questions', 'POST', { course_id: Number(course), text, difficulty, status, references })
      await queryClient.invalidateQueries()
      navigate(`/questions/${item.id}`)
    })
  }
  return <><Header title="Нове питання" subtitle="Налаштуйте питання, еталони й ключові поняття для перевірки." back={back}/>
    <QueryState pending={courses.isPending} error={courses.error}/>
    <form className="stack" onSubmit={save}>
      <Panel title="Основні відомості"><div className="panel-body stack">
        <div className="form-grid">
          <Field label="Курс"><select required value={course} onChange={e => setCourse(e.target.value)}><option value="">Оберіть курс</option>
            {courses.data?.items.map(item => <option key={item.id} value={item.id}>{item.subject_name} · {item.name}</option>)}</select></Field>
          <DifficultyField value={difficulty} change={setDifficulty}/>
          <Field label="Статус"><select value={status} onChange={e => setStatus(e.target.value as typeof status)}><option value="draft">Чернетка</option><option value="published">Опублікувати</option></select></Field>
        </div>
        <Field label="Текст питання"><textarea required minLength={5} maxLength={4000} rows={3} value={text}
          onChange={e => setText(e.target.value)} placeholder="Введіть відкрите питання для студентів."/></Field>
      </div></Panel>
      {references.map((item, index) => <Panel key={index} title={`Еталон ${index + 1}`}
        action={references.length > 1 && <button className="icon-button danger" type="button" aria-label="Вилучити еталон"
          onClick={() => setReferences(references.filter((_, i) => i !== index))}><Trash2 size={17}/></button>}>
        <div className="panel-body"><ReferenceEditor value={item} change={value => setReferences(references.map((old, i) => i === index ? value : old))}/></div>
      </Panel>)}
      {action.error && <Notice>{action.error}</Notice>}
      <div className="form-actions"><button type="button" className="button secondary" disabled={references.length >= 12}
        onClick={() => setReferences([...references, freshReference()])}><CirclePlus size={17}/> Додати еталон</button>
        <button className="button primary" disabled={action.pending}><Save size={17}/> Зберегти питання</button></div>
    </form></>
}

function DifficultyField({ value, change }: { value: Difficulty; change: (value: Difficulty) => void }) {
  return <Field label="Складність"><select value={value} onChange={e => change(e.target.value as Difficulty)}>
    {difficultyOptions.map(item => <option key={item} value={item}>{labels[item]}</option>)}</select></Field>
}

function EditReference({ question, reference, readOnly }: { question: Question; reference?: Reference; readOnly: boolean }) {
  const [value, setValue] = useState<ReferenceFields>(reference ? {
    text: reference.text, concepts: reference.concepts, conflict_rules: reference.conflict_rules,
  } : freshReference())
  const action = useAction()
  const queryClient = useQueryClient()
  const save = (e: FormEvent) => {
    e.preventDefault()
    void action.run(async () => {
      await api<Reference>(reference ? `/reference-answers/${reference.id}` : `/questions/${question.id}/reference-answers`,
        reference ? 'PATCH' : 'POST', value)
      if (!reference) setValue(freshReference())
      await queryClient.invalidateQueries()
    }, 'Еталон збережено.')
  }
  return <Panel title={reference ? `Еталон №${reference.id}` : 'Додатковий еталон'}>
    <form className="panel-body stack" onSubmit={save}>
      <ReferenceEditor key={reference?.updated_at ?? (value.text === '' && value.concepts.length === 0 && value.conflict_rules.length === 0 ? 'empty' : 'new')}
        value={value} change={setValue} disabled={readOnly}/>
      {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
      {!readOnly && <div><button className="button secondary" disabled={action.pending}><Save size={16}/> Зберегти еталон</button></div>}
    </form></Panel>
}

function StaffQuestion({ item }: { item: Question }) {
  const refs = useApi<Reference[]>(`/questions/${item.id}/reference-answers`)
  const [text, setText] = useState(item.text)
  const [difficulty, setDifficulty] = useState(item.difficulty)
  const [proposeFor, setProposeFor] = useState('')
  const [variantText, setVariantText] = useState('')
  const action = useAction()
  const variantAction = useAction()
  const queryClient = useQueryClient()
  const archived = item.status === 'archived'
  function edit(changes: object) {
    void action.run(async () => {
      await api<Question>(`/questions/${item.id}`, 'PATCH', changes)
      await queryClient.invalidateQueries()
    }, 'Питання оновлено.')
  }
  return <>
    <Header title="Картка питання" subtitle={item.course_name} back={back} action={<Badge value={item.status}/>}/>
    <Panel title="Питання" subtitle={item.demo ? 'Демонстраційний матеріал' : undefined}>
      <form className="panel-body stack" onSubmit={e => { e.preventDefault(); edit({ text, difficulty }) }}>
        <fieldset className="stack" disabled={archived}>
          <Field label="Текст питання"><textarea required minLength={5} maxLength={4000} rows={3} value={text} onChange={e => setText(e.target.value)}/></Field>
          <div className="form-grid"><DifficultyField value={difficulty} change={setDifficulty}/></div>
        </fieldset>
        {action.error && <Notice>{action.error}</Notice>}{action.success && <Notice success>{action.success}</Notice>}
        {!archived && <div className="form-actions">
          <button className="button secondary" disabled={action.pending}><Save size={16}/> Зберегти зміни</button>
          {item.status === 'draft' ? <button type="button" className="button primary" disabled={action.pending}
            onClick={() => edit({ status: 'published' })}>Опублікувати</button> : <button type="button" className="button secondary"
            disabled={action.pending} onClick={() => edit({ status: 'draft' })}>Зняти з публікації</button>}
          <button className="button danger" type="button" disabled={action.pending} onClick={() => {
            if (window.confirm('Архівувати це питання?')) void action.run(async () => {
              await api(`/questions/${item.id}/archive`, 'POST'); await queryClient.invalidateQueries()
            }, 'Питання архівовано.')
          }}><Archive size={16}/> Архівувати</button>
        </div>}
      </form>
    </Panel>
    <QueryState pending={refs.isPending} error={refs.error}/>
    {refs.data?.map(reference => <EditReference key={`${reference.id}-${reference.updated_at}`} reference={reference} question={item} readOnly={archived}/>)}
    {!archived && refs.data && refs.data.length < 12 && <EditReference question={item} readOnly={false}/>}
    <Panel title="Варіації" action={<Link className="subtle-link" to={`/variations?question_id=${item.id}`}>Переглянути <ArrowRight size={15}/></Link>}>
      {!archived && <form className="panel-body stack" onSubmit={e => {
        e.preventDefault()
        void variantAction.run(async () => {
          await api<Variation>('/variations', 'POST', { reference_answer_id: Number(proposeFor), text: variantText })
          setVariantText(''); await queryClient.invalidateQueries()
        }, 'Пропозицію варіації додано.')
      }}>
        <Field label="Еталон для варіації"><select required value={proposeFor} onChange={e => setProposeFor(e.target.value)}><option value="">Оберіть еталон</option>{refs.data?.map(ref => <option key={ref.id} value={ref.id}>№{ref.id} · {ref.text.slice(0, 100)}</option>)}</select></Field>
        <Field label="Текст варіації"><textarea required rows={3} minLength={5} maxLength={4000} value={variantText} onChange={e => setVariantText(e.target.value)}/></Field>
        {variantAction.error && <Notice>{variantAction.error}</Notice>}{variantAction.success && <Notice success>{variantAction.success}</Notice>}
        <div><button className="button secondary" disabled={variantAction.pending}><Plus size={16}/> Запропонувати варіацію</button></div>
      </form>}
    </Panel>
  </>
}

function StudentQuestion({ item }: { item: Question }) {
  const [answer, setAnswer] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  const action = useAction()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  return <>
    <Header title="Текстове завдання" subtitle={item.course_name} back={{ to: '/questions', label: 'Завдання' }}
      action={item.demo && <Demo/>}/>
    <Panel title="Питання"><div className="panel-body"><p className="question-prompt">{item.text}</p><span className="muted">Складність · {labels[item.difficulty]}</span></div></Panel>
    <Panel title="Ваша відповідь"><form className="panel-body stack" onSubmit={e => {
      e.preventDefault()
      void action.run(async () => {
        const submission = await api<Submission>('/submissions', 'POST', { question_id: item.id, answer_text: answer, request_id: requestId })
        await queryClient.invalidateQueries()
        navigate(`/submissions/${submission.id}?sent=1`)
      })
    }}>
      <Field label="Текст відповіді"><textarea rows={8} required maxLength={item.max_answer_length} value={answer}
        onChange={e => { setAnswer(e.target.value); setRequestId(crypto.randomUUID()) }} placeholder="Введіть відповідь своїми словами."/></Field>
      <div className="form-actions"><span className="muted">{Array.from(answer).length} / {item.max_answer_length} символів</span>
        <button className="button primary" disabled={action.pending || !answer.trim()}>Надіслати відповідь <ArrowRight size={17}/></button></div>
      {action.error && <Notice>{action.error}</Notice>}
    </form></Panel>
  </>
}

export function QuestionDetail() {
  const user = useOutletContext<User>()
  const { id } = useParams()
  const question = useApi<Question>(`/questions/${id}`)
  if (!question.data) return <QueryState pending={question.isPending} error={question.error}/>
  return user.role === 'student' ? <StudentQuestion item={question.data}/> : <StaffQuestion item={question.data}/>
}
