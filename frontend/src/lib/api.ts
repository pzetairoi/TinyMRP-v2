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

/**
 * Did this request fail, or was it simply cancelled?
 *
 * Navigating away tears down in-flight requests. On a FULL page load the
 * browser kills them without React ever unmounting, so the rejection lands
 * while the page is still on screen and gets rendered as a failure. Firefox
 * words it "NetworkError when attempting to fetch resource", which is exactly
 * what users reported seeing every time they clicked a BOM link.
 *
 * Nothing went wrong in those cases, so nothing should be shown. A genuine
 * outage still surfaces: it produces a rejection too, but the user is not
 * leaving, so the message stays and is correct.
 */
export function isCancelledRequest(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const name = String((error as { name?: unknown }).name || '')
  if (name === 'AbortError') return true
  const message = String((error as { message?: unknown }).message || '').toLowerCase()
  return (
    message.includes('networkerror when attempting to fetch') ||
    message.includes('the operation was aborted') ||
    message.includes('load failed') ||
    message === 'failed to fetch'
  )
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
