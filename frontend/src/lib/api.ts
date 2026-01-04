export type ApiError = {
  code?: string
  message: string
  details?: string[]
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const text = await res.text()
  let data: any = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch (err) {
      throw { message: `Invalid JSON response: ${String(err)}` } as ApiError
    }
  }

  if (!res.ok || (data && data.ok === false)) {
    const error = data?.error || {}
    const message = error.message || `Request failed (${res.status})`
    const details = error.details || []
    throw { code: error.code, message, details } as ApiError
  }

  return data as T
}
