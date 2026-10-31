const BASE_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed (${status})`)
    this.status = status
    this.detail = detail
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail ?? body
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function apiGet<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`${BASE_URL}${path}`))
}

/** Every mutating request carries X-JobPilot: 1, which the API requires (CSRF guard). */
export async function apiSend<T>(method: string, path: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData
  const headers: Record<string, string> = { 'X-JobPilot': '1' }
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  return parse<T>(
    await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    }),
  )
}
