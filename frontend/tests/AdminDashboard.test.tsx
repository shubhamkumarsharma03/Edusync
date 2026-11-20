import { describe, it, expect, vi } from 'vitest'
import {
  verifyAdminPasscode,
  getAdminDocuments,
  resolveConflict,
  reingestDocument,
} from '../src/api/admin'

describe('Admin Dashboard - Phase 6 API & Logic Tests', () => {
  it('verifyAdminPasscode posts to /admin/auth/verify', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: true, message: 'Success' }),
    }) as any

    const isValid = await verifyAdminPasscode('edusync-admin-2026')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/auth/verify'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ password: 'edusync-admin-2026' }),
      })
    )
    expect(isValid).toBe(true)
  })

  it('getAdminDocuments requests documents with pagination and status filters', async () => {
    const mockList = {
      total: 1,
      page: 1,
      limit: 10,
      documents: [
        {
          id: 'doc-123',
          source_url: 'https://ecajmer.ac.in/notice.pdf',
          source_type: 'pdf',
          title: 'Exam Notice',
          status: 'fresh',
          chunk_count: 3,
          ingested_at: '2026-11-20T10:00:00Z',
          last_checked_at: '2026-11-20T10:00:00Z',
        },
      ],
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockList,
    }) as any

    const res = await getAdminDocuments(1, 10, 'fresh', 1, 'Exam')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/admin\/documents\?.*status=fresh.*department_id=1.*search=Exam/),
      expect.anything()
    )
    expect(res.documents.length).toBe(1)
    expect(res.documents[0].status).toBe('fresh')
  })

  it('reingestDocument posts to /admin/documents/{id}/reingest', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', chunks_count: 4, message: 'Done' }),
    }) as any

    const res = await reingestDocument('doc-123')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/documents/doc-123/reingest'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(res.chunks_count).toBe(4)
  })

  it('resolveConflict posts resolution to /admin/conflicts/{id}/resolve', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'success',
        conflict_id: 'conf-1',
        resolution_type: 'supersede',
      }),
    }) as any

    const res = await resolveConflict('conf-1', 'doc-authoritative', 'supersede', 'Superseded')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/conflicts/conf-1/resolve'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          authoritative_document_id: 'doc-authoritative',
          resolution_type: 'supersede',
          notes: 'Superseded',
        }),
      })
    )
    expect(res.status).toBe('success')
  })
})
