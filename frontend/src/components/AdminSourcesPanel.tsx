import React, { useState, useEffect } from 'react'
import {
  Plus,
  RefreshCw,
  Trash2,
  Edit2,
  ArrowUp,
  ArrowDown,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Database,
  Play,
  X,
  Sparkles,
  Bot,
  Search,
  Filter,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  Eye,
} from 'lucide-react'
import {
  IngestionSource,
  SourceCreatePayload,
  getSources,
  createSource,
  updateSource,
  deleteSource,
  reorderSources,
  triggerFetchSource,
  triggerFetchAll,
  seedDefaultSources,
} from '../api/sources'

const DEPARTMENTS_LIST = [
  'Computer Science and Engineering',
  'Civil Engineering',
  'Electrical Engineering',
  'Electronics and Communication Engineering',
  'Electronic Instrumentation And Control Engineering',
  'Mechanical Engineering',
  'Computer Applications',
  'Management Studies',
  'Physics',
  'Chemistry',
  'Mathematics',
  'English',
  'Economics',
  'Examination Section',
  'Registrar Section',
  'Academic Section',
  'Central Library',
  'First Year Cell',
  'Training & Placement Cell',
]

const QUICK_PRESETS = [
  {
    name: 'CSE Circulars',
    url: 'https://www.ecajmer.ac.in/departments/cs-it/circulars',
    department: 'Computer Science and Engineering',
    category: 'circulars',
  },
  {
    name: 'CSE Time Tables',
    url: 'https://www.ecajmer.ac.in/departments/cs-it/timetable',
    department: 'Computer Science and Engineering',
    category: 'timetable',
  },
  {
    name: 'Exam Section Circulars',
    url: 'https://www.ecajmer.ac.in/ui/cells/examination-section/circulars',
    department: 'Examination Section',
    category: 'circulars',
  },
  {
    name: 'Registrar Circulars',
    url: 'https://www.ecajmer.ac.in/ui/cells/registrar/circulars',
    department: 'Registrar Section',
    category: 'circulars',
  },
  {
    name: 'Civil Engineering Circulars',
    url: 'https://www.ecajmer.ac.in/departments/ce/circulars',
    department: 'Civil Engineering',
    category: 'circulars',
  },
  {
    name: 'Electrical Engineering Circulars',
    url: 'https://www.ecajmer.ac.in/departments/ee/circulars',
    department: 'Electrical Engineering',
    category: 'circulars',
  },
  {
    name: 'Electronics & Comm. Circulars',
    url: 'https://www.ecajmer.ac.in/departments/ece/circulars',
    department: 'Electronics and Communication Engineering',
    category: 'circulars',
  },
  {
    name: 'Mechanical Eng. Circulars',
    url: 'https://www.ecajmer.ac.in/departments/me/circulars',
    department: 'Mechanical Engineering',
    category: 'circulars',
  },
]

interface LiveCircularItem {
  id: number
  sno: string
  date: string
  title: string
  content: string
  createdAt?: string
}

export const AdminSourcesPanel: React.FC<{ isStandalone?: boolean }> = ({ isStandalone = false }) => {
  const [sources, setSources] = useState<IngestionSource[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSource, setEditingSource] = useState<IngestionSource | null>(null)
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDeptFilter, setSelectedDeptFilter] = useState('all')

  // ECA-style table pagination controls
  const [pageSize, setPageSize] = useState<number>(10)
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [yearFilter, setYearFilter] = useState<string>('All')

  // Live Circulars Explorer Modal State
  const [explorerOpen, setExplorerOpen] = useState(false)
  const [explorerSource, setExplorerSource] = useState<IngestionSource | null>(null)
  const [liveCirculars, setLiveCirculars] = useState<LiveCircularItem[]>([])
  const [liveLoading, setLiveLoading] = useState(false)
  const [livePageSize, setLivePageSize] = useState(10)
  const [liveCurrentPage, setLiveCurrentPage] = useState(1)
  const [liveTotalItems, setLiveTotalItems] = useState(0)
  const [liveYearFilter, setLiveYearFilter] = useState('All')
  const [liveSearchQuery, setLiveSearchQuery] = useState('')

  const [formData, setFormData] = useState<SourceCreatePayload>({
    name: '',
    url: '',
    department: 'Computer Science and Engineering',
    category: 'circulars',
    priority: 1,
    is_active: true,
    initial_fetch_limit: 50,
    subsequent_fetch_limit: 20,
  })

  const loadSources = async (showSpinner = true) => {
    try {
      if (showSpinner) setLoading(true)
      const data = await getSources()
      setSources(data)
    } catch (err: any) {
      if (showSpinner) showNotice(err.message || 'Failed to load sources', 'error')
    } finally {
      if (showSpinner) setLoading(false)
    }
  }

  useEffect(() => {
    loadSources(true)
  }, [])

  // Auto-poll every 2.5 seconds when any source is actively in "fetching" state
  useEffect(() => {
    const hasActiveFetching = sources.some((s) => s.status === 'fetching')
    if (hasActiveFetching) {
      const interval = setInterval(() => {
        loadSources(false)
      }, 2500)
      return () => clearInterval(interval)
    }
  }, [sources])


  const showNotice = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 4000)
  }

  const handleOpenAdd = () => {
    setEditingSource(null)
    const nextPriority = sources.length > 0 ? Math.max(...sources.map((s) => s.priority)) + 1 : 1
    setFormData({
      name: '',
      url: '',
      department: 'Computer Science and Engineering',
      category: 'circulars',
      priority: nextPriority,
      is_active: true,
      initial_fetch_limit: 50,
      subsequent_fetch_limit: 20,
    })
    setModalOpen(true)
  }

  const handleOpenEdit = (src: IngestionSource) => {
    setEditingSource(src)
    setFormData({
      name: src.name,
      url: src.url,
      department: src.department || '',
      category: src.category,
      priority: src.priority,
      is_active: src.is_active,
      initial_fetch_limit: src.initial_fetch_limit,
      subsequent_fetch_limit: src.subsequent_fetch_limit,
    })
    setModalOpen(true)
  }

  const handleApplyPreset = (preset: (typeof QUICK_PRESETS)[0]) => {
    const nextPriority = sources.length > 0 ? Math.max(...sources.map((s) => s.priority)) + 1 : 1
    setFormData({
      name: preset.name,
      url: preset.url,
      department: preset.department,
      category: preset.category,
      priority: nextPriority,
      is_active: true,
      initial_fetch_limit: 50,
      subsequent_fetch_limit: 20,
    })
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim() || !formData.url.trim()) {
      showNotice('Name and URL are required', 'error')
      return
    }

    try {
      if (editingSource) {
        await updateSource(editingSource.id, formData)
        showNotice(`Updated source "${formData.name}"`)
      } else {
        await createSource(formData)
        showNotice(`Added source "${formData.name}" with priority #${formData.priority}`)
      }
      setModalOpen(false)
      loadSources()
    } catch (err: any) {
      showNotice(err.message || 'Failed to save source', 'error')
    }
  }

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete source "${name}"?`)) return
    try {
      await deleteSource(id)
      showNotice(`Deleted source "${name}"`)
      loadSources()
    } catch (err: any) {
      showNotice(err.message || 'Failed to delete source', 'error')
    }
  }

  const handleMovePriority = async (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return
    if (direction === 'down' && index === sources.length - 1) return

    const targetIndex = direction === 'up' ? index - 1 : index + 1
    const newSources = [...sources]
    const current = newSources[index]
    const target = newSources[targetIndex]

    const tempPriority = current.priority
    current.priority = target.priority
    target.priority = tempPriority

    newSources[index] = target
    newSources[targetIndex] = current
    setSources(newSources)

    try {
      const items = newSources.map((s, idx) => ({ id: s.id, priority: idx + 1 }))
      const updated = await reorderSources(items)
      setSources(updated)
    } catch (err: any) {
      showNotice('Failed to update priority order', 'error')
      loadSources()
    }
  }

  const handleFetchSingle = async (id: string, name: string) => {
    try {
      setActionLoading(id)
      await triggerFetchSource(id)
      showNotice(`Triggered ingestion for "${name}" (50 on initial / 20 on recur)`)
      setTimeout(loadSources, 2000)
    } catch (err: any) {
      showNotice(err.message || 'Fetch trigger failed', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleFetchAll = async () => {
    try {
      setActionLoading('all')
      await triggerFetchAll()
      showNotice('Queued prioritized batch ingestion across all active sources!')
      setTimeout(loadSources, 3000)
    } catch (err: any) {
      showNotice(err.message || 'Batch fetch trigger failed', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const handleSeedDefaults = async () => {
    try {
      setActionLoading('seed')
      const seeded = await seedDefaultSources()
      setSources(seeded)
      showNotice(`Preloaded ${seeded.length} official department sources from ecajmer.ac.in!`)
    } catch (err: any) {
      showNotice(err.message || 'Seeding failed', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  // Live Circulars Fetcher from ECA API
  const fetchLiveEcaCirculars = async (src: IngestionSource, page = 1, limit = 10, search = '') => {
    setLiveLoading(true)
    const slug = src.slug || 'cs-it'
    const categoryId = src.category === 'timetable' ? 2 : 1
    const url = `https://ecajmer.ac.in/api/circulars/public/${slug}?page=${page}&limit=${limit}&mainCategoryId=${categoryId}&search=${encodeURIComponent(
      search
    )}`

    try {
      const res = await fetch(url)
      const data = await res.json()
      if (data && data.success) {
        setLiveCirculars(data.data || [])
        setLiveTotalItems(data.pagination?.totalItems || (data.data || []).length)
      } else {
        setLiveCirculars([])
        setLiveTotalItems(0)
      }
    } catch (err) {
      console.error('Failed to load live circulars:', err)
      setLiveCirculars([])
    } finally {
      setLiveLoading(false)
    }
  }

  const handleOpenExplorer = (src: IngestionSource) => {
    setExplorerSource(src)
    setLiveCurrentPage(1)
    setLivePageSize(10)
    setLiveYearFilter('All')
    setLiveSearchQuery('')
    setExplorerOpen(true)
    fetchLiveEcaCirculars(src, 1, 10, '')
  }

  // Filtered Sources
  const filteredSources = sources.filter((src) => {
    const matchesSearch =
      src.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      src.url.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (src.department && src.department.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesDept = selectedDeptFilter === 'all' || src.department === selectedDeptFilter
    return matchesSearch && matchesDept
  })

  // Pagination calculation
  const totalPages = Math.ceil(filteredSources.length / pageSize) || 1
  const validCurrentPage = Math.min(currentPage, totalPages)
  const startIdx = (validCurrentPage - 1) * pageSize + 1
  const endIdx = Math.min(validCurrentPage * pageSize, filteredSources.length)
  const paginatedSources = filteredSources.slice(
    (validCurrentPage - 1) * pageSize,
    validCurrentPage * pageSize
  )

  const activeCount = sources.filter((s) => s.is_active).length
  const completedCount = sources.filter((s) => s.status === 'completed').length

  // Live Explorer Pagination calculation
  const liveTotalPages = Math.ceil(liveTotalItems / livePageSize) || 1
  const liveStartIdx = (liveCurrentPage - 1) * livePageSize + 1
  const liveEndIdx = Math.min(liveCurrentPage * livePageSize, liveTotalItems)

  return (
    <div
      className={`min-h-screen bg-[#fcfcfc] text-[#18181b] font-['Inter',sans-serif] ${
        isStandalone ? 'p-4 sm:p-8' : ''
      }`}
    >
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Standalone Header if opened in new tab */}
        {isStandalone && (
          <header className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#18181b] flex items-center justify-center text-white shadow-sm">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="font-bold text-lg tracking-tight text-[#18181b]">EduSync Admin</h1>
                  <span className="text-[10px] font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md border border-indigo-100">
                    Source Management
                  </span>
                </div>
                <p className="text-xs text-neutral-500 mt-0.5">
                  Automated institutional document ingestion & prioritization for Engineering College Ajmer.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <a
                href="/"
                className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-neutral-700 bg-neutral-100 hover:bg-neutral-200/80 rounded-xl transition"
              >
                <Bot className="w-3.5 h-3.5" />
                <span>Open Student Assistant</span>
              </a>
            </div>
          </header>
        )}

        {/* Analytics & Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
          <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between text-neutral-500 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Total Sources</span>
              <Database className="w-4 h-4 text-indigo-600" />
            </div>
            <div className="text-2xl font-bold text-[#18181b]">{sources.length}</div>
            <p className="text-[11px] text-neutral-500 mt-1">Configured landing URLs</p>
          </div>

          <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between text-neutral-500 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Active Ingestion</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-2xl font-bold text-[#18181b]">{activeCount}</div>
            <p className="text-[11px] text-emerald-600 font-medium mt-1">Enabled for scheduled runs</p>
          </div>

          <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between text-neutral-500 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Fresh & Verified</span>
              <Clock className="w-4 h-4 text-blue-600" />
            </div>
            <div className="text-2xl font-bold text-[#18181b]">{completedCount}</div>
            <p className="text-[11px] text-neutral-500 mt-1">Up-to-date document sets</p>
          </div>

          <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between text-neutral-500 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Batch Strategy</span>
              <Layers className="w-4 h-4 text-purple-600" />
            </div>
            <div className="text-lg font-bold text-[#18181b]">50 / 20 Limit</div>
            <p className="text-[11px] text-neutral-500 mt-1">50 on 1st run &bull; 20 on recur</p>
          </div>
        </div>

        {/* Main Content Container */}
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-5 sm:p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-6">
          {/* Header Actions */}
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-[#f0f0f2]">
            <div>
              <h2 className="text-lg font-bold text-[#18181b]">Prioritized Institutional Sources</h2>
              <p className="text-xs text-neutral-500 mt-0.5">
                Manage target circulars and timetables. Execution executes in exact sequential priority (#1, #2, #3...).
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => loadSources(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-sm"
                title="Refresh sources list"
              >
                <RefreshCw className="w-3.5 h-3.5 text-neutral-600" />
                Refresh
              </button>

              <button
                onClick={handleSeedDefaults}
                disabled={actionLoading === 'seed'}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-800 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-sm"
                title="Preload all official departments from ecajmer.ac.in"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                Preload Departments
              </button>


              <button
                onClick={handleFetchAll}
                disabled={actionLoading === 'all' || sources.length === 0}
                className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-sm transition disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                Fetch All by Priority
              </button>

              <button
                onClick={handleOpenAdd}
                className="flex items-center gap-1.5 px-4 py-2 bg-[#18181b] hover:bg-black text-white rounded-xl text-xs font-semibold shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                Add New Source
              </button>
            </div>
          </div>

          {/* Toast Notification */}
          {notification && (
            <div
              className={`p-3.5 rounded-xl text-xs font-medium flex items-center gap-2 ${
                notification.type === 'success'
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  : 'bg-rose-50 text-rose-800 border border-rose-200'
              }`}
            >
              {notification.type === 'success' ? (
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              )}
              {notification.message}
            </div>
          )}

          {/* Filter and Search Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="relative flex-1 min-w-[240px] max-w-md">
              <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search sources by name, URL, or department..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  setCurrentPage(1)
                }}
                className="w-full pl-9 pr-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] placeholder-neutral-400 focus:outline-none focus:border-neutral-400 transition"
              />
            </div>

            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-neutral-500" />
              <select
                value={selectedDeptFilter}
                onChange={(e) => {
                  setSelectedDeptFilter(e.target.value)
                  setCurrentPage(1)
                }}
                className="px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-700 focus:outline-none"
              >
                <option value="all">All Departments</option>
                {DEPARTMENTS_LIST.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* ECA-STYLE PAGINATION & OPTIONS BAR */}
          {filteredSources.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-neutral-600 bg-[#f8f9fa] p-3 rounded-xl border border-[#e4e4e7]">
              <div>
                Showing <span className="font-semibold text-neutral-900">{startIdx} - {endIdx}</span> of{' '}
                <span className="font-semibold text-neutral-900">{filteredSources.length}</span> entries
              </div>

              <div className="flex items-center gap-3.5 flex-wrap">
                {/* Show entries dropdown */}
                <div className="flex items-center gap-1.5">
                  <span className="text-neutral-500">Show:</span>
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value))
                      setCurrentPage(1)
                    }}
                    className="px-2.5 py-1 bg-white border border-[#e4e4e7] rounded-lg text-xs font-semibold text-neutral-800 focus:outline-none shadow-sm cursor-pointer"
                  >
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={30}>30</option>
                    <option value={50}>50</option>
                  </select>
                  <span className="text-neutral-500">entries</span>
                </div>

                {/* Year filter dropdown */}
                <div className="flex items-center gap-1.5">
                  <span className="text-neutral-500">Year:</span>
                  <select
                    value={yearFilter}
                    onChange={(e) => {
                      setYearFilter(e.target.value)
                      setCurrentPage(1)
                    }}
                    className="px-2.5 py-1 bg-white border border-[#e4e4e7] rounded-lg text-xs font-semibold text-neutral-800 focus:outline-none shadow-sm cursor-pointer"
                  >
                    <option value="All">All</option>
                    <option value="2026">2026</option>
                    <option value="2025">2025</option>
                    <option value="2024">2024</option>
                    <option value="2023">2023</option>
                  </select>
                </div>

                {/* Page dropdown & Nav buttons */}
                <div className="flex items-center gap-1.5">
                  <select
                    value={validCurrentPage}
                    onChange={(e) => setCurrentPage(Number(e.target.value))}
                    className="px-2.5 py-1 bg-white border border-[#e4e4e7] rounded-lg text-xs font-semibold text-neutral-800 focus:outline-none shadow-sm cursor-pointer"
                  >
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                      <option key={p} value={p}>
                        {String(p).padStart(2, '0')}
                      </option>
                    ))}
                  </select>
                  <span className="text-neutral-500">of {totalPages} Pages</span>

                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={validCurrentPage === 1}
                    className="p-1 bg-white border border-[#e4e4e7] rounded-lg hover:bg-neutral-100 disabled:opacity-30 transition shadow-sm ml-1"
                    title="Previous Page"
                  >
                    <ChevronLeft className="w-3.5 h-3.5 text-neutral-700" />
                  </button>

                  <button
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={validCurrentPage >= totalPages}
                    className="p-1 bg-white border border-[#e4e4e7] rounded-lg hover:bg-neutral-100 disabled:opacity-30 transition shadow-sm"
                    title="Next Page"
                  >
                    <ChevronRight className="w-3.5 h-3.5 text-neutral-700" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Sources Table */}
          <div className="overflow-x-auto border border-[#e4e4e7] rounded-xl">
            {loading ? (
              <div className="py-12 flex flex-col items-center justify-center text-neutral-500 gap-3">
                <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
                <span className="text-sm">Loading ingestion sources...</span>
              </div>
            ) : filteredSources.length === 0 ? (
              <div className="py-16 text-center">
                <Layers className="w-12 h-12 text-neutral-300 mx-auto mb-3" />
                <h3 className="text-sm font-semibold text-neutral-700">No matching sources found</h3>
                <p className="text-xs text-neutral-500 max-w-md mx-auto mt-1 mb-4">
                  Add a new source or preload official college department URLs.
                </p>
                <button
                  onClick={handleSeedDefaults}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-sm"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Preload ECAjmer Departments
                </button>
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#f8f9fa] border-b border-[#e4e4e7] text-[11px] font-bold text-neutral-500 uppercase tracking-wider">
                    <th className="py-3 px-3 w-16 text-center">Priority</th>
                    <th className="py-3 px-3">Source Name & Target URL</th>
                    <th className="py-3 px-3">Department</th>
                    <th className="py-3 px-3">Category</th>
                    <th className="py-3 px-3 text-center">Limits</th>
                    <th className="py-3 px-3 text-center">Status</th>
                    <th className="py-3 px-3">Last Verified</th>
                    <th className="py-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ebecee] text-xs">
                  {paginatedSources.map((src, idx) => {
                    const globalIdx = (validCurrentPage - 1) * pageSize + idx
                    return (
                      <tr
                        key={src.id}
                        className={`hover:bg-[#f8f9fa] transition ${
                          !src.is_active ? 'opacity-50 bg-[#fafafa]' : ''
                        }`}
                      >
                        {/* Priority Controls */}
                        <td className="py-3.5 px-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <span className="w-6 h-6 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center justify-center font-bold text-xs">
                              #{src.priority}
                            </span>
                            <div className="flex flex-col">
                              <button
                                onClick={() => handleMovePriority(globalIdx, 'up')}
                                disabled={globalIdx === 0}
                                className="text-neutral-400 hover:text-neutral-900 disabled:opacity-20 p-0.5"
                                title="Increase Priority"
                              >
                                <ArrowUp className="w-3 h-3" />
                              </button>
                              <button
                                onClick={() => handleMovePriority(globalIdx, 'down')}
                                disabled={globalIdx === sources.length - 1}
                                className="text-neutral-400 hover:text-neutral-900 disabled:opacity-20 p-0.5"
                                title="Decrease Priority"
                              >
                                <ArrowDown className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        </td>

                        {/* Source Name & URL */}
                        <td className="py-3.5 px-3">
                          <div className="font-semibold text-[#18181b] flex items-center gap-2">
                            <button
                              onClick={() => handleOpenExplorer(src)}
                              className="hover:text-indigo-600 text-left transition flex items-center gap-1.5"
                              title="Explore live circulars from this source"
                            >
                              <span>{src.name}</span>
                              <Eye className="w-3.5 h-3.5 text-neutral-400 hover:text-indigo-600" />
                            </button>
                            {!src.is_active && (
                              <span className="text-[10px] bg-neutral-200 text-neutral-600 px-1.5 py-0.5 rounded font-medium">
                                Disabled
                              </span>
                            )}
                          </div>
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-neutral-500 hover:text-indigo-600 flex items-center gap-1 mt-0.5 truncate max-w-sm"
                          >
                            {src.url}
                            <ExternalLink className="w-3 h-3 shrink-0" />
                          </a>
                        </td>

                        {/* Department */}
                        <td className="py-3.5 px-3">
                          <span className="inline-block px-2.5 py-1 bg-neutral-100 border border-neutral-200 rounded-lg text-neutral-700 text-[11px] font-medium">
                            {src.department || 'General'}
                          </span>
                        </td>

                        {/* Category */}
                        <td className="py-3.5 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider ${
                              src.category === 'timetable'
                                ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                : 'bg-blue-50 text-blue-700 border border-blue-200'
                            }`}
                          >
                            {src.category}
                          </span>
                        </td>

                        {/* Limits */}
                        <td className="py-3.5 px-3 text-center text-neutral-500 text-[11px]">
                          <span className="text-emerald-600 font-semibold">{src.initial_fetch_limit}</span> 1st /{' '}
                          <span className="text-indigo-600 font-semibold">{src.subsequent_fetch_limit}</span> Recur
                        </td>

                        {/* Status Badge */}
                        <td className="py-3.5 px-3 text-center">
                          {src.status === 'fetching' ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-amber-50 text-amber-800 border border-amber-200 rounded-full text-[11px] font-medium animate-pulse">
                              <RefreshCw className="w-3 h-3 animate-spin text-amber-600" />
                              Fetching...
                            </span>
                          ) : src.status === 'completed' ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-[11px] font-medium">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              Fresh
                            </span>
                          ) : src.status === 'error' ? (
                            <span
                              className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded-full text-[11px] font-medium"
                              title={src.error_message || 'Fetch error'}
                            >
                              <AlertCircle className="w-3 h-3 text-rose-600" />
                              Error
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-neutral-100 text-neutral-500 rounded-full text-[11px]">
                              <Clock className="w-3 h-3" />
                              Idle
                            </span>
                          )}
                        </td>

                        {/* Last Fetched Date */}
                        <td className="py-3.5 px-3 text-neutral-500 text-[11px]">
                          {src.last_fetched_at
                            ? new Date(src.last_fetched_at).toLocaleDateString([], {
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              })
                            : 'Never'}
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleFetchSingle(src.id, src.name)}
                              disabled={actionLoading === src.id}
                              className="p-1.5 bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white rounded-lg border border-indigo-200 transition disabled:opacity-40"
                              title="Fetch & Embed now"
                            >
                              <Play className="w-3.5 h-3.5 fill-current" />
                            </button>
                            <button
                              onClick={() => handleOpenEdit(src)}
                              className="p-1.5 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 rounded-lg transition border border-neutral-200"
                              title="Edit Source"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDelete(src.id, src.name)}
                              className="p-1.5 bg-rose-50 hover:bg-rose-600 text-rose-600 hover:text-white rounded-lg transition border border-rose-200"
                              title="Delete Source"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* LIVE CIRCULARS EXPLORER MODAL (ECA-STYLE TABLE & CONTROLS) */}
      {explorerOpen && explorerSource && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-[#e4e4e7] rounded-2xl w-full max-w-5xl p-6 shadow-2xl text-[#18181b] max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[#f0f0f2] flex-shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-xl">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#18181b]">
                    {explorerSource.name} &bull; Live ECA Notices
                  </h3>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    Live synchronization view from {explorerSource.url}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setExplorerOpen(false)}
                className="p-1.5 text-neutral-400 hover:text-neutral-900 rounded-lg transition hover:bg-neutral-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Filter & ECA Pagination Bar */}
            <div className="py-4 space-y-3 flex-shrink-0">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="relative flex-1 min-w-[200px] max-w-sm">
                  <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search circulars by title or S.No..."
                    value={liveSearchQuery}
                    onChange={(e) => {
                      setLiveSearchQuery(e.target.value)
                      setLiveCurrentPage(1)
                      fetchLiveEcaCirculars(explorerSource, 1, livePageSize, e.target.value)
                    }}
                    className="w-full pl-9 pr-3 py-1.5 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] placeholder-neutral-400 focus:outline-none"
                  />
                </div>

                {/* ECA Pagination Controls */}
                <div className="flex items-center gap-3 text-xs text-neutral-600 flex-wrap">
                  <div>
                    Showing <span className="font-semibold text-neutral-900">{liveStartIdx} - {liveEndIdx}</span> of{' '}
                    <span className="font-semibold text-neutral-900">{liveTotalItems}</span> entries
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-neutral-500">Show:</span>
                    <select
                      value={livePageSize}
                      onChange={(e) => {
                        const newLimit = Number(e.target.value)
                        setLivePageSize(newLimit)
                        setLiveCurrentPage(1)
                        fetchLiveEcaCirculars(explorerSource, 1, newLimit, liveSearchQuery)
                      }}
                      className="px-2 py-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-semibold text-neutral-800 focus:outline-none cursor-pointer"
                    >
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                      <option value={30}>30</option>
                      <option value={50}>50</option>
                    </select>
                    <span className="text-neutral-500">entries</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-neutral-500">Year:</span>
                    <select
                      value={liveYearFilter}
                      onChange={(e) => setLiveYearFilter(e.target.value)}
                      className="px-2 py-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-semibold text-neutral-800 focus:outline-none cursor-pointer"
                    >
                      <option value="All">All</option>
                      <option value="2026">2026</option>
                      <option value="2025">2025</option>
                      <option value="2024">2024</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <select
                      value={liveCurrentPage}
                      onChange={(e) => {
                        const newP = Number(e.target.value)
                        setLiveCurrentPage(newP)
                        fetchLiveEcaCirculars(explorerSource, newP, livePageSize, liveSearchQuery)
                      }}
                      className="px-2 py-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-semibold text-neutral-800 focus:outline-none cursor-pointer"
                    >
                      {Array.from({ length: liveTotalPages }, (_, i) => i + 1).map((p) => (
                        <option key={p} value={p}>
                          {String(p).padStart(2, '0')}
                        </option>
                      ))}
                    </select>
                    <span className="text-neutral-500">of {liveTotalPages} Pages</span>

                    <button
                      onClick={() => {
                        const p = Math.max(1, liveCurrentPage - 1)
                        setLiveCurrentPage(p)
                        fetchLiveEcaCirculars(explorerSource, p, livePageSize, liveSearchQuery)
                      }}
                      disabled={liveCurrentPage === 1}
                      className="p-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg hover:bg-neutral-200 disabled:opacity-30 transition"
                      title="Previous Page"
                    >
                      <ChevronLeft className="w-3.5 h-3.5 text-neutral-700" />
                    </button>

                    <button
                      onClick={() => {
                        const p = Math.min(liveTotalPages, liveCurrentPage + 1)
                        setLiveCurrentPage(p)
                        fetchLiveEcaCirculars(explorerSource, p, livePageSize, liveSearchQuery)
                      }}
                      disabled={liveCurrentPage >= liveTotalPages}
                      className="p-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg hover:bg-neutral-200 disabled:opacity-30 transition"
                      title="Next Page"
                    >
                      <ChevronRight className="w-3.5 h-3.5 text-neutral-700" />
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Live ECA Table */}
            <div className="overflow-y-auto flex-1 border border-[#e4e4e7] rounded-xl">
              {liveLoading ? (
                <div className="py-16 flex flex-col items-center justify-center text-neutral-500 gap-3">
                  <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
                  <span className="text-sm">Fetching live circulars from ECA portal...</span>
                </div>
              ) : liveCirculars.length === 0 ? (
                <div className="py-16 text-center text-neutral-500 text-xs">
                  No circulars found for this selection.
                </div>
              ) : (
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#f8f9fa] border-b border-[#e4e4e7] text-[11px] font-bold text-neutral-500 uppercase tracking-wider sticky top-0">
                      <th className="py-3 px-4 w-32">S.No</th>
                      <th className="py-3 px-4 w-28">Date</th>
                      <th className="py-3 px-4">Title</th>
                      <th className="py-3 px-4 w-24 text-right">View</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#ebecee] text-xs">
                    {liveCirculars.map((item) => {
                      const pdfUrl = item.content?.startsWith('http')
                        ? item.content
                        : `https://ecajmer.ac.in/${item.content?.replace(/^\//, '')}`
                      return (
                        <tr key={item.id} className="hover:bg-[#f8f9fa] transition">
                          <td className="py-3 px-4 font-mono font-medium text-neutral-700">
                            {item.sno || `#${item.id}`}
                          </td>
                          <td className="py-3 px-4 text-neutral-600">{item.date || 'N/A'}</td>
                          <td className="py-3 px-4 font-medium text-[#18181b]">{item.title}</td>
                          <td className="py-3 px-4 text-right">
                            {item.content ? (
                              <a
                                href={pdfUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white rounded-lg text-xs font-semibold border border-indigo-200 transition"
                              >
                                <span>View</span>
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            ) : (
                              <span className="text-neutral-400 text-xs">N/A</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {/* Modal Footer */}
            <div className="pt-4 mt-3 border-t border-[#f0f0f2] flex items-center justify-between text-xs text-neutral-500 flex-shrink-0">
              <span>Connected to https://ecajmer.ac.in API</span>
              <button
                onClick={() => setExplorerOpen(false)}
                className="px-4 py-1.5 bg-neutral-100 hover:bg-neutral-200 text-neutral-800 rounded-xl font-semibold transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add / Edit Source Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-[#e4e4e7] rounded-2xl w-full max-w-xl p-6 shadow-2xl text-[#18181b]">
            <div className="flex items-center justify-between pb-4 border-b border-[#f0f0f2]">
              <div>
                <h3 className="text-base font-bold text-[#18181b]">
                  {editingSource ? 'Edit Ingestion Source' : 'Add New Source Link'}
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5">
                  Configure department notices & timetable target on ecajmer.ac.in.
                </p>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1.5 text-neutral-400 hover:text-neutral-900 rounded-lg transition hover:bg-neutral-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Presets */}
            {!editingSource && (
              <div className="my-4">
                <div className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider mb-2">
                  Quick Presets (ECAjmer Departments & Cells)
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {QUICK_PRESETS.map((preset) => (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() => handleApplyPreset(preset)}
                      className="px-2.5 py-1 bg-neutral-100 hover:bg-indigo-50 text-neutral-700 hover:text-indigo-700 border border-neutral-200 hover:border-indigo-200 rounded-lg text-[11px] font-medium transition"
                    >
                      + {preset.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <form onSubmit={handleSave} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-neutral-700 mb-1">
                  Source Display Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. CSE Department Circulars"
                  className="w-full px-3.5 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] placeholder-neutral-400 focus:outline-none focus:border-neutral-400"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-700 mb-1">
                  Source URL on ecajmer.ac.in *
                </label>
                <input
                  type="url"
                  required
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  placeholder="https://www.ecajmer.ac.in/departments/cs-it/circulars"
                  className="w-full px-3.5 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] placeholder-neutral-400 focus:outline-none focus:border-neutral-400"
                />
                <p className="text-[11px] text-neutral-500 mt-1">
                  Attached PDF notices and timetables will be downloaded and embedded automatically.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">Department</label>
                  <select
                    value={formData.department || ''}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                  >
                    {DEPARTMENTS_LIST.map((dept) => (
                      <option key={dept} value={dept}>
                        {dept}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">Category</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                  >
                    <option value="circulars">Circulars / Notices (Category 1)</option>
                    <option value="timetable">Time Tables (Category 2)</option>
                    <option value="announcements">Announcements</option>
                    <option value="general_html">General Web Page</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">Priority Rank</label>
                  <input
                    type="number"
                    min="1"
                    value={formData.priority || 1}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 1 })}
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">1st Time Limit</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={formData.initial_fetch_limit || 50}
                    onChange={(e) =>
                      setFormData({ ...formData, initial_fetch_limit: parseInt(e.target.value) || 50 })
                    }
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">Recurring Limit</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={formData.subsequent_fetch_limit || 20}
                    onChange={(e) =>
                      setFormData({ ...formData, subsequent_fetch_limit: parseInt(e.target.value) || 20 })
                    }
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded border-[#d4d4d8] text-indigo-600 focus:ring-0"
                />
                <label htmlFor="is_active" className="text-xs text-neutral-700 font-medium">
                  Active for automated background extraction
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#f0f0f2]">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 rounded-xl text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#18181b] hover:bg-black text-white rounded-xl text-xs font-semibold shadow-sm transition"
                >
                  {editingSource ? 'Update Source' : 'Add Source'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
