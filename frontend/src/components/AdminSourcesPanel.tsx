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
  Pause,
  X,
  Search,
  Filter,
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  Globe,
  FileCode,
  MessageSquare,
} from 'lucide-react'

import { LivePipelineModal } from './LivePipelineModal'

import {
  IngestionSource,
  SourceCreatePayload,
  IngestedDocumentItem,
  DocumentChunkItem,
  getSources,
  createSource,
  updateSource,
  deleteSource,
  reorderSources,
  triggerFetchSource,
  pauseFetchSource,
  triggerFetchAll,
  seedDefaultSources,
  getSourceDocuments,
  getDocumentChunks,
  getSourceLiveFeed,
} from '../api/sources'
import { Department, getDepartments, createDepartment } from '../api/departments'
import { testSourceUrl, TestUrlResponse } from '../api/admin'

export interface HardcodedPrefetchSource {
  name: string
  url: string
  department: string
  category: 'circulars' | 'timetable' | 'general_html'
  deptId: number
}

// 4 Hardcoded Core Sources kept for fast one-click prefetching & seeding
export const HARDCODED_PREFETCH_SOURCES: HardcodedPrefetchSource[] = [
  // Cells
  { name: 'Registrar Circulars & Orders', url: 'https://www.ecajmer.ac.in/ui/cells/registrar/circulars', department: 'Registrar Section', category: 'circulars', deptId: 3 },
  { name: 'Accounts Section Circulars', url: 'https://www.ecajmer.ac.in/ui/cells/accounts/circulars', department: 'Accounts Section', category: 'circulars', deptId: 16 },
  { name: 'Examination Section Circulars', url: 'https://www.ecajmer.ac.in/ui/cells/examination-section/circulars', department: 'Examination Section', category: 'circulars', deptId: 2 },
  { name: 'Academic Section Notices', url: 'https://www.ecajmer.ac.in/ui/cells/academic-section/circulars', department: 'Academic Section', category: 'circulars', deptId: 4 },
  { name: 'Proctor Section Circulars', url: 'https://www.ecajmer.ac.in/ui/cells/proctor/circulars', department: 'Proctor Section', category: 'circulars', deptId: 17 },
  { name: 'First Year Circulars', url: 'https://www.ecajmer.ac.in/ui/cells/first-year/circulars', department: 'First Year', category: 'circulars', deptId: 21 },
  { name: 'Central Library', url: 'https://www.ecajmer.ac.in/ui/cells/central-library/circulars', department: 'Central Library', category: 'circulars', deptId: 19 },
  { name: 'Mandatory Disclosure', url: 'https://ecajmer.ac.in/mandatorydisclousure', department: 'General Admin', category: 'general_html', deptId: 23 },

  // Branches
  { name: 'CE Circulars', url: 'https://www.ecajmer.ac.in/departments/ce/circulars', department: 'Civil Engineering', category: 'circulars', deptId: 5 },
  { name: 'CE Timetable', url: 'https://www.ecajmer.ac.in/departments/ce/timetable', department: 'Civil Engineering', category: 'timetable', deptId: 5 },
  { name: 'Chemistry Circulars', url: 'https://www.ecajmer.ac.in/departments/chemistry/circulars', department: 'Chemistry', category: 'circulars', deptId: 13 },
  { name: 'CS-IT Circulars', url: 'https://www.ecajmer.ac.in/departments/cs-it/circulars', department: 'Computer Science and Engineering', category: 'circulars', deptId: 1 },
  { name: 'CS-IT Timetable', url: 'https://www.ecajmer.ac.in/departments/cs-it/timetable', department: 'Computer Science and Engineering', category: 'timetable', deptId: 1 },
  { name: 'ECE Circulars', url: 'https://www.ecajmer.ac.in/departments/ece/circulars', department: 'Electronics & Communication Engineering', category: 'circulars', deptId: 7 },
  { name: 'ECE Timetable', url: 'https://www.ecajmer.ac.in/departments/ece/timetable', department: 'Electronics & Communication Engineering', category: 'timetable', deptId: 7 },
  { name: 'Economy Circulars', url: 'https://www.ecajmer.ac.in/departments/economy/circulars', department: 'Humanities and Social Sciences', category: 'circulars', deptId: 22 },
  { name: 'EE Circulars', url: 'https://www.ecajmer.ac.in/departments/ee/circulars', department: 'Electrical Engineering', category: 'circulars', deptId: 6 },
  { name: 'EE Timetable', url: 'https://www.ecajmer.ac.in/departments/ee/timetable', department: 'Electrical Engineering', category: 'timetable', deptId: 6 },
  { name: 'EIC Circulars', url: 'https://www.ecajmer.ac.in/departments/eic/circulars', department: 'Electronic Instrumentation & Control', category: 'circulars', deptId: 9 },
  { name: 'EIC Timetable', url: 'https://www.ecajmer.ac.in/departments/eic/timetable', department: 'Electronic Instrumentation & Control', category: 'timetable', deptId: 9 },
  { name: 'English Circulars', url: 'https://www.ecajmer.ac.in/departments/english/circulars', department: 'English & Humanities', category: 'circulars', deptId: 15 },
  { name: 'Maths Circulars', url: 'https://www.ecajmer.ac.in/departments/maths/circulars', department: 'Mathematics', category: 'circulars', deptId: 14 },
  { name: 'MBA Circulars', url: 'https://www.ecajmer.ac.in/departments/mba/circulars', department: 'Management Studies (MBA)', category: 'circulars', deptId: 11 },
  { name: 'MCA Circulars', url: 'https://www.ecajmer.ac.in/departments/mca/circulars', department: 'Computer Applications (MCA)', category: 'circulars', deptId: 10 },
  { name: 'ME Circulars', url: 'https://www.ecajmer.ac.in/departments/me/circulars', department: 'Mechanical Engineering', category: 'circulars', deptId: 8 },
  { name: 'ME Timetable', url: 'https://www.ecajmer.ac.in/departments/me/timetable', department: 'Mechanical Engineering', category: 'timetable', deptId: 8 },
  { name: 'Physics Circulars', url: 'https://www.ecajmer.ac.in/departments/physics/circulars', department: 'Physics', category: 'circulars', deptId: 12 },

  // Others
  { name: 'Training and Placement (TPO)', url: 'https://tpo.ecajmer.ac.in/all-news', department: 'Training & Placement Office', category: 'circulars', deptId: 18 },
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
  const [confirmBatchModalOpen, setConfirmBatchModalOpen] = useState(false)

  // URL Testing State
  const [testingUrl, setTestingUrl] = useState(false)
  const [urlTestResult, setUrlTestResult] = useState<TestUrlResponse | null>(null)


  // ECA-style table pagination controls
  const [pageSize, setPageSize] = useState<number>(10)
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [yearFilter, setYearFilter] = useState<string>('All')

  // Explorer Modal State (Database Documents & Live ECA Notices)
  const [explorerOpen, setExplorerOpen] = useState(false)
  const [explorerSource, setExplorerSource] = useState<IngestionSource | null>(null)
  const [explorerTab, setExplorerTab] = useState<'db' | 'live'>('db')

  // DB Ingested Documents State
  const [dbDocuments, setDbDocuments] = useState<IngestedDocumentItem[]>([])
  const [dbTotal, setDbTotal] = useState(0)
  const [dbLoading, setDbLoading] = useState(false)
  const [dbPageSize, setDbPageSize] = useState(10)
  const [dbCurrentPage, setDbCurrentPage] = useState(1)
  const [dbSearchQuery, setDbSearchQuery] = useState('')

  // Chunk Inspection Modal State
  const [chunkModalDoc, setChunkModalDoc] = useState<IngestedDocumentItem | null>(null)
  const [docChunks, setDocChunks] = useState<DocumentChunkItem[]>([])
  const [chunksLoading, setChunksLoading] = useState(false)

  // Live ECA Notices State (proxied via backend)
  const [liveCirculars, setLiveCirculars] = useState<LiveCircularItem[]>([])
  const [liveLoading, setLiveLoading] = useState(false)
  const [livePageSize, setLivePageSize] = useState(10)
  const [liveCurrentPage, setLiveCurrentPage] = useState(1)
  const [liveTotalItems, setLiveTotalItems] = useState(0)
  const [liveSearchQuery, setLiveSearchQuery] = useState('')

  // Dynamic Departments from PostgreSQL (Simple IDs 1, 2, 3...)
  const [departments, setDepartments] = useState<Department[]>([])
  const [departmentsLoading, setDepartmentsLoading] = useState(false)
  const [newDeptModalOpen, setNewDeptModalOpen] = useState(false)
  const [newDeptForm, setNewDeptForm] = useState({
    name: '',
    code: '',
    category: 'Engineering',
  })

  // Live Pipeline Inspector Modal State
  const [isLiveInspectorOpen, setIsLiveInspectorOpen] = useState(false)
  const [liveInspectorSource, setLiveInspectorSource] = useState<{ id?: string; name?: string } | null>(null)

  const handleOpenLiveInspector = (id?: string, name?: string) => {
    setLiveInspectorSource({ id, name })
    setIsLiveInspectorOpen(true)
  }

  const [formData, setFormData] = useState<SourceCreatePayload>({
    name: '',
    url: '',
    department_id: undefined,
    category: 'circulars',
    priority: 1,
    is_active: true,
    initial_fetch_limit: 10,
    subsequent_fetch_limit: 5,
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

  const loadDepartments = async () => {
    try {
      setDepartmentsLoading(true)
      const data = await getDepartments()
      setDepartments(data)
    } catch (err: any) {
      console.error('Failed to load dynamic departments:', err)
    } finally {
      setDepartmentsLoading(false)
    }
  }

  const handleCreateDepartment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newDeptForm.name.trim()) return
    try {
      const created = await createDepartment(newDeptForm)
      showNotice(`Created department #${created.id}: ${created.name}`)
      await loadDepartments()
      setFormData((prev) => ({ ...prev, department_id: created.id }))
      setNewDeptModalOpen(false)
      setNewDeptForm({ name: '', code: '', category: 'Engineering' })
    } catch (err: any) {
      showNotice(err.message || 'Failed to create department', 'error')
    }
  }

  useEffect(() => {
    loadSources(true)
    loadDepartments()
  }, [])

  // Auto-poll every 5 seconds when any source is actively in "fetching" state
  useEffect(() => {
    const hasActiveFetching = sources.some((s) => s.status === 'fetching')
    if (hasActiveFetching) {
      const interval = setInterval(() => {
        loadSources(false)
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [sources])


  const showNotice = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 4000)
  }

  const handleOpenAdd = () => {
    setEditingSource(null)
    setUrlTestResult(null)
    const nextPriority = sources.length > 0 ? Math.max(...sources.map((s) => s.priority)) + 1 : 1
    setFormData({
      name: '',
      url: '',
      department_id: undefined,
      category: 'circulars',
      priority: nextPriority,
      is_active: true,
      initial_fetch_limit: 10,
      subsequent_fetch_limit: 5,
    })
    setModalOpen(true)
  }

  const handleOpenEdit = (src: IngestionSource) => {
    setEditingSource(src)
    setUrlTestResult(null)
    setFormData({
      name: src.name,
      url: src.url,
      department_id: src.department_id || undefined,
      category: src.category,
      priority: src.priority,
      is_active: src.is_active,
      initial_fetch_limit: src.initial_fetch_limit,
      subsequent_fetch_limit: src.subsequent_fetch_limit,
    })
    setModalOpen(true)
  }

  const handleTestUrl = async () => {
    if (!formData.url.trim()) {
      showNotice('Please enter a URL first to test', 'error')
      return
    }
    try {
      setTestingUrl(true)
      setUrlTestResult(null)
      const res = await testSourceUrl(formData.url)
      setUrlTestResult(res)
      if (res.is_valid) {
        showNotice(`Connection verified! Found ${res.notices_found} circulars. (Status ${res.status_code})`)
      } else {
        showNotice(res.message || 'Page returned error status', 'error')
      }
    } catch (err: any) {
      showNotice(err.message || 'Failed to test source URL', 'error')
    } finally {
      setTestingUrl(false)
    }
  }

  const handleApplyPreset = (preset: HardcodedPrefetchSource) => {
    const nextPriority = sources.length > 0 ? Math.max(...sources.map((s) => s.priority)) + 1 : 1
    setFormData({
      name: preset.name,
      url: preset.url,
      department_id: preset.deptId,
      category: preset.category,
      priority: nextPriority,
      is_active: true,
      initial_fetch_limit: 10,
      subsequent_fetch_limit: 5,
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
      // Optimistically flip status to fetching so Pause button and Fetching pill appear immediately
      setSources((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'fetching' } : s))
      )
      await triggerFetchSource(id)
      showNotice(`Triggered ingestion for "${name}"`)
      setTimeout(loadSources, 2000)
    } catch (err: any) {
      showNotice(err.message || 'Fetch trigger failed', 'error')
      loadSources()
    } finally {
      setActionLoading(null)
    }
  }

  const handlePauseSingle = async (id: string, name: string) => {
    try {
      setActionLoading(id)
      setSources((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'idle' } : s))
      )
      await pauseFetchSource(id)
      showNotice(`Paused ingestion for "${name}"`)
      setTimeout(loadSources, 500)
    } catch (err: any) {
      showNotice(err.message || 'Failed to pause fetching', 'error')
      loadSources()
    } finally {
      setActionLoading(null)
    }
  }

  const handleFetchAll = async () => {
    try {
      setActionLoading('all')
      setSources((prev) =>
        prev.map((s) => (s.is_active ? { ...s, status: 'fetching' } : s))
      )
      await triggerFetchAll()
      showNotice('Queued prioritized batch ingestion across all active sources!')
      setTimeout(loadSources, 2500)
    } catch (err: any) {
      showNotice(err.message || 'Batch fetch trigger failed', 'error')
      loadSources()
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

  // DB Documents Fetcher
  const loadDbDocuments = async (src: IngestionSource, page = 1, limit = 10, search = '') => {
    try {
      setDbLoading(true)
      const res = await getSourceDocuments(src.id, page, limit, search)
      setDbDocuments(res.documents)
      setDbTotal(res.total)
    } catch (err: any) {
      console.error('Failed to load stored documents:', err)
      setDbDocuments([])
      setDbTotal(0)
    } finally {
      setDbLoading(false)
    }
  }

  // Live Circulars Fetcher from backend proxy (no CORS issues)
  const fetchLiveEcaCirculars = async (src: IngestionSource, page = 1, limit = 10, search = '') => {
    try {
      setLiveLoading(true)
      const data = await getSourceLiveFeed(src.id, page, limit, search)
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
      setLiveTotalItems(0)
    } finally {
      setLiveLoading(false)
    }
  }

  const handleOpenExplorer = (src: IngestionSource) => {
    setExplorerSource(src)
    setExplorerTab('db')
    setDbCurrentPage(1)
    setDbPageSize(10)
    setDbSearchQuery('')
    setLiveCurrentPage(1)
    setLivePageSize(10)
    setLiveSearchQuery('')
    setExplorerOpen(true)
    loadDbDocuments(src, 1, 10, '')
    fetchLiveEcaCirculars(src, 1, 10, '')
  }

  const handleOpenChunks = async (doc: IngestedDocumentItem) => {
    if (!explorerSource) return
    setChunkModalDoc(doc)
    setChunksLoading(true)
    try {
      const chunks = await getDocumentChunks(explorerSource.id, doc.id)
      setDocChunks(chunks)
    } catch (err) {
      console.error('Failed to load document chunks:', err)
      setDocChunks([])
    } finally {
      setChunksLoading(false)
    }
  }

  // Filtered Sources
  const filteredSources = sources.filter((src) => {
    const matchesSearch =
      src.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      src.url.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (src.department_id && departments.find(d => d.id === src.department_id)?.name.toLowerCase().includes(searchQuery.toLowerCase()))
    const matchesDept = selectedDeptFilter === 'all' || src.department_id?.toString() === selectedDeptFilter
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

  // DB Documents Pagination calculation
  const dbTotalPages = Math.ceil(dbTotal / dbPageSize) || 1
  const dbStartIdx = dbTotal === 0 ? 0 : (dbCurrentPage - 1) * dbPageSize + 1
  const dbEndIdx = Math.min(dbCurrentPage * dbPageSize, dbTotal)

  // Live Explorer Pagination calculation
  const liveTotalPages = Math.ceil(liveTotalItems / livePageSize) || 1
  const liveStartIdx = (liveCurrentPage - 1) * livePageSize + 1
  const liveEndIdx = Math.min(liveCurrentPage * livePageSize, liveTotalItems)

  return (
    <div
      className={`min-h-screen bg-[#fcfcfc] text-[#18181b] font-['Inter',sans-serif] ${isStandalone ? 'p-4 sm:p-8' : ''
        }`}
    >
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Standalone Header if opened in new tab */}
        {isStandalone && (
          <header className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <img src="/logo-icon.png" alt="EduSync" className="w-10 h-10 rounded-xl object-contain bg-white border border-[#e4e4e7] p-1 shadow-sm" />
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
                <MessageSquare className="w-3.5 h-3.5" />
                <span>Student Chat</span>
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
                className="flex items-center gap-1.5 px-3.5 py-2 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-800 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-xs"
                title="Preload all official departments from ecajmer.ac.in"
              >
                <Layers className="w-3.5 h-3.5 text-neutral-500" />
                Preload Departments
              </button>

              <button
                onClick={() => setConfirmBatchModalOpen(true)}
                disabled={actionLoading === 'all' || sources.length === 0}
                className="flex items-center gap-1.5 px-4 py-2 bg-[#18181b] hover:bg-black text-white rounded-xl text-xs font-semibold shadow-xs transition disabled:opacity-50"
                title="Trigger sequential synchronization across all active sources"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Sync All Sources</span>
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
              className={`p-3.5 rounded-xl text-xs font-medium flex items-center gap-2 ${notification.type === 'success'
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
                <option value="all">All Departments / Sections</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.name}>
                    [#{d.id}] {d.name}
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
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#18181b] hover:bg-black text-white rounded-xl text-xs font-semibold shadow-xs"
                >
                  <Layers className="w-3.5 h-3.5" />
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
                        className={`hover:bg-[#f8f9fa] transition ${!src.is_active ? 'opacity-50 bg-[#fafafa]' : ''
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
                            {departments.find(d => d.id === src.department_id)?.name || 'General'}
                          </span>
                        </td>

                        {/* Category */}
                        <td className="py-3.5 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider ${src.category === 'timetable'
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

                        {/* Status Badge - Clickable to open live pipeline inspector */}
                        <td className="py-3.5 px-3 text-center">
                          {src.status === 'fetching' ? (
                            <button
                              onClick={() => handleOpenLiveInspector(src.id, src.name)}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 rounded-full text-[11px] font-medium cursor-pointer shadow-xs transition"
                              title="Click to view live backend working & step-by-step progress"
                            >
                              <RefreshCw className="w-3 h-3 animate-spin text-amber-600" />
                              <span>Fetching...</span>
                            </button>
                          ) : src.status === 'completed' ? (
                            <button
                              onClick={() => handleOpenLiveInspector(src.id, src.name)}
                              className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-full text-[11px] font-medium cursor-pointer transition"
                              title="Click to inspect pipeline run logs"
                            >
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              <span>Fresh</span>
                            </button>
                          ) : src.status === 'error' ? (
                            <button
                              onClick={() => handleOpenLiveInspector(src.id, src.name)}
                              className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-full text-[11px] font-medium cursor-pointer transition"
                              title={src.error_message || 'Fetch error - click to inspect error logs'}
                            >
                              <AlertCircle className="w-3 h-3 text-rose-600" />
                              <span>Error</span>
                            </button>
                          ) : (
                            <button
                              onClick={() => handleOpenLiveInspector(src.id, src.name)}
                              className="inline-flex items-center gap-1 px-2 py-0.5 bg-neutral-100 hover:bg-neutral-200 text-neutral-600 rounded-full text-[11px] cursor-pointer transition"
                              title="Click to view pipeline status"
                            >
                              <Clock className="w-3 h-3" />
                              <span>Idle</span>
                            </button>
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
                            {src.status === 'fetching' ? (
                              <button
                                onClick={() => handlePauseSingle(src.id, src.name)}
                                disabled={actionLoading === src.id}
                                className="p-1.5 bg-amber-50 hover:bg-amber-600 text-amber-600 hover:text-white rounded-lg border border-amber-200 transition disabled:opacity-40"
                                title="Pause / Stop fetching"
                              >
                                <Pause className="w-3.5 h-3.5 fill-current" />
                              </button>
                            ) : (
                              <button
                                onClick={() => handleFetchSingle(src.id, src.name)}
                                disabled={actionLoading === src.id}
                                className="p-1.5 bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white rounded-lg border border-indigo-200 transition disabled:opacity-40"
                                title="Fetch & Embed now"
                              >
                                <Play className="w-3.5 h-3.5 fill-current" />
                              </button>
                            )}
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

      {/* INGESTED DOCUMENTS & LIVE EXPLORER MODAL */}
      {explorerOpen && explorerSource && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150">
          <div className="bg-white border border-[#e4e4e7] rounded-2xl w-full max-w-5xl shadow-2xl text-[#18181b] max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 sm:p-5 border-b border-[#f0f0f2] flex-shrink-0 bg-white">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-xl">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-[#18181b]">
                      {explorerSource.name}
                    </h3>
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200">
                      {departments.find(d => d.id === explorerSource.department_id)?.name || 'General'}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-500 mt-0.5 flex items-center gap-1.5 truncate max-w-xl">
                    <span>Source Target:</span>
                    <a
                      href={explorerSource.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-600 hover:underline flex items-center gap-1"
                    >
                      {explorerSource.url}
                      <ExternalLink className="w-3 h-3" />
                    </a>
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

            {/* Navigation Tabs (DB Documents vs Live ECA Portal) */}
            <div className="px-5 pt-3 border-b border-[#f0f0f2] flex items-center gap-4 bg-[#fafbfc]">
              <button
                onClick={() => {
                  setExplorerTab('db')
                  loadDbDocuments(explorerSource, 1, dbPageSize, dbSearchQuery)
                }}
                className={`pb-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${explorerTab === 'db'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-neutral-500 hover:text-neutral-900'
                  }`}
              >
                <Database className="w-4 h-4" />
                <span>Stored in EduSync DB</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-100 text-indigo-700 font-bold">
                  {dbTotal}
                </span>
              </button>

              <button
                onClick={() => {
                  setExplorerTab('live')
                  fetchLiveEcaCirculars(explorerSource, 1, livePageSize, liveSearchQuery)
                }}
                className={`pb-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${explorerTab === 'live'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-neutral-500 hover:text-neutral-900'
                  }`}
              >
                <Globe className="w-4 h-4" />
                <span>Live ECA Portal Feed</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-neutral-200 text-neutral-700 font-bold">
                  {liveTotalItems}
                </span>
              </button>
            </div>

            {/* TAB CONTENT */}
            {explorerTab === 'db' ? (
              <div className="p-4 flex-1 flex flex-col overflow-hidden space-y-3">
                {/* Search & Pagination Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
                  <div className="relative flex-1 min-w-[220px] max-w-md">
                    <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search stored notices by title, S.No, or OCR content..."
                      value={dbSearchQuery}
                      onChange={(e) => {
                        setDbSearchQuery(e.target.value)
                        setDbCurrentPage(1)
                        loadDbDocuments(explorerSource, 1, dbPageSize, e.target.value)
                      }}
                      className="w-full pl-9 pr-3 py-1.5 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] placeholder-neutral-400 focus:outline-none"
                    />
                  </div>

                  <div className="flex items-center gap-3 text-xs text-neutral-600 flex-wrap">
                    <div>
                      Showing <span className="font-semibold text-neutral-900">{dbStartIdx} - {dbEndIdx}</span> of{' '}
                      <span className="font-semibold text-neutral-900">{dbTotal}</span> stored documents
                    </div>

                    <div className="flex items-center gap-1.5">
                      <span className="text-neutral-500">Show:</span>
                      <select
                        value={dbPageSize}
                        onChange={(e) => {
                          const newLimit = Number(e.target.value)
                          setDbPageSize(newLimit)
                          setDbCurrentPage(1)
                          loadDbDocuments(explorerSource, 1, newLimit, dbSearchQuery)
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
                      <select
                        value={dbCurrentPage}
                        onChange={(e) => {
                          const newP = Number(e.target.value)
                          setDbCurrentPage(newP)
                          loadDbDocuments(explorerSource, newP, dbPageSize, dbSearchQuery)
                        }}
                        className="px-2 py-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-semibold text-neutral-800 focus:outline-none cursor-pointer"
                      >
                        {Array.from({ length: dbTotalPages }, (_, i) => i + 1).map((p) => (
                          <option key={p} value={p}>
                            {String(p).padStart(2, '0')}
                          </option>
                        ))}
                      </select>
                      <span className="text-neutral-500">of {dbTotalPages} Pages</span>

                      <button
                        onClick={() => {
                          const p = Math.max(1, dbCurrentPage - 1)
                          setDbCurrentPage(p)
                          loadDbDocuments(explorerSource, p, dbPageSize, dbSearchQuery)
                        }}
                        disabled={dbCurrentPage === 1}
                        className="p-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg hover:bg-neutral-200 disabled:opacity-30 transition"
                        title="Previous Page"
                      >
                        <ChevronLeft className="w-3.5 h-3.5 text-neutral-700" />
                      </button>

                      <button
                        onClick={() => {
                          const p = Math.min(dbTotalPages, dbCurrentPage + 1)
                          setDbCurrentPage(p)
                          loadDbDocuments(explorerSource, p, dbPageSize, dbSearchQuery)
                        }}
                        disabled={dbCurrentPage >= dbTotalPages}
                        className="p-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg hover:bg-neutral-200 disabled:opacity-30 transition"
                        title="Next Page"
                      >
                        <ChevronRight className="w-3.5 h-3.5 text-neutral-700" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Stored Documents Table */}
                <div className="overflow-y-auto flex-1 border border-[#e4e4e7] rounded-xl">
                  {dbLoading ? (
                    <div className="py-16 flex flex-col items-center justify-center text-neutral-500 gap-3">
                      <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
                      <span className="text-sm">Loading ingested documents from database...</span>
                    </div>
                  ) : dbDocuments.length === 0 ? (
                    <div className="py-16 text-center text-neutral-500 text-xs">
                      No documents found in database for this selection. Click "Fetch & Embed" on this source to ingest notices.
                    </div>
                  ) : (
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-[#f8f9fa] border-b border-[#e4e4e7] text-[11px] font-bold text-neutral-500 uppercase tracking-wider sticky top-0">
                          <th className="py-3 px-4 w-32">S.No</th>
                          <th className="py-3 px-4 w-28">Date</th>
                          <th className="py-3 px-4">Document / Notice Title</th>
                          <th className="py-3 px-4 w-36 text-center">Status & Chunks</th>
                          <th className="py-3 px-4 w-40 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#ebecee] text-xs">
                        {dbDocuments.map((doc) => (
                          <tr key={doc.id} className="hover:bg-[#f8f9fa] transition">
                            <td className="py-3 px-4 font-mono font-medium text-neutral-700">
                              {doc.notice_sno || `#${doc.id.slice(0, 8)}`}
                            </td>
                            <td className="py-3 px-4 text-neutral-600">
                              {doc.notice_date ||
                                (doc.ingested_at
                                  ? new Date(doc.ingested_at).toLocaleDateString([], {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                  })
                                  : 'N/A')}
                            </td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-[#18181b]">{doc.title}</div>
                              <div className="text-[11px] text-neutral-400 font-mono truncate max-w-md mt-0.5">
                                {doc.source_url}
                              </div>
                            </td>
                            <td className="py-3 px-4 text-center">
                              <div className="inline-flex items-center gap-1.5">
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md text-[10px] font-semibold uppercase">
                                  <CheckCircle2 className="w-2.5 h-2.5" />
                                  {doc.status}
                                </span>
                                <span className="px-2 py-0.5 bg-neutral-100 text-neutral-700 border border-neutral-200 rounded-md text-[10px] font-semibold">
                                  {doc.chunk_count} chunks
                                </span>
                              </div>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => handleOpenChunks(doc)}
                                  className="inline-flex items-center gap-1 px-2 py-1 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 rounded-lg text-xs font-semibold border border-neutral-200 transition"
                                  title="Inspect extracted chunks and embeddings"
                                >
                                  <FileCode className="w-3.5 h-3.5 text-neutral-500" />
                                  <span>Chunks</span>
                                </button>
                                {doc.source_url && (
                                  <a
                                    href={doc.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white rounded-lg text-xs font-semibold border border-indigo-200 transition"
                                  >
                                    <span>View PDF</span>
                                    <ExternalLink className="w-3 h-3" />
                                  </a>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            ) : (
              /* LIVE ECA PORTAL FEED TAB */
              <div className="p-4 flex-1 flex flex-col overflow-hidden space-y-3">
                {/* Search & Pagination Bar */}
                <div className="flex flex-wrap items-center justify-between gap-3 flex-shrink-0">
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

                  <div className="flex items-center gap-3 text-xs text-neutral-600 flex-wrap">
                    <div>
                      Showing <span className="font-semibold text-neutral-900">{liveStartIdx} - {liveEndIdx}</span> of{' '}
                      <span className="font-semibold text-neutral-900">{liveTotalItems}</span> live entries
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

                {/* Live ECA Table */}
                <div className="overflow-y-auto flex-1 border border-[#e4e4e7] rounded-xl">
                  {liveLoading ? (
                    <div className="py-16 flex flex-col items-center justify-center text-neutral-500 gap-3">
                      <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
                      <span className="text-sm">Fetching live circulars from ECA portal via proxy...</span>
                    </div>
                  ) : liveCirculars.length === 0 ? (
                    <div className="py-16 text-center text-neutral-500 text-xs">
                      No circulars found on ECA portal for this selection.
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
              </div>
            )}

            {/* Modal Footer */}
            <div className="p-4 border-t border-[#f0f0f2] flex items-center justify-between text-xs text-neutral-500 flex-shrink-0 bg-white">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>
                  {explorerTab === 'db'
                    ? `Connected to PostgreSQL • Showing ${dbDocuments.length} of ${dbTotal} ingested documents`
                    : `Proxied through backend • Connected to ecajmer.ac.in`}
                </span>
              </div>
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

      {/* CHUNK INSPECTION SUB-MODAL */}
      {chunkModalDoc && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60] flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white border border-[#e4e4e7] rounded-2xl w-full max-w-3xl shadow-2xl text-[#18181b] max-h-[85vh] flex flex-col overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#f0f0f2] bg-white">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-purple-50 border border-purple-100 text-purple-600 rounded-xl">
                  <FileCode className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-[#18181b]">{chunkModalDoc.title}</h4>
                  <p className="text-[11px] text-neutral-500 font-mono mt-0.5">
                    ID: {chunkModalDoc.id} &bull; SHA256: {chunkModalDoc.content_hash.slice(0, 16)}...
                  </p>
                </div>
              </div>
              <button
                onClick={() => setChunkModalDoc(null)}
                className="p-1 text-neutral-400 hover:text-neutral-900 rounded-lg hover:bg-neutral-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 overflow-y-auto flex-1 space-y-3 bg-[#fafbfc]">
              {chunksLoading ? (
                <div className="py-12 flex flex-col items-center justify-center text-neutral-500 gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-purple-600" />
                  <span className="text-xs">Loading chunks and token counts...</span>
                </div>
              ) : docChunks.length === 0 ? (
                <div className="py-12 text-center text-neutral-500 text-xs">No chunks found for this document.</div>
              ) : (
                docChunks.map((chunk, index) => (
                  <div
                    key={chunk.id}
                    className="p-3.5 bg-white border border-[#e4e4e7] rounded-xl shadow-sm text-xs space-y-2"
                  >
                    <div className="flex items-center justify-between text-[11px] text-neutral-500 border-b border-neutral-100 pb-2">
                      <span className="font-semibold text-neutral-800">Chunk #{index + 1}</span>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded font-mono font-medium">
                          {chunk.token_count} tokens
                        </span>
                        <span>{new Date(chunk.last_verified).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    </div>
                    <pre className="text-[11px] font-mono text-neutral-800 whitespace-pre-wrap bg-[#f8f9fa] p-2.5 rounded-lg border border-neutral-200 overflow-x-auto max-h-48">
                      {chunk.content}
                    </pre>
                  </div>
                ))
              )}
            </div>

            <div className="p-3 border-t border-[#f0f0f2] flex justify-end bg-white">
              <button
                onClick={() => setChunkModalDoc(null)}
                className="px-3.5 py-1.5 bg-neutral-100 hover:bg-neutral-200 text-neutral-800 rounded-lg text-xs font-semibold"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add / Edit Source Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150">
          <div className="bg-white border border-[#e4e4e7] rounded-2xl w-full max-w-xl max-h-[88vh] sm:max-h-[90vh] flex flex-col shadow-2xl text-[#18181b] overflow-hidden">
            {/* Sticky Header */}
            <div className="flex items-center justify-between p-4 sm:p-5 border-b border-[#f0f0f2] flex-shrink-0 bg-white">
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

            {/* Scrollable Form Body */}
            <form onSubmit={handleSave} className="flex flex-col flex-1 min-h-0 overflow-hidden">
              <div className="overflow-y-auto p-4 sm:p-5 space-y-4 flex-1">
                {/* Categorized Official Presets Selector */}
                {!editingSource && (
                  <div className="p-3.5 bg-neutral-50 border border-neutral-200 rounded-xl space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="text-[11px] font-bold text-neutral-700 uppercase tracking-wider flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5 text-neutral-500" />
                        <span>Official Department Presets</span>
                      </div>
                      <span className="text-[10px] text-neutral-500">1-Click Fast Pick</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {HARDCODED_PREFETCH_SOURCES.map((preset) => (
                        <button
                          key={preset.url}
                          type="button"
                          onClick={() => handleApplyPreset(preset)}
                          className="flex items-center justify-between p-2.5 bg-white hover:bg-indigo-50/70 border border-neutral-200 hover:border-indigo-300 rounded-xl text-left transition shadow-xs group"
                        >
                          <div className="min-w-0 pr-2">
                            <div className="text-xs font-semibold text-neutral-900 truncate group-hover:text-indigo-700">
                              {preset.name}
                            </div>
                            <div className="text-[10px] text-neutral-500 truncate">
                              {preset.department}
                            </div>
                          </div>
                          <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 shrink-0">
                            #{preset.deptId}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

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
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-semibold text-neutral-700">
                      Source URL on ecajmer.ac.in *
                    </label>
                    <button
                      type="button"
                      onClick={handleTestUrl}
                      disabled={testingUrl || !formData.url.trim()}
                      className="text-[11px] font-semibold text-neutral-700 hover:text-neutral-900 flex items-center gap-1 disabled:opacity-40 cursor-pointer"
                    >
                      <RefreshCw className={`w-3 h-3 ${testingUrl ? 'animate-spin' : ''}`} />
                      <span>{testingUrl ? 'Testing...' : 'Test Connection'}</span>
                    </button>
                  </div>
                  <input
                    type="url"
                    required
                    value={formData.url}
                    onChange={(e) => {
                      setFormData({ ...formData, url: e.target.value })
                      setUrlTestResult(null)
                    }}
                    placeholder="https://www.ecajmer.ac.in/departments/cs-it/circulars"
                    className="w-full px-3.5 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] placeholder-neutral-400 focus:outline-none focus:border-neutral-400"
                  />
                  {urlTestResult && (
                    <div
                      className={`mt-1.5 p-2 rounded-lg text-[11px] font-medium flex items-center gap-1.5 ${urlTestResult.is_valid
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : 'bg-rose-50 text-rose-800 border border-rose-200'
                        }`}
                    >
                      {urlTestResult.is_valid ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          <span>
                            Verified live ({urlTestResult.status_code}): Discovered {urlTestResult.notices_found} notices/circulars.
                          </span>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                          <span>
                            Connection check failed: {urlTestResult.message || `HTTP ${urlTestResult.status_code}`}
                          </span>
                        </>
                      )}
                    </div>
                  )}
                  <p className="text-[11px] text-neutral-500 mt-1">
                    Attached PDF notices and timetables will be downloaded and embedded automatically.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-semibold text-neutral-700">Department / Section</label>
                      <button
                        type="button"
                        onClick={() => setNewDeptModalOpen(true)}
                        className="text-[11px] font-medium text-indigo-600 hover:text-indigo-800 flex items-center gap-0.5"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Add Section</span>
                      </button>
                    </div>
                    <select
                      value={formData.department_id || ''}
                      onChange={(e) => setFormData({ ...formData, department_id: parseInt(e.target.value) || undefined })}
                      className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                    >
                      {departmentsLoading ? (
                        <option value="">Loading sections...</option>
                      ) : (
                        departments.map((dept) => (
                          <option key={dept.id} value={dept.name}>
                            [#{dept.id}] {dept.name} ({dept.code || dept.category})
                          </option>
                        ))
                      )}
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
                      value={formData.initial_fetch_limit || 10}
                      onChange={(e) =>
                        setFormData({ ...formData, initial_fetch_limit: parseInt(e.target.value) || 10 })
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
                      value={formData.subsequent_fetch_limit || 5}
                      onChange={(e) =>
                        setFormData({ ...formData, subsequent_fetch_limit: parseInt(e.target.value) || 5 })
                      }
                      className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
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
              </div>

              {/* Sticky Footer */}
              <div className="p-4 sm:p-5 bg-neutral-50/90 border-t border-[#f0f0f2] flex items-center justify-end gap-3 flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 bg-white border border-[#d4d4d8] hover:bg-neutral-100 text-neutral-700 rounded-xl text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#18181b] hover:bg-black text-white rounded-xl text-xs font-semibold shadow-sm transition active:scale-95"
                >
                  {editingSource ? 'Update Source' : 'Add Source'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Universal Sync All Confirmation Modal */}
      {confirmBatchModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150">
          <div className="bg-white border border-[#e4e4e7] rounded-2xl w-full max-w-lg max-h-[88vh] sm:max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Sticky Header */}
            <div className="p-4 sm:p-5 border-b border-[#f0f0f2] flex items-center justify-between flex-shrink-0 bg-white">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600 shadow-sm">
                  <RefreshCw className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-[#18181b]">Synchronize All Data Sources</h3>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    Process all {activeCount} active sources in sequential priority order
                  </p>
                </div>
              </div>
              <button
                onClick={() => setConfirmBatchModalOpen(false)}
                className="w-8 h-8 rounded-lg hover:bg-neutral-100 flex items-center justify-center text-neutral-500 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Scrollable Content */}
            <div className="overflow-y-auto p-4 sm:p-5 space-y-4 text-xs text-neutral-600 leading-relaxed flex-1">
              <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-3.5 space-y-2">
                <p className="font-semibold text-neutral-800">What will happen during synchronization:</p>
                <ul className="space-y-1.5 text-neutral-600 list-disc list-inside">
                  <li>Crawls official circulars & downloads PDF attachments in <strong>priority sequence (#1 to #{sources.length})</strong>.</li>
                  <li>Computes <strong>SHA-256 content hashes</strong> to skip unchanged files and re-embed only new/updated circulars.</li>
                  <li>Generates 384-dimensional vector embeddings and upserts them to PostgreSQL (pgvector).</li>
                  <li>Each source status updates live from <span className="text-amber-700 font-semibold bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">fetching</span> to <span className="text-emerald-700 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">completed</span>.</li>
                </ul>
              </div>

              <div>
                <span className="font-semibold text-neutral-700 block mb-2">
                  Sequential Queue Preview ({activeCount} Sources):
                </span>
                <div className="max-h-32 overflow-y-auto space-y-1 border border-neutral-200 rounded-xl p-2 bg-white">
                  {sources
                    .filter((s) => s.is_active)
                    .sort((a, b) => a.priority - b.priority)
                    .map((s, idx) => (
                      <div key={s.id} className="flex items-center justify-between text-[11px] px-2.5 py-1 bg-neutral-50 rounded-lg">
                        <span className="font-medium text-neutral-800 truncate max-w-[280px]">
                          #{idx + 1}. {s.name}
                        </span>
                        <span className="text-neutral-400 shrink-0 text-[10px]">{departments.find(d => d.id === s.department_id)?.name || s.category}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>

            {/* Sticky Footer */}
            <div className="p-4 sm:p-5 bg-neutral-50/90 border-t border-[#f0f0f2] flex items-center justify-end gap-3 flex-shrink-0">
              <button
                type="button"
                onClick={() => setConfirmBatchModalOpen(false)}
                className="px-4 py-2 bg-white border border-[#d4d4d8] hover:bg-neutral-100 text-neutral-700 rounded-xl text-xs font-semibold transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmBatchModalOpen(false)
                  handleFetchAll()
                }}
                disabled={actionLoading === 'all'}
                className="flex items-center gap-1.5 px-5 py-2 bg-[#18181b] hover:bg-black text-white rounded-xl text-xs font-semibold shadow-xs transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Confirm & Sync All</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ADD NEW DEPARTMENT / SECTION MODAL */}
      {newDeptModalOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-neutral-200 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-4 border-b border-neutral-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg">
                  <Database className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-neutral-900">Add New Department / Section</h3>
                  <p className="text-[11px] text-neutral-500">Assigned a simple ID number automatically in database</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setNewDeptModalOpen(false)}
                className="text-neutral-400 hover:text-neutral-600 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateDepartment} className="p-4 space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-neutral-700 mb-1">
                  Section / Department Name *
                </label>
                <input
                  type="text"
                  required
                  value={newDeptForm.name}
                  onChange={(e) => setNewDeptForm({ ...newDeptForm, name: e.target.value })}
                  placeholder="e.g. Sports & Cultural Committee"
                  className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Code / Abbreviation
                  </label>
                  <input
                    type="text"
                    value={newDeptForm.code}
                    onChange={(e) => setNewDeptForm({ ...newDeptForm, code: e.target.value })}
                    placeholder="e.g. SPORTS"
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-neutral-700 mb-1">
                    Category
                  </label>
                  <select
                    value={newDeptForm.category}
                    onChange={(e) => setNewDeptForm({ ...newDeptForm, category: e.target.value })}
                    className="w-full px-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-[#18181b] focus:outline-none"
                  >
                    <option value="Engineering">Engineering</option>
                    <option value="Basic Sciences">Basic Sciences</option>
                    <option value="Administration">Administration</option>
                    <option value="Cell / Committee">Cell / Committee</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-2 border-t border-neutral-100">
                <button
                  type="button"
                  onClick={() => setNewDeptModalOpen(false)}
                  className="px-3.5 py-1.5 text-xs text-neutral-600 hover:text-neutral-900"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-xs"
                >
                  Save Section
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Live Ingestion Pipeline Inspector Modal */}
      <LivePipelineModal
        isOpen={isLiveInspectorOpen}
        onClose={() => setIsLiveInspectorOpen(false)}
        sourceId={liveInspectorSource?.id}
        sourceName={liveInspectorSource?.name}
      />
    </div>
  )
}

