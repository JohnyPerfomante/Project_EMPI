import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, withParams } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('REST client', () => {
  it('encodes Ukrainian query values and preserves false and zero', () => {
    const url = new URL(withParams('/questions', { q: 'система & мережа', offset: 0, active: false, status: '' }), 'https://example.org')
    expect(url.searchParams.get('q')).toBe('система & мережа')
    expect(url.searchParams.get('offset')).toBe('0')
    expect(url.searchParams.get('active')).toBe('false')
    expect(url.searchParams.has('status')).toBe(false)
  })

  it('uses a protected same-origin request and returns validation errors', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'invalid_answer', message: 'Введіть текст.' },
    }), { status: 422 }))
    vi.stubGlobal('fetch', request)
    await expect(api('/submissions', 'POST', { answer_text: '' })).rejects.toMatchObject({
      status: 422, code: 'invalid_answer', message: 'Введіть текст.',
    } satisfies Partial<ApiError>)
    expect(request.mock.calls[0][1]).toMatchObject({ credentials: 'same-origin', headers: { 'X-EMPI-Request': '1' } })
  })

  it('refreshes an expired cookie and retries the original read', async () => {
    const request = vi.fn()
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response('{}', { status: 200 }))
      .mockResolvedValueOnce(new Response('{"role":"teacher"}', { status: 200 }))
    vi.stubGlobal('fetch', request)
    await expect(api('/auth/me')).resolves.toEqual({ role: 'teacher' })
    expect(request.mock.calls.map(([path]) => path)).toEqual(['/api/v1/auth/me', '/api/v1/auth/refresh', '/api/v1/auth/me'])
  })
})
