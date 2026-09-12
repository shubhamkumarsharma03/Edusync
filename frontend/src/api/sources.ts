/**
 * EduSync Admin Sources API Client
 */

export interface IngestionSource {
  id: string
  name: string
  url: string
  department?: string | null
  category: string
  slug?: string | null
  priority: number
  is_active: boolean
  initial_fetch_limit: number
  subsequent_fetch_limit: number
  last_fetched_at?: string | null
  status: 'idle' | 'fetching' | 'completed' | 'error'
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface SourceCreatePayload {
  name: string
  url: string
  department?: string
  category?: string
  slug?: string
  priority?: number
  is_active?: boolean
  initial_fetch_limit?: number
  subsequent_fetch_limit?: number
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function getSources(): Promise<IngestionSource[]> {
  const res = await fetch(`${API_BASE_URL}/admin/sources`, {
    headers: { 'Accept': 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to fetch sources: ${res.status}`)
  }
  return res.json()
}

export async function createSource(payload: SourceCreatePayload): Promise<IngestionSource> {
  const res = await fetch(`${API_BASE_URL}/admin/sources`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Failed to create source: ${res.status}`)
  }
  return res.json()
}

export async function updateSource(
  id: string,
  payload: Partial<SourceCreatePayload>
): Promise<IngestionSource> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Failed to update source: ${res.status}`)
  }
  return res.json()
}

export async function deleteSource(id: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/${id}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    throw new Error(`Failed to delete source: ${res.status}`)
  }
}

export async function reorderSources(
  items: { id: string; priority: number }[]
): Promise<IngestionSource[]> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/reorder`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ items }),
  })
  if (!res.ok) {
    throw new Error(`Failed to reorder sources: ${res.status}`)
  }
  return res.json()
}

export async function triggerFetchSource(id: string): Promise<{ status: string; task_id: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/${id}/fetch`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to trigger fetch: ${res.status}`)
  }
  return res.json()
}

export async function triggerFetchAll(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/fetch-all`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to trigger fetch all: ${res.status}`)
  }
  return res.json()
}

export async function seedDefaultSources(): Promise<IngestionSource[]> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/seed-defaults`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw new Error(`Failed to seed default sources: ${res.status}`)
  }
  return res.json()
}

export interface IngestedDocumentItem {
  id: string
  source_url: string
  source_type: string
  department?: string | null
  title: string
  notice_sno?: string | null
  notice_date?: string | null
  content_hash: string
  status: string
  chunk_count: number
  ingested_at: string
  last_checked_at: string
  preview?: string | null
}

export interface IngestedDocumentsResponse {
  total: number
  page: number
  limit: number
  source_id: string
  source_name: string
  documents: IngestedDocumentItem[]
}

export interface DocumentChunkItem {
  id: string
  token_count: number
  last_verified: string
  content: string
}

export async function getSourceDocuments(
  sourceId: string,
  page: number = 1,
  limit: number = 10,
  search?: string
): Promise<IngestedDocumentsResponse> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  })
  if (search && search.trim()) {
    params.append('search', search.trim())
  }
  const res = await fetch(`${API_BASE_URL}/admin/sources/${sourceId}/documents?${params.toString()}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch source documents: ${res.status}`)
  }
  return res.json()
}

export async function getDocumentChunks(
  sourceId: string,
  documentId: string
): Promise<DocumentChunkItem[]> {
  const res = await fetch(`${API_BASE_URL}/admin/sources/${sourceId}/documents/${documentId}/chunks`)
  if (!res.ok) {
    throw new Error(`Failed to fetch document chunks: ${res.status}`)
  }
  return res.json()
}

export async function getSourceLiveFeed(
  sourceId: string,
  page: number = 1,
  limit: number = 10,
  search: string = ''
): Promise<{ success: boolean; data: any[]; pagination?: { totalItems: number } }> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
    search,
  })
  const res = await fetch(`${API_BASE_URL}/admin/sources/${sourceId}/live-feed?${params.toString()}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch live feed: ${res.status}`)
  }
  return res.json()
}

export interface ActiveDocumentInfo {
  title: string
  filename: string
  url: string
  source_type: string
  page?: number | null
  total_pages?: number | null
  size_kb?: number | null
}

export interface PipelineLogEntry {
  timestamp: string
  level: 'info' | 'fetch' | 'ocr' | 'chunk' | 'embed' | 'bypass' | 'warn' | 'error' | 'success'
  message: string
  tag?: string | null
}

export interface PipelineProgressState {
  source_id?: string | null
  source_name: string
  status: 'idle' | 'fetching' | 'completed' | 'error'
  phase: string
  step_index: number
  total_steps: number
  current_action: string
  next_action: string
  active_document?: ActiveDocumentInfo | null
  stats: {
    checked: number
    total: number
    ocr_count: number
    chunks_count: number
    bypassed_count: number
    created_count: number
    updated_count: number
  }
  logs: PipelineLogEntry[]
  started_at?: string | null
  updated_at?: string | null
}

export async function getLiveProgress(sourceId?: string): Promise<PipelineProgressState> {
  const url = sourceId
    ? `${API_BASE_URL}/admin/sources/${sourceId}/live-progress`
    : `${API_BASE_URL}/admin/sources/live-progress`
  const res = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!res.ok) {
    throw new Error(`Failed to fetch live progress: ${res.status}`)
  }
  return res.json()
}

