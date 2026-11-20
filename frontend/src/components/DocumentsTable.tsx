import React, { useState, useEffect } from 'react'
import {
  Search,
  ExternalLink,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Archive,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import {
  AdminDocumentItem,
  getAdminDocuments,
  reingestDocument,
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

  const totalPages = Math.ceil(total / pageSize) || 1
  const startIdx = total === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endIdx = Math.min(currentPage * pageSize, total)

  const renderStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'fresh':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md text-[10px] font-semibold uppercase tracking-wider">
            <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
            Fresh
          </span>
        )
      case 'conflicted':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-md text-[10px] font-semibold uppercase tracking-wider">
            <AlertTriangle className="w-2.5 h-2.5 text-amber-600" />
            Conflicted
          </span>
        )
      case 'stale':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-neutral-100 text-neutral-700 border border-neutral-200 rounded-md text-[10px] font-semibold uppercase tracking-wider">
            <Clock className="w-2.5 h-2.5 text-neutral-500" />
            Stale
          </span>
        )
      case 'archived':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-neutral-100 text-neutral-500 border border-neutral-200 rounded-md text-[10px] font-semibold uppercase tracking-wider">
            <Archive className="w-2.5 h-2.5 text-neutral-400" />
            Archived
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-neutral-100 text-neutral-700 border border-neutral-200 rounded-md text-[10px] font-semibold uppercase tracking-wider">
            {status}
          </span>
        )
    }
  }

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
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white border border-[#e4e4e7] rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#f8f9fa] border-b border-[#e4e4e7] text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                <th className="py-3 px-4 w-28">S.No</th>
                <th className="py-3 px-4 w-28">Date</th>
                <th className="py-3 px-4">Document / Notice Title</th>
                <th className="py-3 px-4 w-40">Department</th>
                <th className="py-3 px-4 w-32 text-center">Status</th>
                <th className="py-3 px-4 w-44 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ebecee] text-xs">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-16 text-center text-neutral-500">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RotateCw className="w-6 h-6 animate-spin text-neutral-400" />
                      <span>Loading institutional documents from PostgreSQL...</span>
                    </div>
                  </td>
                </tr>
              ) : documents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-neutral-500">
                    No documents matching the selected filters found.
                  </td>
                </tr>
              ) : (
                documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-[#f8f9fa] transition">
                    <td className="py-3.5 px-4 font-mono font-medium text-neutral-700">
                      {doc.notice_sno || `#${doc.id.slice(0, 8)}`}
                    </td>
                    <td className="py-3.5 px-4 text-neutral-600 whitespace-nowrap">
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
                      <div className="flex items-center justify-center gap-1.5">
                        {renderStatusBadge(doc.status)}
                        <span className="px-1.5 py-0.5 bg-neutral-100 text-neutral-600 rounded text-[10px] font-semibold border border-neutral-200">
                          {doc.chunk_count}c
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
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
                          <span>{reingestingId === doc.id ? 'Re-ingesting' : 'Re-ingest'}</span>
                        </button>
                        {doc.source_url && (
                          <a
                            href={doc.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-lg text-xs font-semibold border border-[#d4d4d8] transition shadow-sm"
                            title="View official document"
                          >
                            <span>PDF</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
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
              className="px-2 py-1 bg-white border border-[#d4d4d8] rounded-md text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer"
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
    </div>
  )
}
