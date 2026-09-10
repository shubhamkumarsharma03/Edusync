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
  Eye,
  Globe,
  FileCode,
} from 'lucide-react'

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
  triggerFetchAll,
  seedDefaultSources,
  getSourceDocuments,
  getDocumentChunks,
  getSourceLiveFeed,
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
  'Accounts Section',
  'Proctor Section',
  'Store Section',
  'First Year Cell',
  'ERP Cell',
  'Central Library',
  'Training & Placement Cell',
  'Startup Cell',
  'Institution\'s Innovation Cell (IIC)',
  'Industry Institute Interaction Cell (IIIC)',
  'AI/ML Club (CSE)',
  'National Innovation & Startup Policy',
  'Scholarship Cell',
  'Student / Parent Grievance Cell',
  'SC/ST/OBC Cell',
  'Women Cell',
  'Psychological Counseling & Mental Health Cell',
  'Hostels Section',
  'Sports Department',
  'National Service Scheme (NSS)',
  'National Cadet Corps (NCC)',
  'Unnat Bharat Abhiyan (UBA)',
  'Nasha Mukti Abhiyan (NMA)',
  'Alumni Cell',
  'AICTE Cell',
  'Student Activity Center',
  'Student Achievements',
  'Academic Calendar',
  'General Administration',
]

export interface PresetSource {
  name: string
  url: string
  department: string
  category: 'circulars' | 'timetable' | 'announcements' | 'general_html'
  group: string
}

const QUICK_PRESETS: PresetSource[] = [
  // 1. Engineering & Academic Departments
  {
    name: 'CSE Circulars & Notices',
    url: 'https://www.ecajmer.ac.in/departments/cs-it/circulars',
    department: 'Computer Science and Engineering',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'CSE Time Tables',
    url: 'https://www.ecajmer.ac.in/departments/cs-it/timetable',
    department: 'Computer Science and Engineering',
    category: 'timetable',
    group: 'Academic Departments',
  },
  {
    name: 'Civil Engineering Circulars',
    url: 'https://www.ecajmer.ac.in/departments/ce/circulars',
    department: 'Civil Engineering',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Electrical Engineering Circulars',
    url: 'https://www.ecajmer.ac.in/departments/ee/circulars',
    department: 'Electrical Engineering',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Electronics & Comm. Circulars',
    url: 'https://www.ecajmer.ac.in/departments/ece/circulars',
    department: 'Electronics and Communication Engineering',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'EIC Department Circulars',
    url: 'https://www.ecajmer.ac.in/departments/eic/circulars',
    department: 'Electronic Instrumentation And Control Engineering',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Mechanical Engineering Circulars',
    url: 'https://www.ecajmer.ac.in/departments/me/circulars',
    department: 'Mechanical Engineering',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Computer Applications (MCA) Circulars',
    url: 'https://www.ecajmer.ac.in/departments/mca/circulars',
    department: 'Computer Applications',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Management Studies (MBA) Circulars',
    url: 'https://www.ecajmer.ac.in/departments/mba/circulars',
    department: 'Management Studies',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Physics Department Circulars',
    url: 'https://www.ecajmer.ac.in/departments/physics/circulars',
    department: 'Physics',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Chemistry Department Circulars',
    url: 'https://www.ecajmer.ac.in/departments/chemistry/circulars',
    department: 'Chemistry',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Mathematics Department Circulars',
    url: 'https://www.ecajmer.ac.in/departments/maths/circulars',
    department: 'Mathematics',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'English Department Circulars',
    url: 'https://www.ecajmer.ac.in/departments/english/circulars',
    department: 'English',
    category: 'circulars',
    group: 'Academic Departments',
  },
  {
    name: 'Economics Department Circulars',
    url: 'https://www.ecajmer.ac.in/departments/economy/circulars',
    department: 'Economics',
    category: 'circulars',
    group: 'Academic Departments',
  },

  // 2. Core Administration & Examination Sections
  {
    name: 'Examination Section Circulars',
    url: 'https://www.ecajmer.ac.in/ui/cells/examination-section/circulars',
    department: 'Examination Section',
    category: 'circulars',
    group: 'Administration & Exams',
  },
  {
    name: 'Registrar Circulars & Orders',
    url: 'https://www.ecajmer.ac.in/ui/cells/registrar/circulars',
    department: 'Registrar Section',
    category: 'circulars',
    group: 'Administration & Exams',
  },
  {
    name: 'Academic Section Circulars',
    url: 'https://www.ecajmer.ac.in/ui/cells/academic-section/circulars',
    department: 'Academic Section',
    category: 'circulars',
    group: 'Administration & Exams',
  },
  {
    name: 'Academic Calendar 2025-26',
    url: 'https://www.ecajmer.ac.in/academics/academic-calendar',
    department: 'Academic Section',
    category: 'general_html',
    group: 'Administration & Exams',
  },
  {
    name: 'First Year Cell Circulars',
    url: 'https://www.ecajmer.ac.in/ui/cells/first-year',
    department: 'First Year Cell',
    category: 'circulars',
    group: 'Administration & Exams',
  },
  {
    name: 'Account Section & Fees',
    url: 'https://www.ecajmer.ac.in/ui/cells/accounts',
    department: 'Accounts Section',
    category: 'general_html',
    group: 'Administration & Exams',
  },
  {
    name: 'Proctor Section Notices',
    url: 'https://www.ecajmer.ac.in/ui/cells/proctor',
    department: 'Proctor Section',
    category: 'general_html',
    group: 'Administration & Exams',
  },
  {
    name: 'Store Section',
    url: 'https://www.ecajmer.ac.in/ui/cells/stores',
    department: 'Store Section',
    category: 'general_html',
    group: 'Administration & Exams',
  },
  {
    name: 'ERP Cell',
    url: 'https://www.ecajmer.ac.in/ui/cells/erp-cell',
    department: 'ERP Cell',
    category: 'general_html',
    group: 'Administration & Exams',
  },
  {
    name: 'AICTE Cell',
    url: 'https://www.ecajmer.ac.in/ui/cells/aicte',
    department: 'AICTE Cell',
    category: 'general_html',
    group: 'Administration & Exams',
  },

  // 3. Curriculum, Courses & Research
  {
    name: 'UG Courses & Schemes',
    url: 'https://www.ecajmer.ac.in/ui/cells/ug-courses',
    department: 'Academic Section',
    category: 'general_html',
    group: 'Curriculum & Courses',
  },
  {
    name: 'PG Courses (M.Tech/MCA/MBA)',
    url: 'https://www.ecajmer.ac.in/ui/cells/pg-courses',
    department: 'Academic Section',
    category: 'general_html',
    group: 'Curriculum & Courses',
  },
  {
    name: 'PhD Research Cell',
    url: 'https://www.ecajmer.ac.in/ui/cells/phd',
    department: 'Academic Section',
    category: 'general_html',
    group: 'Curriculum & Courses',
  },
  {
    name: 'MOOC Courses Portal',
    url: 'https://www.ecajmer.ac.in/MoocCourses',
    department: 'Academic Section',
    category: 'general_html',
    group: 'Curriculum & Courses',
  },

  // 4. Training, Placements & Innovation Cells
  {
    name: 'Training & Placement Office (TPO)',
    url: 'https://tpo.ecajmer.ac.in/',
    department: 'Training & Placement Cell',
    category: 'general_html',
    group: 'Placements & Innovation',
  },
  {
    name: 'Startup Cell ECA',
    url: 'https://www.ecajmer.ac.in/ui/cells/startup-cell',
    department: 'Startup Cell',
    category: 'general_html',
    group: 'Placements & Innovation',
  },
  {
    name: 'Institution Innovation Council (IIC)',
    url: 'https://www.ecajmer.ac.in/ui/cells/iic-cell',
    department: 'Institution\'s Innovation Cell (IIC)',
    category: 'general_html',
    group: 'Placements & Innovation',
  },
  {
    name: 'Industry Institute Interaction (IIIC)',
    url: 'https://www.ecajmer.ac.in/ui/cells/iii-cell',
    department: 'Industry Institute Interaction Cell (IIIC)',
    category: 'general_html',
    group: 'Placements & Innovation',
  },
  {
    name: 'AI/ML Club (CSE Department)',
    url: 'https://www.ecajmer.ac.in/ui/cells/aimlclub',
    department: 'Computer Science and Engineering',
    category: 'general_html',
    group: 'Placements & Innovation',
  },
  {
    name: 'National Innovation & Startup Policy',
    url: 'https://www.ecajmer.ac.in/nationalialnnovationandstartuppolicy',
    department: 'Startup Cell',
    category: 'general_html',
    group: 'Placements & Innovation',
  },
  {
    name: 'MOUs with Companies & Industry',
    url: 'https://www.ecajmer.ac.in/MousWithCompanies',
    department: 'Training & Placement Cell',
    category: 'general_html',
    group: 'Placements & Innovation',
  },

  // 5. Student Welfare, Services & Facilities
  {
    name: 'Scholarship Details & Notices',
    url: 'https://www.ecajmer.ac.in/ui/cells/scholarship-details',
    department: 'Scholarship Cell',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Student / Parent Grievance Cell',
    url: 'https://www.ecajmer.ac.in/ui/cells/grievance',
    department: 'Student / Parent Grievance Cell',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'SC/ST/OBC Cell',
    url: 'https://www.ecajmer.ac.in/ui/cells/stsc',
    department: 'SC/ST/OBC Cell',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Women Cell & Grievance',
    url: 'https://www.ecajmer.ac.in/ui/cells/women-cell',
    department: 'Women Cell',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Mental Health & Counseling (MHC)',
    url: 'https://www.ecajmer.ac.in/ui/cells/mhc',
    department: 'Psychological Counseling & Mental Health Cell',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Central Library & E-Resources',
    url: 'https://www.ecajmer.ac.in/ui/cells/central-library',
    department: 'Central Library',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'E-Resources & E-Learning',
    url: 'https://www.ecajmer.ac.in/EResources',
    department: 'Central Library',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Campus Hostels',
    url: 'https://www.ecajmer.ac.in/ui/cells/hostels',
    department: 'Hostels Section',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Sports Department',
    url: 'https://www.ecajmer.ac.in/ui/cells/sports-department',
    department: 'Sports Department',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'National Service Scheme (NSS)',
    url: 'https://www.ecajmer.ac.in/ui/cells/nss',
    department: 'National Service Scheme (NSS)',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'National Cadet Corps (NCC)',
    url: 'https://www.ecajmer.ac.in/ui/cells/ncc',
    department: 'National Cadet Corps (NCC)',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Unnat Bharat Abhiyan (UBA)',
    url: 'https://www.ecajmer.ac.in/ui/cells/uba',
    department: 'Unnat Bharat Abhiyan (UBA)',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Nasha Mukti Abhiyan (NMA)',
    url: 'https://www.ecajmer.ac.in/ui/cells/nma',
    department: 'Nasha Mukti Abhiyan (NMA)',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Creative Art Society (CAS)',
    url: 'https://www.ecajmer.ac.in/ui/cells/cas',
    department: 'Student Activity Center',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Admission Corner & Enquiry',
    url: 'https://www.ecajmer.ac.in/ui/admission-enquiry',
    department: 'Academic Section',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },
  {
    name: 'Alumni Cell',
    url: 'https://www.ecajmer.ac.in/ui/cells/alumni-cell',
    department: 'Alumni Cell',
    category: 'general_html',
    group: 'Student Welfare & Services',
  },

  // 6. Institutional Policies & Governance
  {
    name: 'Principal Message & Leadership',
    url: 'https://www.ecajmer.ac.in/administration/PrincipalMessage',
    department: 'General Administration',
    category: 'general_html',
    group: 'Governance & Policies',
  },
  {
    name: 'BOG (Minutes of Meetings)',
    url: 'https://www.ecajmer.ac.in/administration/bog/Minutes-of-meetings',
    department: 'General Administration',
    category: 'general_html',
    group: 'Governance & Policies',
  },
  {
    name: 'Mandatory Disclosure',
    url: 'https://www.ecajmer.ac.in/mandatorydisclousure',
    department: 'General Administration',
    category: 'general_html',
    group: 'Governance & Policies',
  },
  {
    name: 'Annual Reports',
    url: 'https://www.ecajmer.ac.in/AnnualReports',
    department: 'General Administration',
    category: 'general_html',
    group: 'Governance & Policies',
  },
  {
    name: 'Audit Report & Balance Sheets',
    url: 'https://www.ecajmer.ac.in/AuditReportandbalanaceSheets',
    department: 'Accounts Section',
    category: 'general_html',
    group: 'Governance & Policies',
  },
  {
    name: 'Higher Education Policy Document',
    url: 'https://www.ecajmer.ac.in/assets/highereducationpolicy-Bi6EbfuP.pdf',
    department: 'General Administration',
    category: 'general_html',
    group: 'Governance & Policies',
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
  const [confirmBatchModalOpen, setConfirmBatchModalOpen] = useState(false)


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

  const [formData, setFormData] = useState<SourceCreatePayload>({
    name: '',
    url: '',
    department: 'Computer Science and Engineering',
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
      initial_fetch_limit: 10,
      subsequent_fetch_limit: 5,
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
      className={`min-h-screen bg-[#fcfcfc] text-[#18181b] font-['Inter',sans-serif] ${
        isStandalone ? 'p-4 sm:p-8' : ''
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
                onClick={() => setConfirmBatchModalOpen(true)}
                disabled={actionLoading === 'all' || sources.length === 0}
                className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 text-white rounded-xl text-xs font-semibold shadow-sm transition active:scale-95 disabled:opacity-50"
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

          {/* Live Active Synchronization Status Banner */}
          {sources.some((s) => s.status === 'fetching') && (
            <div className="bg-indigo-50/90 border border-indigo-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs text-indigo-950 shadow-sm animate-pulse">
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-600"></span>
                </span>
                <span className="font-bold text-indigo-900">
                  Data Synchronization Active:
                </span>
                <span className="text-indigo-800">
                  Currently syncing & embedding: <strong className="underline">{sources.find((s) => s.status === 'fetching')?.name || 'next source in queue'}</strong>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded-md border border-indigo-200">
                  Auto-Syncing (2.5s)
                </span>
              </div>
            </div>
          )}


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
                      {explorerSource.department || 'General'}
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
                className={`pb-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
                  explorerTab === 'db'
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
                className={`pb-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition ${
                  explorerTab === 'live'
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
                        <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                        <span>Official ECA Portals (Auto-Fill)</span>
                      </div>
                      <span className="text-[10px] text-neutral-500">Select to fill fields</span>
                    </div>

                    {/* Categorized Group Dropdown */}
                    <select
                      onChange={(e) => {
                        const found = QUICK_PRESETS.find((p) => p.url === e.target.value)
                        if (found) handleApplyPreset(found)
                      }}
                      defaultValue=""
                      className="w-full px-3 py-2 bg-white border border-[#d4d4d8] rounded-xl text-xs text-[#18181b] font-medium focus:outline-none focus:border-indigo-600 shadow-sm"
                    >
                      <option value="" disabled>
                        -- ⚡ Choose an official ECA department or cell to auto-fill --
                      </option>
                      {Array.from(new Set(QUICK_PRESETS.map((p) => p.group))).map((groupName) => (
                        <optgroup key={groupName} label={`📁 ${groupName}`}>
                          {QUICK_PRESETS.filter((p) => p.group === groupName).map((p) => (
                            <option key={p.url} value={p.url}>
                              {p.name} — {p.department}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>

                    {/* Popular Fast-Pick Chips */}
                    <div>
                      <span className="text-[10px] font-semibold text-neutral-400 block mb-1.5 uppercase">
                        Quick Fast-Picks:
                      </span>
                      <div className="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto">
                        {QUICK_PRESETS.slice(0, 8).map((preset) => (
                          <button
                            key={preset.name}
                            type="button"
                            onClick={() => handleApplyPreset(preset)}
                            className="px-2.5 py-1 bg-white hover:bg-indigo-50 text-neutral-700 hover:text-indigo-700 border border-neutral-200 hover:border-indigo-300 rounded-lg text-[11px] font-medium transition shadow-xs"
                          >
                            + {preset.name.replace(' Circulars & Notices', '').replace(' Circulars', '')}
                          </button>
                        ))}
                      </div>
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

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
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
                        <span className="text-neutral-400 shrink-0 text-[10px]">{s.department || s.category}</span>
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
                className="flex items-center gap-1.5 px-5 py-2 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 text-white rounded-xl text-xs font-semibold shadow-sm transition active:scale-95"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Confirm & Sync All</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
