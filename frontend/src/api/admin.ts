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
  status: 'fresh' | 'stale' | 'conflicted' | 'pending' | 'archived' | string
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

export interface DocumentChunkItem {
  id: string
  document_id: string
  content: string
  original_content?: string | null
  token_count: number
  last_verified: string
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

export interface ConflictCompareDocument extends ConflictDocumentDetail {
  chunks: DocumentChunkItem[]
}

export interface ConflictCompareResponse {
  conflict_id: string
  detected_at: string
  resolution_note?: string | null
  documents: ConflictCompareDocument[]
}

export interface RecentQueryItem {
  id: string
  question: string
  answer_preview?: string | null
  confidence_score?: number | null
  feedback?: 'up' | 'down' | null
  created_at: string
}

export interface ConfidenceTierBreakdown {
  high_count: number
  medium_count: number
  low_count: number
  high_percentage: number
  medium_percentage: number
  low_percentage: number
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
  confidence_distribution?: {
    high_count: number
    medium_count: number
    low_count: number
    high_percentage: number
    medium_percentage: number
    low_percentage: number
  } | null
}

export interface DiagnosticChunkItem {
  chunk_id: string
  document_id: string
  title: string
  department?: string | null
  source_url: string
  content_snippet: string
  vector_score?: number | null
  keyword_score?: number | null
  rrf_score: number
  rerank_score?: number | null
  rank: number
}

export interface RAGPlaygroundResponse {
  query: string
  execution_time_ms: number
  passed_gate: boolean
  confidence_level: 'high' | 'medium' | 'low' | string
  confidence_score: number
  is_fallback: boolean
  fallback_message?: string | null
  chunks: DiagnosticChunkItem[]
}

export interface SystemHealthData {
  status: string
  db_ping_ms: number
  total_documents: number
  total_chunks: number
  total_sources: number
  unresolved_conflicts: number
  pgvector_installed: boolean
}

export interface TestUrlResponse {
  is_valid: boolean
  status_code: number
  notices_found: number
  sample_titles: string[]
  message: string
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

export async function updateDocumentStatus(
  documentId: string,
  newStatus: string
): Promise<{ status: string; document_id: string; new_status: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/documents/${documentId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ status: newStatus }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Status update failed (${res.status})`)
  }
  return res.json()
}

export async function updateDocumentMetadata(
  documentId: string,
  payload: {
    title?: string
    notice_sno?: string
    notice_date?: string
    department_id?: number
    status?: string
  }
): Promise<{ status: string; document_id: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/documents/${documentId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Metadata update failed (${res.status})`)
  }
  return res.json()
}

export async function manualUploadDocument(payload: {
  title: string
  content: string
  notice_sno?: string
  notice_date?: string
  department_id?: number
  source_url?: string
}): Promise<{ status: string; document_id: string; title: string; chunks_count: number; message: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/documents/manual-upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Manual upload failed (${res.status})`)
  }
  return res.json()
}

export async function getDocumentChunks(documentId: string): Promise<DocumentChunkItem[]> {
  const res = await fetch(`${API_BASE_URL}/admin/documents/${documentId}/chunks`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to fetch chunks (${res.status})`)
  }
  return res.json()
}

export async function deleteDocument(
  documentId: string
): Promise<{ status: string; document_id: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/documents/${documentId}`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to delete document (${res.status})`)
  }
  return res.json()
}

export async function bulkActionDocuments(
  documentIds: string[],
  action: 'reingest' | 'update_status' | 'delete',
  targetStatus?: string
): Promise<{ status: string; action: string; affected_count: number; new_status?: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/documents/bulk-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      document_ids: documentIds,
      action,
      target_status: targetStatus || null,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Bulk action failed (${res.status})`)
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
  resolutionType: 'supersede' | 'non_conflicting' | 'archive_both' | 'drop_both' | 'dismiss' = 'supersede',
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

export async function reopenConflict(
  conflictId: string
): Promise<{ status: string; conflict_id: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/conflicts/${conflictId}/reopen`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to reopen conflict (${res.status})`)
  }
  return res.json()
}

export async function compareConflictDocuments(
  conflictId: string
): Promise<ConflictCompareResponse> {
  const res = await fetch(`${API_BASE_URL}/admin/conflicts/${conflictId}/compare`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to compare conflict documents (${res.status})`)
  }
  return res.json()
}

// 4. Analytics
export async function getAdminAnalytics(queryFilter = 'all'): Promise<AnalyticsData> {
  const url = new URL(`${API_BASE_URL}/admin/analytics`)
  if (queryFilter && queryFilter !== 'all') {
    url.searchParams.append('query_filter', queryFilter)
  }
  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to load analytics: ${res.status}`)
  }
  return res.json()
}

export function getExportAnalyticsCsvUrl(): string {
  return `${API_BASE_URL}/admin/analytics/export`
}

// 5. System Tools & Sources
export async function getSystemToolsHealth(): Promise<SystemHealthData> {
  const res = await fetch(`${API_BASE_URL}/admin/tools/health`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to load system health: ${res.status}`)
  }
  return res.json()
}

export async function runRAGPlayground(
  query: string,
  department?: string,
  topK = 5
): Promise<RAGPlaygroundResponse> {
  const res = await fetch(`${API_BASE_URL}/admin/tools/rag-playground`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ query, department: department || null, top_k: topK }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Playground search failed (${res.status})`)
  }
  return res.json()
}

export async function triggerCorpusSync(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/tools/sync-all-sources`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Corpus sync trigger failed (${res.status})`)
  }
  return res.json()
}

export async function testSourceUrl(url: string): Promise<TestUrlResponse> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/test-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Test URL failed (${res.status})`)
  }
  return res.json()
}
