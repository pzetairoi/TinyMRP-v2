export type ApiError = {
  code?: string
  message: string
  details?: string[]
}

function normalizedApiError(data: any, status: number): ApiError {
  const payload = data?.error
  if (payload && typeof payload === 'object') {
    return {
      code: typeof payload.code === 'string' ? payload.code : undefined,
      message: payload.message || `Request failed (${status})`,
      details: Array.isArray(payload.details) ? payload.details : [],
    }
  }
  return {
    code: typeof payload === 'string' ? payload : undefined,
    message: data?.message || (typeof payload === 'string' ? payload : `Request failed (${status})`),
    details: Array.isArray(data?.details) ? data.details : [],
  }
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'message' in error) {
    const message = String((error as { message?: unknown }).message || '').trim()
    if (message) return message
  }
  return fallback
}

export async function readApiResponse<T = any>(res: Response): Promise<T> {
  const text = await res.text()
  let data: any = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch (err) {
      if (!res.ok) throw { message: `Request failed (${res.status})` } as ApiError
      throw { message: `Invalid JSON response: ${String(err)}` } as ApiError
    }
  }

  if (!res.ok || (data && data.ok === false)) {
    throw normalizedApiError(data, res.status)
  }
  return data as T
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })
  return readApiResponse<T>(res)
}
