import { describe, it, expect, vi } from 'vitest'
import {
  verifyAdminPasscode,
  getAdminDocuments,
  resolveConflict,
  reingestDocument,
  updateDocumentStatus,
  deleteDocument,
  bulkActionDocuments,
  compareConflictDocuments,
  reopenConflict,
  updateDocumentMetadata,
  manualUploadDocument,
  testSourceUrl,
  getSystemToolsHealth,
  runRAGPlayground,
  triggerCorpusSync,
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

  it('resolveConflict supports archive_both resolution', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'success',
        conflict_id: 'conf-1',
        resolution_type: 'archive_both',
      }),
    }) as any

    const res = await resolveConflict('conf-1', undefined, 'archive_both', 'Both obsolete')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/conflicts/conf-1/resolve'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          authoritative_document_id: null,
          resolution_type: 'archive_both',
          notes: 'Both obsolete',
        }),
      })
    )
    expect(res.resolution_type).toBe('archive_both')
  })

  it('updateDocumentStatus patches document status', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', document_id: 'doc-1', new_status: 'archived' }),
    }) as any

    const res = await updateDocumentStatus('doc-1', 'archived')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/documents/doc-1/status'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ status: 'archived' }),
      })
    )
    expect(res.new_status).toBe('archived')
  })

  it('bulkActionDocuments posts bulk actions', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', action: 'update_status', affected_count: 2 }),
    }) as any

    const res = await bulkActionDocuments(['d1', 'd2'], 'update_status', 'fresh')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/documents/bulk-action'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          document_ids: ['d1', 'd2'],
          action: 'update_status',
          target_status: 'fresh',
        }),
      })
    )
    expect(res.affected_count).toBe(2)
  })

  it('compareConflictDocuments and reopenConflict work correctly', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ conflict_id: 'c1', documents: [] }),
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success', message: 'Reopened' }),
    }) as any

    const comp = await compareConflictDocuments('c1')
    expect(comp.conflict_id).toBe('c1')

    const reopen = await reopenConflict('c1')
    expect(reopen.status).toBe('success')
  })

  it('updateDocumentMetadata puts updated metadata', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', document_id: 'doc-1', updated_fields: { title: 'New Title' } }),
    }) as any

    const res = await updateDocumentMetadata('doc-1', { title: 'New Title' })
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/documents/doc-1'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ title: 'New Title' }),
      })
    )
    expect(res.status).toBe('success')
  })

  it('manualUploadDocument posts direct notice for chunking and embedding', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', document_id: 'doc-manual', chunks_count: 3 }),
    }) as any

    const res = await manualUploadDocument({
      title: 'Manual Notice',
      content: 'This is the body of the notice.',
      department_id: 1,
    })
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/documents/manual-upload'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          title: 'Manual Notice',
          content: 'This is the body of the notice.',
          department_id: 1,
        }),
      })
    )
    expect(res.chunks_count).toBe(3)
  })

  it('testSourceUrl tests ECA web connectivity', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        url: 'https://ecajmer.ac.in/departments/cs-it/circulars',
        is_valid: true,
        status_code: 200,
        notices_found: 10,
        sample_titles: [],
        message: 'Success',
      }),
    }) as any

    const res = await testSourceUrl('https://ecajmer.ac.in/departments/cs-it/circulars')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/admin/sources/test-url'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ url: 'https://ecajmer.ac.in/departments/cs-it/circulars' }),
      })
    )
    expect(res.is_valid).toBe(true)
    expect(res.notices_found).toBe(10)
  })

  it('getSystemToolsHealth and runRAGPlayground work properly', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        db_ping_ms: 1.2,
        pgvector_extension: true,
        total_documents: 207,
        total_chunks: 538,
        total_sources: 22,
        unresolved_conflicts: 0,
      }),
    }).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        query: 'When are mid-term exams?',
        passed_gate: true,
        confidence_score: 0.88,
        retrieved_chunks: [],
      }),
    }) as any

    const health = await getSystemToolsHealth()
    expect(health.pgvector_extension).toBe(true)
    expect(health.total_documents).toBe(207)

    const diag = await runRAGPlayground('When are mid-term exams?')
    expect(diag.passed_gate).toBe(true)
    expect(diag.confidence_score).toBe(0.88)
  })
})
