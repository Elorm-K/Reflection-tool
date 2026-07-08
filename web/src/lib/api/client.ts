export interface ApiError {
  status: number
  detail: string
}

let authToken: string | null = sessionStorage.getItem('gm_token')
let authRole: 'student' | 'instructor' | null = sessionStorage.getItem('gm_role') as
  | 'student'
  | 'instructor'
  | null

export function setAuth(token: string, role: 'student' | 'instructor') {
  authToken = token
  authRole = role
  sessionStorage.setItem('gm_token', token)
  sessionStorage.setItem('gm_role', role)
}

export function clearAuth() {
  authToken = null
  authRole = null
  sessionStorage.removeItem('gm_token')
  sessionStorage.removeItem('gm_role')
}

export function getRole() {
  return authToken ? authRole : null
}

export async function api<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const resp = await fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const data = await resp.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* non-JSON error body */
    }
    throw { status: resp.status, detail } satisfies ApiError
  }
  return resp.json() as Promise<T>
}
