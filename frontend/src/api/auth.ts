import { API_BASE_URL } from './client'

const TOKEN_KEY = 'edusync_auth_token'

export interface StudentProfile {
  id: string
  college_roll_no: string
  email: string
  full_name: string
  branch: string
  semester: number
  degree: string
  admission_year: number
  role: string
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  student: StudentProfile
}

export interface RegisterPayload {
  college_roll_no: string
  email: string
  full_name: string
  branch: string
  semester: number
  degree?: string
  admission_year?: number
  password: string
}

export interface LoginPayload {
  identifier: string
  password: string
}

const memoryStorage = new Map<string, string>()

function getStorage() {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage
  }
  if (typeof globalThis !== 'undefined' && (globalThis as any).localStorage) {
    return (globalThis as any).localStorage
  }
  return {
    getItem: (k: string) => memoryStorage.get(k) || null,
    setItem: (k: string, v: string) => {
      memoryStorage.set(k, v)
    },
    removeItem: (k: string) => {
      memoryStorage.delete(k)
    },
    clear: () => {
      memoryStorage.clear()
    },
  }
}

export function getAuthToken(): string | null {
  try {
    return getStorage().getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setAuthToken(token: string): void {
  try {
    getStorage().setItem(TOKEN_KEY, token)
  } catch {}
}

export function clearAuthToken(): void {
  try {
    getStorage().removeItem(TOKEN_KEY)
  } catch {}
}

export async function registerStudent(payload: RegisterPayload): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Registration failed.' }))
    throw new Error(err.detail || 'Registration failed.')
  }

  const data: AuthResponse = await res.json()
  setAuthToken(data.access_token)
  return data
}

export async function loginStudent(payload: LoginPayload): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Invalid credentials.' }))
    throw new Error(err.detail || 'Invalid roll number or password.')
  }

  const data: AuthResponse = await res.json()
  setAuthToken(data.access_token)
  return data
}

export async function fetchCurrentStudent(): Promise<StudentProfile | null> {
  const token = getAuthToken()
  if (!token) return null

  try {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })

    if (!res.ok) {
      clearAuthToken()
      return null
    }

    return await res.json()
  } catch {
    return null
  }
}
