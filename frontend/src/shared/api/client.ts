import i18n from '@/i18n'
import { useSession } from '@/shared/lib/session'

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  json?: unknown
  body?: BodyInit
}

/** Запрос к /api с токеном. Ошибка всегда содержит текст для человека (detail с сервера). */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, headers: rawHeaders, ...init } = options
  const headers = new Headers(rawHeaders)
  const token = useSession.getState().token
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let body = init.body
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(json)
  }

  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...init, headers, body })
  } catch {
    throw new ApiError(0, i18n.t('errors.network'))
  }

  if (response.status === 401 && token) {
    useSession.getState().signOut()
  }

  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    const detail =
      data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string'
        ? data.detail
        : i18n.t('errors.server', { status: response.status })
    throw new ApiError(response.status, detail, data)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
