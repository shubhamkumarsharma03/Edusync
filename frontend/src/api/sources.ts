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
