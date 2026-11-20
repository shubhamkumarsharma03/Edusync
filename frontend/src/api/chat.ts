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
}

export async function sendChatMessage(
  query: string,
  department?: string | null,
  history?: ChatMessage[],
  timeoutMs: number = 30000
): Promise<ChatResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      signal: controller.signal,
      body: JSON.stringify({
        query,
        department: department && department !== 'all' ? department : null,
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
  feedback: 'up' | 'down'
): Promise<{ status: string; query_id: string; feedback: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        query_id: queryId,
        feedback,
      }),
    })

    if (!response.ok) {
      // Fallback attempt to root /feedback if needed
      const fallbackRes = await fetch(`${API_BASE_URL}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          query_id: queryId,
          feedback,
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
