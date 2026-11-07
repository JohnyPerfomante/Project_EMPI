export const roleLabels = { student: 'Студент', teacher: 'Викладач', admin: 'Адміністратор' } as const
export const labels: Record<string, string> = {
  draft: 'Чернетка', published: 'Опубліковано', archived: 'Архів',
  proposed: 'Очікує перевірки', approved: 'Затверджено', rejected: 'Відхилено', partial: 'Частково правильно',
  queued: 'У черзі', processing: 'Аналізується', analyzed: 'Проаналізовано', failed: 'Помилка аналізу',
  HIGH_MATCH: 'Висока відповідність', NEEDS_REVIEW: 'Потребує перевірки', LOW_MATCH: 'Низька відповідність',
  easy: 'Базовий', medium: 'Середній', hard: 'Високий', automatic: 'Одразу після аналізу',
  reviewed: 'Після рішення викладача', hidden: 'Прихований', active: 'Активний', blocked: 'Заблоковано',
  correct: 'Зараховано', incorrect: 'Не зараховано',
}

export const date = (value: string, withTime = false) => new Intl.DateTimeFormat('uk-UA', {
  dateStyle: 'medium', timeStyle: withTime ? 'short' : undefined, timeZone: 'Europe/Kyiv',
}).format(new Date(value))
export const percent = (value: number | null) => value === null ? '—' : `${Math.round(value * 100)}%`
export const initials = (name: string) => name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
export const errorMessage = (value: unknown) => value instanceof Error ? value.message : 'Дію не вдалося виконати.'
