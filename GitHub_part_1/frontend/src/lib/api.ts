import { useQuery } from '@tanstack/react-query'
import type { Page } from './types'

const base = '/api/v1'
type Params = Record<string, string | number | boolean | undefined>

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) { super(message) }
}

export function withParams(path: string, params: Params) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== '' && value !== undefined) query.set(key, String(value))
  }
  return query.size ? `${path}?${query}` : path
}

let refreshRequest: Promise<boolean> | null = null

function refresh() {
  if (!refreshRequest) {
    refreshRequest = fetch(base + '/auth/refresh', {
      method: 'POST', credentials: 'same-origin', headers: { 'X-EMPI-Request': '1' },
    }).then(response => response.ok, () => false).finally(() => { refreshRequest = null })
  }
  return refreshRequest
}

export async function api<T>(path: string, method = 'GET', data?: unknown, signal?: AbortSignal): Promise<T> {
  const send = () => fetch(base + path, {
    method, credentials: 'same-origin', signal,
    headers: { 'X-EMPI-Request': '1', ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: data === undefined ? undefined : JSON.stringify(data),
  })
  let response: Response
  try {
    response = await send()
    if (response.status === 401 && path !== '/auth/login' && path !== '/auth/logout' && await refresh()) {
      response = await send()
    }
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError(0, 'З’єднання із сервером перервано. Спробуйте ще раз.')
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok || payload === null) {
    const error = payload?.error
    if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('empi:signed-out'))
    throw new ApiError(response.status, error?.message ?? 'Сервіс тимчасово недоступний.', error?.code)
  }
  return payload as T
}

export function useApi<T>(path: string, enabled = true, polling?: number) {
  return useQuery({
    queryKey: [path], queryFn: ({ signal }) => api<T>(path, 'GET', undefined, signal),
    enabled, refetchInterval: polling,
  })
}

export function usePage<T>(path: string, params: Params = {}, enabled = true, polling?: number) {
  return useApi<Page<T>>(withParams(path, params), enabled, polling)
}
