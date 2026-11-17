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
  confidence: string
  confidence_score: number
  is_fallback: boolean
  query: string
}

export async function sendChatMessage(
  query: string,
  department?: string,
  history?: ChatMessage[]
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      query,
      department: department || null,
      history: history || [],
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `Chat request failed with status: ${response.status}`)
  }

  return response.json()
}
