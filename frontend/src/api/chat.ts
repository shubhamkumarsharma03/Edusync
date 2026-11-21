import { getAuthToken } from './auth'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface SourceCitation {
  title: string
  url?: string
  department?: string
  last_verified?: string
  confidence_score?: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  answer: string
  sources: SourceCitation[]
  confidence: 'high' | 'medium' | 'low' | string
  confidence_score: number
  is_fallback: boolean
  query: string
  query_id?: string
  suggestions?: string[]
}

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  }
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

export async function sendChatMessage(
  query: string,
  department?: string | null,
  history?: ChatMessage[],
  sessionId?: string | null,
  timeoutMs: number = 30000
): Promise<ChatResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      signal: controller.signal,
      body: JSON.stringify({
        query,
        department: department && department !== 'all' ? department : null,
        session_id: sessionId || null,
        history: history || [],
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `Chat request failed with status: ${response.status}`)
    }

    return await response.json()
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out while waiting for verified college notices. Please try again.')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export async function sendChatFeedback(
  queryId: string,
  feedback: 'up' | 'down',
  issueTag?: string | null,
  studentComment?: string | null
): Promise<{ status: string; query_id: string; feedback: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/feedback`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        query_id: queryId,
        feedback,
        issue_tag: issueTag || null,
        student_comment: studentComment || null,
      }),
    })

    if (!response.ok) {
      const fallbackRes = await fetch(`${API_BASE_URL}/feedback`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          query_id: queryId,
          feedback,
          issue_tag: issueTag || null,
          student_comment: studentComment || null,
        }),
      })
      if (!fallbackRes.ok) {
        throw new Error(`Feedback failed (${response.status})`)
      }
      return fallbackRes.json()
    }

    return response.json()
  } catch (err: any) {
    console.error('Feedback submission failed:', err)
    throw err
  }
}

// ----------------- Chat Session & Multi-User API -----------------

export interface ChatSessionSummary {
  id: string
  student_id: string
  title: string
  is_pinned: boolean
  is_archived: boolean
  created_at: string
  updated_at: string
  message_count: number
  last_message_preview?: string | null
}

export interface ChatSessionDetail {
  id: string
  student_id: string
  title: string
  is_pinned: boolean
  is_archived: boolean
  created_at: string
  updated_at: string
  messages: any[]
  metadata?: Record<string, any>
}

export async function fetchChatSessions(
  studentId: string = 'student_guest',
  isArchived?: boolean
): Promise<ChatSessionSummary[]> {
  try {
    const params = new URLSearchParams()
    if (studentId) params.set('student_id', studentId)
    if (typeof isArchived === 'boolean') {
      params.set('is_archived', String(isArchived))
    }
    const res = await fetch(
      `${API_BASE_URL}/chat/sessions?${params.toString()}`,
      { headers: getAuthHeaders() }
    )
    if (!res.ok) return []
    return await res.json()
  } catch (err) {
    console.warn('Failed to fetch chat sessions from server:', err)
    return []
  }
}

export async function createChatSession(
  studentId: string = 'student_guest',
  title: string = 'New Chat',
  messages: any[] = []
): Promise<ChatSessionDetail | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ student_id: studentId, title, messages }),
    })
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Failed to create server chat session:', err)
    return null
  }
}

export async function fetchChatSession(sessionId: string): Promise<ChatSessionDetail | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
      headers: getAuthHeaders(),
    })
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Failed to fetch server chat session detail:', err)
    return null
  }
}

export async function updateChatSession(
  sessionId: string,
  updates: {
    title?: string
    is_pinned?: boolean
    is_archived?: boolean
    messages?: any[]
  }
): Promise<ChatSessionDetail | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(updates),
    })
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Failed to update server chat session:', err)
    return null
  }
}

export async function deleteChatSession(sessionId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    })
    return res.ok
  } catch (err) {
    console.warn('Failed to delete server chat session:', err)
    return false
  }
}

export async function togglePinChatSession(sessionId: string): Promise<ChatSessionDetail | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/pin`, {
      method: 'POST',
      headers: getAuthHeaders(),
    })
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Failed to toggle pin on server session:', err)
    return null
  }
}

export async function toggleArchiveChatSession(
  sessionId: string
): Promise<ChatSessionDetail | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/archive`, {
      method: 'POST',
      headers: getAuthHeaders(),
    })
    if (!res.ok) return null
    return await res.json()
  } catch (err) {
    console.warn('Failed to toggle archive on server session:', err)
    return null
  }
}
