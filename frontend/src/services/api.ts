import type { Role, User } from '../types'

const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api'
const SESSION_KEY = 'p2p-session'
export type Session = { access_token: string; user: User }

export function getSession(): Session | null {
  try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? 'null') as Session | null } catch { return null }
}

export function saveSession(session: Session | null) {
  if (session) sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  else sessionStorage.removeItem(SESSION_KEY)
}

export async function signIn(username: Role, password = `demo-${username}`): Promise<Session> {
  const response = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail ?? 'Sign in failed')
  return { access_token: data.access_token as string, user: data.user as User }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = getSession()
  const headers = new Headers(options.headers)
  if (session?.access_token) headers.set('Authorization', `Bearer ${session.access_token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API}${path}`, { ...options, headers })
  if (response.status === 204) return undefined as T
  const type = response.headers.get('content-type') ?? ''
  const body = type.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) throw new Error(typeof body === 'object' ? (body.detail ?? 'Request failed') : body || 'Request failed')
  return body as T
}

export const send = <T>(path: string, body: unknown, method = 'POST') => request<T>(path, { method, body: JSON.stringify(body) })
export async function downloadCsv(path: string, filename: string) {
  const content = await request<string>(path)
  const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url)
}
export const money = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100)
export const dateLabel = (value: string) => new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
