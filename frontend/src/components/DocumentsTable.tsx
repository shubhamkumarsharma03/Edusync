import React, { useState, useEffect } from 'react'
import {
  Search,
  ExternalLink,
  RotateCw,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Layers,
  X,
  FileText,
  CheckSquare,
  Square,
  Plus,
  Edit2,
} from 'lucide-react'
import {
  AdminDocumentItem,
  DocumentChunkItem,
  getAdminDocuments,
  reingestDocument,
  updateDocumentStatus,
  getDocumentChunks,
  deleteDocument,
  bulkActionDocuments,
  updateDocumentMetadata,
  manualUploadDocument,
} from '../api/admin'
import { Department, getDepartments } from '../api/departments'

export const DocumentsTable: React.FC = () => {
  const [documents, setDocuments] = useState<AdminDocumentItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [reingestingId, setReingestingId] = useState<string | null>(null)
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  // Filters
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedDeptId, setSelectedDeptId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [departments, setDepartments] = useState<Department[]>([])

  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Selection & Bulk Actions
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const [bulkActionLoading, setBulkActionLoading] = useState(false)

  // Chunk Modal State
  const [chunkModalDoc, setChunkModalDoc] = useState<AdminDocumentItem | null>(null)
  const [chunks, setChunks] = useState<DocumentChunkItem[]>([])
  const [chunksLoading, setChunksLoading] = useState(false)

  // Delete Confirm Modal State
  const [deletingDoc, setDeletingDoc] = useState<AdminDocumentItem | null>(null)
  const [deletingLoading, setDeletingLoading] = useState(false)

  // Edit Metadata Modal State
  const [editingDoc, setEditingDoc] = useState<AdminDocumentItem | null>(null)
  const [editFormData, setEditFormData] = useState<{
    title: string
    notice_sno: string
    notice_date: string
    department_id: number | undefined
  }>({ title: '', notice_sno: '', notice_date: '', department_id: undefined })
  const [editLoading, setEditLoading] = useState(false)

  // Manual Notice Upload Modal State
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [uploadFormData, setUploadFormData] = useState<{
    title: string
    notice_sno: string
    notice_date: string
    department_id: number | undefined
    source_url: string
    content: string
  }>({
    title: '',
    notice_sno: '',
    notice_date: '',
    department_id: undefined,
    source_url: '',
    content: '',
  })
  const [uploadLoading, setUploadLoading] = useState(false)

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 4000)
  }

  const loadDocs = async () => {
    try {
      setLoading(true)
      const data = await getAdminDocuments(
        currentPage,
        pageSize,
        statusFilter,
        selectedDeptId,
        searchQuery
      )
      setDocuments(data.documents)
      setTotal(data.total)
    } catch (err: any) {
      showToast(err.message || 'Failed to load documents', 'error')
      setDocuments([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    getDepartments()
      .then(setDepartments)
      .catch((err) => console.warn('Could not load departments filter:', err))
  }, [])

  useEffect(() => {
    loadDocs()
    setSelectedDocIds([])
  }, [currentPage, pageSize, statusFilter, selectedDeptId])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setCurrentPage(1)
    loadDocs()
  }

  const handleReingest = async (doc: AdminDocumentItem) => {
    try {
      setReingestingId(doc.id)
      const res = await reingestDocument(doc.id)
      showToast(`Re-ingested "${doc.title}" (${res.chunks_count} chunks)`)
      await loadDocs()
    } catch (err: any) {
      showToast(err.message || 'Re-ingestion failed', 'error')
    } finally {
      setReingestingId(null)
    }
  }

  const handleStatusChange = async (docId: string, newStatus: string) => {
    try {
      await updateDocumentStatus(docId, newStatus)
      showToast(`Document status changed to ${newStatus}`)
      await loadDocs()
    } catch (err: any) {
      showToast(err.message || 'Failed to change status', 'error')
    }
  }

  const handleOpenChunks = async (doc: AdminDocumentItem) => {
    try {
      setChunkModalDoc(doc)
      setChunksLoading(true)
      const data = await getDocumentChunks(doc.id)
      setChunks(data)
    } catch (err: any) {
      showToast(err.message || 'Failed to fetch chunks', 'error')
    } finally {
      setChunksLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!deletingDoc) return
    try {
      setDeletingLoading(true)
      await deleteDocument(deletingDoc.id)
      showToast(`Deleted "${deletingDoc.title}"`)
      setDeletingDoc(null)
      await loadDocs()
    } catch (err: any) {
      showToast(err.message || 'Failed to delete document', 'error')
    } finally {
      setDeletingLoading(false)
    }
  }

  const handleOpenEdit = (doc: AdminDocumentItem) => {
    setEditingDoc(doc)
    setEditFormData({
      title: doc.title || '',
      notice_sno: doc.notice_sno || '',
      notice_date: doc.notice_date || '',
      department_id: doc.department_id || undefined,
    })
  }

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingDoc) return
    try {
      setEditLoading(true)
      await updateDocumentMetadata(editingDoc.id, {
        title: editFormData.title.trim() || undefined,
        notice_sno: editFormData.notice_sno.trim() || undefined,
        notice_date: editFormData.notice_date.trim() || undefined,
        department_id: editFormData.department_id,
      })
      showToast(`Updated metadata for "${editFormData.title}"`)
      setEditingDoc(null)
      await loadDocs()
    } catch (err: any) {
      showToast(err.message || 'Failed to update metadata', 'error')
    } finally {
      setEditLoading(false)
    }
  }

  const handleOpenUpload = () => {
    setUploadFormData({
      title: '',
      notice_sno: '',
      notice_date: new Date().toISOString().split('T')[0],
      department_id: departments[0]?.id || undefined,
      source_url: '',
      content: '',
    })
    setIsUploadModalOpen(true)
  }

  const handleSaveUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFormData.title.trim() || !uploadFormData.content.trim()) {
      showToast('Title and notice content are required', 'error')
      return
    }
    try {
      setUploadLoading(true)
      const res = await manualUploadDocument({
        title: uploadFormData.title.trim(),
        notice_sno: uploadFormData.notice_sno.trim() || undefined,
        notice_date: uploadFormData.notice_date.trim() || undefined,
        department_id: uploadFormData.department_id,
        source_url: uploadFormData.source_url.trim() || undefined,
        content: uploadFormData.content.trim(),
      })
      showToast(`Uploaded & indexed notice (${res.chunks_count} chunks embedded)`)
      setIsUploadModalOpen(false)
      await loadDocs()
    } catch (err: any) {
      showToast(err.message || 'Failed to upload notice', 'error')
    } finally {
      setUploadLoading(false)
    }
  }

  // Bulk Actions
  const toggleSelectAll = () => {
    if (selectedDocIds.length === documents.length) {
      setSelectedDocIds([])
    } else {
      setSelectedDocIds(documents.map((d) => d.id))
    }
  }

  const toggleSelectDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const handleBulkAction = async (action: 'reingest' | 'update_status' | 'delete', targetStatus?: string) => {
    if (selectedDocIds.length === 0) return
    try {
      setBulkActionLoading(true)
      const res = await bulkActionDocuments(selectedDocIds, action, targetStatus)
      showToast(`Bulk action completed: ${res.affected_count} documents affected`)
      setSelectedDocIds([])
      await loadDocs()
    } catch (err: any) {
      showToast(err.message || 'Bulk action failed', 'error')
    } finally {
      setBulkActionLoading(false)
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1
  const startIdx = total === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endIdx = Math.min(currentPage * pageSize, total)

  return (
    <div className="space-y-4 font-['Inter',sans-serif]">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`p-3.5 rounded-xl text-xs font-semibold flex items-center justify-between shadow-sm transition-all ${
            notification.type === 'error'
              ? 'bg-rose-50 text-rose-800 border border-rose-200'
              : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
          }`}
        >
          <span>{notification.message}</span>
          <button
            onClick={() => setNotification(null)}
            className="text-neutral-400 hover:text-neutral-800 font-bold ml-2 cursor-pointer"
          >
            &times;
          </button>
        </div>
      )}

      {/* Control Bar: Filters & Search */}
      <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex flex-wrap items-center justify-between gap-3">
        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search documents by title, S.No, or URL..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 placeholder-neutral-400 focus:outline-none focus:border-neutral-900"
          />
        </form>

        {/* Filters */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Status Filter */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-neutral-500 font-medium">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setCurrentPage(1)
              }}
              className="px-2.5 py-1.5 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer"
            >
              <option value="all">All Statuses</option>
              <option value="fresh">Fresh & Verified</option>
              <option value="conflicted">Conflicted (Excluded)</option>
              <option value="stale">Stale</option>
              <option value="archived">Archived / Superseded</option>
            </select>
          </div>

          {/* Department Filter */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-neutral-500 font-medium">Department:</span>
            <select
              value={selectedDeptId?.toString() || 'all'}
              onChange={(e) => {
                const val = e.target.value
                setSelectedDeptId(val === 'all' ? null : Number(val))
                setCurrentPage(1)
              }}
              className="px-2.5 py-1.5 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer max-w-[180px] truncate"
            >
              <option value="all">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>

          {/* Refresh Button */}
          <button
            type="button"
            onClick={loadDocs}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-sm cursor-pointer"
            title="Refresh list"
          >
            <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          {/* Upload Notice Button */}
          <button
            type="button"
            onClick={handleOpenUpload}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#18181b] hover:bg-neutral-800 text-white rounded-xl text-xs font-semibold transition shadow-sm cursor-pointer"
            title="Upload a new notice or circular directly into RAG"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Manual Notice</span>
          </button>
        </div>
      </div>

      {/* Bulk Action Toolbar (Surfaces when rows are selected) */}
      {selectedDocIds.length > 0 && (
        <div className="bg-[#18181b] text-white px-4 py-3 rounded-xl flex flex-wrap items-center justify-between gap-3 shadow-md animate-in fade-in">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-bold bg-white/20 px-2 py-0.5 rounded text-[11px]">
              {selectedDocIds.length} Selected
            </span>
            <span className="text-neutral-300">Choose batch operation:</span>
          </div>

          <div className="flex items-center gap-2 flex-wrap text-xs">
            <button
              onClick={() => handleBulkAction('reingest')}
              disabled={bulkActionLoading}
              className="px-3 py-1 bg-white/10 hover:bg-white/20 rounded-lg font-semibold transition cursor-pointer"
            >
              Bulk Re-ingest
            </button>
            <button
              onClick={() => handleBulkAction('update_status', 'fresh')}
              disabled={bulkActionLoading}
              className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold transition cursor-pointer"
            >
              Mark Fresh
            </button>
            <button
              onClick={() => handleBulkAction('update_status', 'archived')}
              disabled={bulkActionLoading}
              className="px-3 py-1 bg-neutral-700 hover:bg-neutral-600 text-white rounded-lg font-semibold transition cursor-pointer"
            >
              Mark Archived
            </button>
            <button
              onClick={() => handleBulkAction('delete')}
              disabled={bulkActionLoading}
              className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-semibold transition cursor-pointer"
            >
              Bulk Delete
            </button>
            <button
              onClick={() => setSelectedDocIds([])}
              className="px-2 py-1 text-neutral-400 hover:text-white transition ml-1"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Documents Table */}
      <div className="bg-white border border-[#e4e4e7] rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#f8f9fa] border-b border-[#e4e4e7] text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                <th className="py-3 px-3 w-10 text-center">
                  <button
                    type="button"
                    onClick={toggleSelectAll}
                    className="text-neutral-500 hover:text-neutral-900 transition"
                  >
                    {documents.length > 0 && selectedDocIds.length === documents.length ? (
                      <CheckSquare className="w-4 h-4 text-neutral-900" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                </th>
                <th className="py-3 px-3 w-28">S.No</th>
                <th className="py-3 px-3 w-28">Date</th>
                <th className="py-3 px-4">Document / Notice Title</th>
                <th className="py-3 px-4 w-36">Department</th>
                <th className="py-3 px-4 w-36 text-center">Status</th>
                <th className="py-3 px-4 w-52 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ebecee] text-xs">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-neutral-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RotateCw className="w-6 h-6 animate-spin text-neutral-400" />
                      <span>Loading institutional documents from PostgreSQL...</span>
                    </div>
                  </td>
                </tr>
              ) : documents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-neutral-500">
                    No documents matching the selected filters found.
                  </td>
                </tr>
              ) : (
                documents.map((doc) => {
                  const isSelected = selectedDocIds.includes(doc.id)
                  return (
                    <tr
                      key={doc.id}
                      className={`hover:bg-[#f8f9fa] transition ${isSelected ? 'bg-indigo-50/20' : ''}`}
                    >
                      <td className="py-3.5 px-3 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectDoc(doc.id)}
                          className="w-4 h-4 rounded text-neutral-900 border-neutral-300 focus:ring-0 cursor-pointer"
                        />
                      </td>
                      <td className="py-3.5 px-3 font-mono font-medium text-neutral-700">
                        {doc.notice_sno || `#${doc.id.slice(0, 8)}`}
                      </td>
                      <td className="py-3.5 px-3 text-neutral-600 whitespace-nowrap">
                        {doc.notice_date || 'N/A'}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-[#18181b] line-clamp-1">{doc.title}</div>
                        <div className="text-[11px] text-neutral-400 font-mono truncate max-w-sm mt-0.5">
                          {doc.source_url}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-neutral-700">
                        <span className="text-[11px] font-medium bg-neutral-100 text-neutral-800 px-2 py-0.5 rounded-md border border-neutral-200 line-clamp-1">
                          {doc.department_name || 'General'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {/* Interactive Status Switcher */}
                        <select
                          value={doc.status.toLowerCase()}
                          onChange={(e) => handleStatusChange(doc.id, e.target.value)}
                          className="px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded-md border border-[#e4e4e7] bg-white cursor-pointer focus:outline-none"
                        >
                          <option value="fresh">Fresh</option>
                          <option value="stale">Stale</option>
                          <option value="conflicted">Conflicted</option>
                          <option value="archived">Archived</option>
                        </select>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Chunks Inspector Button */}
                          <button
                            type="button"
                            onClick={() => handleOpenChunks(doc)}
                            className="inline-flex items-center gap-1 px-2 py-1 bg-white hover:bg-neutral-100 text-neutral-700 rounded-lg text-xs font-semibold border border-neutral-200 transition shadow-2xs"
                            title="Inspect text chunks and token counts"
                          >
                            <Layers className="w-3 h-3 text-neutral-500" />
                            <span>{doc.chunk_count}c</span>
                          </button>

                          {/* Reingest Button */}
                          <button
                            type="button"
                            onClick={() => handleReingest(doc)}
                            disabled={reingestingId === doc.id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-lg text-xs font-semibold border border-[#d4d4d8] transition shadow-sm disabled:opacity-40 cursor-pointer"
                            title="Force re-chunk & re-embed this document"
                          >
                            <RotateCw
                              className={`w-3 h-3 ${reingestingId === doc.id ? 'animate-spin' : ''}`}
                            />
                            <span>{reingestingId === doc.id ? 'Syncing' : 'Re-ingest'}</span>
                          </button>

                          {/* PDF View Link */}
                          {doc.source_url && (
                            <a
                              href={doc.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-indigo-700 rounded-lg text-xs font-semibold border border-[#d4d4d8] transition shadow-sm"
                              title="View official document"
                            >
                              <span>PDF</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}

                          {/* Edit Metadata Button */}
                          <button
                            type="button"
                            onClick={() => handleOpenEdit(doc)}
                            className="p-1 text-neutral-400 hover:text-neutral-900 rounded-md transition"
                            title="Edit notice metadata (title, S.No, date, department)"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>

                          {/* Delete Document Button */}
                          <button
                            type="button"
                            onClick={() => setDeletingDoc(doc)}
                            className="p-1 text-neutral-400 hover:text-rose-600 rounded-md transition"
                            title="Delete this document"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-[#e4e4e7] bg-[#f8f9fa] flex flex-wrap items-center justify-between gap-3 text-xs text-neutral-600">
          <div>
            Showing <span className="font-semibold text-neutral-900">{startIdx} - {endIdx}</span> of{' '}
            <span className="font-semibold text-neutral-900">{total}</span> documents
          </div>

          <div className="flex items-center gap-2">
            <span className="text-neutral-500">Show:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value))
                setCurrentPage(1)
              }}
              className="px-2 py-1 bg-white border border-[#e4e4e7] rounded-md text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>

            <div className="flex items-center gap-1 ml-2">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="p-1 bg-white border border-[#d4d4d8] rounded-md hover:bg-neutral-100 disabled:opacity-30 transition cursor-pointer"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="px-2 font-medium">
                {currentPage} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                className="p-1 bg-white border border-[#d4d4d8] rounded-md hover:bg-neutral-100 disabled:opacity-30 transition cursor-pointer"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Chunks Inspector Modal */}
      {chunkModalDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#e4e4e7] max-w-4xl w-full max-h-[85vh] flex flex-col shadow-xl overflow-hidden animate-in fade-in zoom-in-95">
            <div className="px-5 py-4 border-b border-[#f0f0f2] flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-[#18181b] flex items-center gap-2">
                  <FileText className="w-4 h-4 text-neutral-600" />
                  <span>Document Chunks & Vector Breakdown</span>
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5 line-clamp-1">
                  {chunkModalDoc.title}
                </p>
              </div>
              <button
                onClick={() => setChunkModalDoc(null)}
                className="p-1 text-neutral-400 hover:text-neutral-800 rounded-lg hover:bg-neutral-100 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto flex-1 space-y-3 bg-[#f8f9fa]">
              {chunksLoading ? (
                <div className="py-16 text-center text-neutral-500">
                  <RotateCw className="w-6 h-6 animate-spin mx-auto text-neutral-400 mb-2" />
                  <span className="text-xs">Loading chunks...</span>
                </div>
              ) : chunks.length === 0 ? (
                <p className="text-xs text-neutral-400 py-8 text-center">No chunks found for this document.</p>
              ) : (
                chunks.map((ch, idx) => (
                  <div
                    key={ch.id}
                    className="p-4 bg-white border border-[#e4e4e7] rounded-xl text-xs space-y-2 shadow-2xs"
                  >
                    <div className="flex items-center justify-between text-[11px] text-neutral-500 pb-2 border-b border-neutral-100">
                      <span className="font-semibold text-neutral-800">Chunk #{idx + 1}</span>
                      <span className="font-mono">{ch.token_count} tokens &bull; ID: {ch.id.slice(0, 8)}</span>
                    </div>
                    <p className="text-neutral-800 whitespace-pre-wrap leading-relaxed font-mono text-[11px]">
                      {ch.content}
                    </p>
                  </div>
                ))
              )}
            </div>

            <div className="px-5 py-3 border-t border-[#f0f0f2] bg-white flex justify-end">
              <button
                onClick={() => setChunkModalDoc(null)}
                className="px-4 py-1.5 bg-neutral-900 hover:bg-black text-white text-xs font-semibold rounded-xl shadow-sm transition cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#e4e4e7] max-w-md w-full p-5 space-y-4 shadow-xl animate-in fade-in zoom-in-95">
            <div>
              <h3 className="font-bold text-sm text-[#18181b]">Confirm Document Deletion</h3>
              <p className="text-xs text-neutral-500 mt-1">
                Are you sure you want to permanently delete "{deletingDoc.title}"? All associated vector embeddings and text chunks will be purged.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-neutral-100">
              <button
                onClick={() => setDeletingDoc(null)}
                className="px-3 py-1.5 text-xs font-semibold text-neutral-700 bg-neutral-100 hover:bg-neutral-200 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deletingLoading}
                className="px-3 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition disabled:opacity-40"
              >
                {deletingLoading ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Metadata Modal */}
      {editingDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#e4e4e7] max-w-lg w-full p-5 space-y-4 shadow-xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-100">
              <h3 className="font-bold text-sm text-[#18181b] flex items-center gap-2">
                <Edit2 className="w-4 h-4 text-neutral-600" />
                <span>Edit Document Metadata</span>
              </h3>
              <button
                onClick={() => setEditingDoc(null)}
                className="p-1 text-neutral-400 hover:text-neutral-800 rounded-lg hover:bg-neutral-100 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-neutral-700 mb-1">Document / Notice Title *</label>
                <input
                  type="text"
                  required
                  value={editFormData.title}
                  onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                  placeholder="Official Notice Title"
                  className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-neutral-700 mb-1">Serial / Order No</label>
                  <input
                    type="text"
                    value={editFormData.notice_sno}
                    onChange={(e) => setEditFormData({ ...editFormData, notice_sno: e.target.value })}
                    placeholder="e.g. ECA/CS/2026/102"
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-neutral-700 mb-1">Notice Date</label>
                  <input
                    type="date"
                    value={editFormData.notice_date}
                    onChange={(e) => setEditFormData({ ...editFormData, notice_date: e.target.value })}
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-neutral-700 mb-1">Department / Issuing Section</label>
                <select
                  value={editFormData.department_id || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, department_id: e.target.value ? Number(e.target.value) : undefined })}
                  className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                >
                  <option value="">Select or leave unchanged</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-100">
                <button
                  type="button"
                  onClick={() => setEditingDoc(null)}
                  className="px-3.5 py-1.5 text-xs font-semibold text-neutral-700 bg-neutral-100 hover:bg-neutral-200 rounded-xl transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editLoading}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-[#18181b] hover:bg-black rounded-xl shadow-sm transition disabled:opacity-40"
                >
                  {editLoading ? 'Saving...' : 'Save Metadata'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Notice Upload Modal */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#e4e4e7] max-w-xl w-full p-5 space-y-4 shadow-xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-neutral-100">
              <div>
                <h3 className="font-bold text-sm text-[#18181b] flex items-center gap-2">
                  <Plus className="w-4 h-4 text-neutral-600" />
                  <span>Upload Manual Notice to Knowledge Base</span>
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5">
                  Content will be chunked, embedded via vector embeddings, and immediately active in student retrieval.
                </p>
              </div>
              <button
                onClick={() => setIsUploadModalOpen(false)}
                className="p-1 text-neutral-400 hover:text-neutral-800 rounded-lg hover:bg-neutral-100 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveUpload} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-neutral-700 mb-1">Notice Title *</label>
                <input
                  type="text"
                  required
                  value={uploadFormData.title}
                  onChange={(e) => setUploadFormData({ ...uploadFormData, title: e.target.value })}
                  placeholder="e.g. Schedule for Mid-Term Examination Spring 2026"
                  className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-neutral-700 mb-1">Serial / Dispatch No</label>
                  <input
                    type="text"
                    value={uploadFormData.notice_sno}
                    onChange={(e) => setUploadFormData({ ...uploadFormData, notice_sno: e.target.value })}
                    placeholder="e.g. ECA/Exam/2026/045"
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-neutral-700 mb-1">Notice Date</label>
                  <input
                    type="date"
                    value={uploadFormData.notice_date}
                    onChange={(e) => setUploadFormData({ ...uploadFormData, notice_date: e.target.value })}
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-neutral-700 mb-1">Department / Cell</label>
                  <select
                    value={uploadFormData.department_id || ''}
                    onChange={(e) => setUploadFormData({ ...uploadFormData, department_id: e.target.value ? Number(e.target.value) : undefined })}
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                  >
                    <option value="">Select Department</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-neutral-700 mb-1">Source URL (Optional)</label>
                  <input
                    type="url"
                    value={uploadFormData.source_url}
                    onChange={(e) => setUploadFormData({ ...uploadFormData, source_url: e.target.value })}
                    placeholder="https://ecajmer.ac.in/..."
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-neutral-700 mb-1">Full Notice Content / Text *</label>
                <textarea
                  required
                  rows={6}
                  value={uploadFormData.content}
                  onChange={(e) => setUploadFormData({ ...uploadFormData, content: e.target.value })}
                  placeholder="Paste official notification text here. It will be tokenized, chunked, and vectorized..."
                  className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 focus:outline-none focus:border-neutral-900 font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-neutral-100">
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(false)}
                  className="px-3.5 py-1.5 text-xs font-semibold text-neutral-700 bg-neutral-100 hover:bg-neutral-200 rounded-xl transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploadLoading}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-[#18181b] hover:bg-black rounded-xl shadow-sm transition disabled:opacity-40"
                >
                  {uploadLoading ? 'Embedding & Indexing...' : 'Upload & Embed Notice'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
