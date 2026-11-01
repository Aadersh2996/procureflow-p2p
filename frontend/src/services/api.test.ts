import { beforeEach, describe, expect, it, vi } from 'vitest'
import { dateLabel, getSession, money, request, saveSession, signIn } from './api'

describe('API utilities', () => {
  beforeEach(() => { sessionStorage.clear() })

  it('formats paise as Indian rupees', () => expect(money(123456)).toContain('₹1,235'))
  it('formats zero value', () => expect(money(0)).toContain('₹0'))
  it('formats a date for the Indian locale', () => expect(dateLabel('2026-11-01')).toMatch(/01 Nov 2026/))
  it('stores and reads a signed session payload', () => {
    const session = { access_token: 'token', user: { username: 'ap', role: 'ap' as const } }
    saveSession(session); expect(getSession()).toEqual(session)
  })
  it('clears the session on sign out', () => { saveSession({ access_token: 'x', user: { username: 'viewer', role: 'viewer' } }); saveSession(null); expect(getSession()).toBeNull() })
  it('sends a bearer token with API requests', async () => {
    saveSession({ access_token: 'session-token', user: { username: 'ap', role: 'ap' } })
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }))
    await expect(request<{ ok: boolean }>('/health')).resolves.toEqual({ ok: true })
    expect(new Headers(fetch.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer session-token')
  })
  it('turns API validation details into readable errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Supplier code already exists' }), { status: 409, headers: { 'content-type': 'application/json' } }))
    await expect(request('/suppliers')).rejects.toThrow('Supplier code already exists')
  })
  it('obtains a role session from the login endpoint', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ access_token: 'new-token', token_type: 'bearer', user: { username: 'ap', role: 'ap' } }), { status: 200, headers: { 'content-type': 'application/json' } }))
    await expect(signIn('ap')).resolves.toMatchObject({ access_token: 'new-token', user: { role: 'ap' } })
    expect(JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))).toEqual({ username: 'ap', password: 'demo-ap' })
  })
})
