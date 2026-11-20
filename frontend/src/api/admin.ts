const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface AdminDocumentItem {
  id: string
  source_url: string
  source_type: string
  department_id?: number | null
  department_name?: string | null
  title: string
  notice_sno?: string | null
  notice_date?: string | null
  status: 'fresh' | 'stale' | 'conflicted' | 'archived' | string
  content_hash: string
  chunk_count: number
  ingested_at: string
  last_checked_at: string
}

export interface AdminDocumentsListResponse {
  total: number
  page: number
  limit: number
  documents: AdminDocumentItem[]
}

export interface ConflictDocumentDetail {
  id: string
  title: string
  notice_sno?: string | null
  notice_date?: string | null
  status: string
  source_url: string
  department_name?: string | null
}

export interface ConflictItem {
  id: string
  document_ids: string[]
  detected_at: string
  resolved_by?: string | null
  resolved_at?: string | null
  resolution_note?: string | null
  documents: ConflictDocumentDetail[]
}

export interface RecentQueryItem {
  id: string
  question: string
  answer_preview?: string | null
  confidence_score?: number | null
  feedback?: 'up' | 'down' | null
  created_at: string
}

export interface AnalyticsData {
  total_queries: number
  total_documents: number
  total_chunks: number
  total_sources: number
  unresolved_conflicts: number
  feedback_stats: {
    up_count: number
    down_count: number
    unrated_count: number
    positive_feedback_rate: number
  }
  fallback_rate: number
  recent_queries: RecentQueryItem[]
  top_fallback_questions: string[]
}

// 1. Auth Gate
export async function verifyAdminPasscode(password: string): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/admin/auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ password }),
  })
  if (!res.ok) {
    return false
  }
  const data = await res.json()
  return Boolean(data.authenticated)
}

// 2. Documents Management
export async function getAdminDocuments(
  page = 1,
  limit = 10,
  status = 'all',
  departmentId?: number | null,
  search?: string
): Promise<AdminDocumentsListResponse> {
  const url = new URL(`${API_BASE_URL}/admin/documents`)
  url.searchParams.append('page', page.toString())
  url.searchParams.append('limit', limit.toString())
  if (status && status !== 'all') {
    url.searchParams.append('status', status)
  }
  if (departmentId) {
    url.searchParams.append('department_id', departmentId.toString())
  }
  if (search && search.trim()) {
    url.searchParams.append('search', search.trim())
  }

  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to load documents: ${res.status}`)
  }
  return res.json()
}

export async function reingestDocument(
  documentId: string
): Promise<{ status: string; chunks_count: number; message: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/documents/${documentId}/reingest`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Re-ingestion failed (${res.status})`)
  }
  return res.json()
}

// 3. Conflicts Management
export async function getAdminConflicts(unresolvedOnly = false): Promise<ConflictItem[]> {
  const url = new URL(`${API_BASE_URL}/admin/conflicts`)
  if (unresolvedOnly) {
    url.searchParams.append('unresolved_only', 'true')
  }
  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to load conflicts: ${res.status}`)
  }
  return res.json()
}

export async function resolveConflict(
  conflictId: string,
  authoritativeDocId?: string,
  resolutionType: 'supersede' | 'non_conflicting' | 'dismiss' = 'supersede',
  notes?: string
): Promise<{ status: string; conflict_id: string; resolution_type: string; resolution_note: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/conflicts/${conflictId}/resolve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      authoritative_document_id: authoritativeDocId || null,
      resolution_type: resolutionType,
      notes: notes || null,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Conflict resolution failed (${res.status})`)
  }
  return res.json()
}

// 4. Analytics
export async function getAdminAnalytics(): Promise<AnalyticsData> {
  const res = await fetch(`${API_BASE_URL}/admin/analytics`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to load analytics: ${res.status}`)
  }
  return res.json()
}
