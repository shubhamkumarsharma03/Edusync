import React, { useState, useEffect, useRef } from 'react'
import {
  History,
  Archive,
  Pin,
  Plus,
  Send,
  Menu,
  X,
  ExternalLink,
  Database,
  MessageSquare,
  SquarePen,
  PanelLeft,
  Trash2,
  Edit2,
  RotateCcw,
  RotateCw,
  Search,
  User,
  LogIn,
  UserPlus,
  LogOut,
  GraduationCap,
  Building2,
  Hash,
  Mail,
  KeyRound,
  AlertCircle,
  Loader2,
  Lock,
  Calendar,
  CreditCard,
  BookOpen,
  ArrowUpRight,
  Sparkles,
} from 'lucide-react'
import { checkBackendHealth } from './api/client'
import {
  sendChatMessage,
  sendChatFeedback,
  createChatSession,
  togglePinChatSession,
  toggleArchiveChatSession,
} from './api/chat'
import {
  StudentProfile,
  registerStudent,
  loginStudent,
  fetchCurrentStudent,
  getAuthToken,
  clearAuthToken,
} from './api/auth'
import { AdminDashboard } from './components/AdminDashboard'
import { MessageBubble, BubbleMessage } from './components/MessageBubble'
import { DepartmentSelector } from './components/DepartmentSelector'
import {
  Conversation,
  getActiveStudentId,
  setActiveStudentId,
  loadLocalConversations,
  saveLocalConversations,
  syncConversationsWithServer,
  loadSessionMessagesFromServer,
  backgroundUpdateServerSession,
  backgroundDeleteServerSession,
} from './utils/chatStorage'

const DEPARTMENTS_LIST = [
  'Computer Science & Engineering',
  'Information Technology',
  'Electronics & Communication Engineering',
  'Electrical Engineering',
  'Mechanical Engineering',
  'Civil Engineering',
  'Master of Computer Applications',
  'Master of Business Administration',
]

export const isMastersBranch = (branch: string): boolean => {
  const lower = branch.toLowerCase()
  return lower.includes('master') || lower.includes('mca') || lower.includes('mba')
}

export const getMaxSemesters = (branch: string): number => {
  return isMastersBranch(branch) ? 4 : 8
}

export const STARTER_QUESTIONS = [
  {
    title: 'Mid-term exam schedule for CSE',
    category: 'Examination Cell',
    icon: Calendar,
  },
  {
    title: 'Semester fee notice and due dates',
    category: 'Accounts & Registrar',
    icon: CreditCard,
  },
  {
    title: 'Mercy exam rules for B.Tech',
    category: 'Academics & Back Exam',
    icon: GraduationCap,
  },
  {
    title: 'Central Library book issue timings',
    category: 'Library & Facilities',
    icon: BookOpen,
  },
]

export const App: React.FC = () => {
  const [isAdminView, setIsAdminView] = useState(() => {
    if (typeof window === 'undefined') return false
    return (
      window.location.pathname.startsWith('/admin') ||
      window.location.hash === '#admin' ||
      window.location.search.includes('view=admin')
    )
  })

  // Student Account & Multi-User Partitioning
  const [studentId, setStudentIdState] = useState<string>(() => getActiveStudentId())
  const [currentStudent, setCurrentStudent] = useState<StudentProfile | null>(null)
  const [showAccountModal, setShowAccountModal] = useState<boolean>(false)

  // Derived: Is currently in Guest Mode (not signed into a student account)
  const isGuest = !currentStudent

  // Auth modal states
  const [authTab, setAuthTab] = useState<'login' | 'register'>('login')
  const [authLoading, setAuthLoading] = useState<boolean>(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  // Login form state
  const [loginIdentifier, setLoginIdentifier] = useState('')
  const [loginPassword, setLoginPassword] = useState('')

  // Register form state
  const [regFullName, setRegFullName] = useState('')
  const [regRollNo, setRegRollNo] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regBranch, setRegBranch] = useState('Computer Science & Engineering')
  const [regSemester, setRegSemester] = useState(6)
  const [regPassword, setRegPassword] = useState('')

  // Conversations State (strictly from DB / localStorage; NO dummy data)
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    return loadLocalConversations(studentId)
  })

  const [activeChatId, setActiveChatId] = useState<string>(() => {
    return conversations[0]?.id || ''
  })

  // Sidebar Views: 'recent' shows pinned + recents; 'archived' shows archived conversations
  const [sidebarTab, setSidebarTab] = useState<'recent' | 'archived'>('recent')
  const [searchFilter, setSearchFilter] = useState<string>('')

  // Chat UI states
  const [input, setInput] = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all')
  const [lastUserQuery, setLastUserQuery] = useState<string>('')
  const [sidebarOpen, setSidebarOpen] = useState(false) // Mobile overlay
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false) // Desktop collapse
  const [isTyping, setIsTyping] = useState(false)

  // In-line Renaming State
  const [editingTitleId, setEditingTitleId] = useState<string | null>(null)
  const [editingTitleValue, setEditingTitleValue] = useState<string>('')

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Handle URL change for Admin View
  useEffect(() => {
    const handlePopState = () => {
      setIsAdminView(
        window.location.pathname.startsWith('/admin') ||
        window.location.hash === '#admin' ||
        window.location.search.includes('view=admin')
      )
    }
    window.addEventListener('popstate', handlePopState)
    window.addEventListener('hashchange', handlePopState)
    return () => {
      window.removeEventListener('popstate', handlePopState)
      window.removeEventListener('hashchange', handlePopState)
    }
  }, [])

  // Keyboard shortcut (Ctrl+K / Cmd+K) for New Chat
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        handleNewChat()
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [studentId, conversations, isGuest])

  // Hydrate authenticated student and sync conversations from PostgreSQL
  useEffect(() => {
    checkBackendHealth().catch(() => {})

    const token = getAuthToken()
    if (token) {
      fetchCurrentStudent()
        .then(async (student) => {
          if (student) {
            setCurrentStudent(student)
            setStudentIdState(student.college_roll_no)
            setActiveStudentId(student.college_roll_no)

            const synced = await syncConversationsWithServer([], student.college_roll_no)
            setConversations(synced)
            if (synced.length > 0) {
              setActiveChatId(synced[0].id)
            }
          }
        })
        .catch(() => {
          clearAuthToken()
        })
    } else {
      // In guest mode, do not sync with server - start clean transient guest state
      setConversations([])
      setActiveChatId('')
    }
  }, [])

  // Active Conversation Helper
  const currentConversation =
    conversations.find((c) => c.id === activeChatId) ||
    conversations.find((c) => !c.is_archived) ||
    null

  const messages = currentConversation?.messages || []

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isTyping])

  // Auto-grow textarea height dynamically
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }

  // ----------------- Conversation Handlers -----------------

  const handleNewChat = () => {
    if (isGuest) {
      setConversations([])
      setActiveChatId('')
      setInput('')
      setSidebarOpen(false)
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
      return
    }

    if (currentConversation && currentConversation.messages.length === 0) {
      setSidebarOpen(false)
      setInput('')
      return
    }
    setActiveChatId('')
    setSidebarOpen(false)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleSelectChat = async (id: string) => {
    if (isGuest) {
      setAuthTab('login')
      setShowAccountModal(true)
      return
    }

    setActiveChatId(id)
    setSidebarOpen(false)

    // Lazy load messages from DB if not loaded yet
    const target = conversations.find((c) => c.id === id)
    if (target && target.messages.length === 0) {
      const dbMessages = await loadSessionMessagesFromServer(id)
      if (dbMessages && dbMessages.length > 0) {
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, messages: dbMessages } : c))
        )
      }
    }
  }

  const handleTogglePin = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    if (isGuest) {
      setAuthTab('login')
      setAuthError(null)
      setShowAccountModal(true)
      return
    }

    const target = conversations.find((c) => c.id === id)
    if (!target) return

    const updated = conversations.map((c) =>
      c.id === id ? { ...c, is_pinned: !c.is_pinned, updated_at: new Date().toISOString() } : c
    )
    setConversations(updated)
    saveLocalConversations(updated, studentId)
    togglePinChatSession(id).catch(() => {})
  }

  const handleToggleArchive = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    if (isGuest) {
      setAuthTab('login')
      setAuthError(null)
      setShowAccountModal(true)
      return
    }

    const target = conversations.find((c) => c.id === id)
    if (!target) return

    const newArchivedState = !target.is_archived
    const updated = conversations.map((c) =>
      c.id === id
        ? {
            ...c,
            is_archived: newArchivedState,
            is_pinned: newArchivedState ? false : c.is_pinned,
            updated_at: new Date().toISOString(),
          }
        : c
    )
    setConversations(updated)
    saveLocalConversations(updated, studentId)
    toggleArchiveChatSession(id).catch(() => {})

    // If archiving current active chat, switch to first unarchived chat
    if (id === activeChatId && newArchivedState) {
      const nextActive = updated.find((c) => !c.is_archived)
      setActiveChatId(nextActive?.id || '')
    }
  }

  const handleDeleteChat = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    if (isGuest) {
      setConversations([])
      setActiveChatId('')
      return
    }

    const updated = conversations.filter((c) => c.id !== id)
    setConversations(updated)
    saveLocalConversations(updated, studentId)
    backgroundDeleteServerSession(id)

    if (id === activeChatId) {
      const nextActive = updated.find((c) => !c.is_archived)
      setActiveChatId(nextActive?.id || '')
    }
  }

  const handleResetActiveChat = () => {
    if (!currentConversation) return
    const updated = conversations.map((c) =>
      c.id === currentConversation.id
        ? {
            ...c,
            title: 'New Chat',
            messages: [],
            updated_at: new Date().toISOString(),
          }
        : c
    )
    setConversations(updated)
    if (!isGuest) {
      saveLocalConversations(updated, studentId)
      const target = updated.find((c) => c.id === currentConversation.id)
      if (target) backgroundUpdateServerSession(target)
    }
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleStartRename = (id: string, currentTitle: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    if (isGuest) return
    setEditingTitleId(id)
    setEditingTitleValue(currentTitle)
  }

  const handleSaveRename = (id: string, e?: React.FormEvent) => {
    e?.preventDefault()
    e?.stopPropagation()
    if (isGuest) return
    if (!editingTitleValue.trim()) {
      setEditingTitleId(null)
      return
    }

    const updated = conversations.map((c) =>
      c.id === id
        ? { ...c, title: editingTitleValue.trim(), updated_at: new Date().toISOString() }
        : c
    )
    setConversations(updated)
    saveLocalConversations(updated, studentId)
    setEditingTitleId(null)

    const target = updated.find((c) => c.id === id)
    if (target) backgroundUpdateServerSession(target)
  }

  // ----------------- Authentication Handlers -----------------

  const handleBranchChange = (newBranch: string) => {
    setRegBranch(newBranch)
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.regBranch
      delete next.regSemester
      return next
    })
    const maxSems = getMaxSemesters(newBranch)
    if (regSemester > maxSems) {
      setRegSemester(1)
    }
  }

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errors: Record<string, string> = {}
    const trimmedId = loginIdentifier.trim()
    const trimmedPw = loginPassword

    if (!trimmedId) {
      errors.loginIdentifier = 'College roll number or email is required.'
    } else if (trimmedId.length < 3) {
      errors.loginIdentifier = 'Identifier must be at least 3 characters.'
    }

    if (!trimmedPw) {
      errors.loginPassword = 'Password is required.'
    } else if (trimmedPw.length < 6) {
      errors.loginPassword = 'Password must be at least 6 characters.'
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      setAuthError('Please correct the validation errors below.')
      return
    }

    setFieldErrors({})
    setAuthLoading(true)
    setAuthError(null)

    try {
      const res = await loginStudent({
        identifier: trimmedId,
        password: trimmedPw,
      })
      setCurrentStudent(res.student)
      setStudentIdState(res.student.college_roll_no)
      setActiveStudentId(res.student.college_roll_no)

      const serverConvs = await syncConversationsWithServer([], res.student.college_roll_no)
      setConversations(serverConvs)
      setActiveChatId(serverConvs[0]?.id || '')

      setShowAccountModal(false)
      setLoginPassword('')
    } catch (err: any) {
      setAuthError(err.message || 'Login failed. Please check your credentials.')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errors: Record<string, string> = {}
    const trimmedName = regFullName.trim()
    const trimmedRoll = regRollNo.trim().toUpperCase()
    const trimmedEmail = regEmail.trim().toLowerCase()
    const maxSem = getMaxSemesters(regBranch)

    // Name validation: 2-100 characters, letters and spaces only
    if (!trimmedName) {
      errors.regFullName = 'Full name is required.'
    } else if (!/^[A-Za-z\s.'-]{2,100}$/.test(trimmedName)) {
      errors.regFullName = 'Full name must be 2-100 characters (letters and spaces only).'
    }

    // Roll number validation: 4-25 characters alphanumeric and hyphens
    if (!trimmedRoll) {
      errors.regRollNo = 'College roll number is required.'
    } else if (!/^[A-Z0-9-]{4,25}$/.test(trimmedRoll)) {
      errors.regRollNo = 'Roll number must be 4-25 alphanumeric characters (e.g. 22ECA108).'
    }

    // Email validation
    if (!trimmedEmail) {
      errors.regEmail = 'Email address is required.'
    } else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmedEmail)) {
      errors.regEmail = 'Please enter a valid institutional email address.'
    }

    // Department validation
    if (!regBranch || !DEPARTMENTS_LIST.includes(regBranch)) {
      errors.regBranch = 'Please select a valid department.'
    }

    // Semester validation (4 for Masters, 8 for B.Tech)
    if (!regSemester || regSemester < 1 || regSemester > maxSem) {
      errors.regSemester = `Semester must be between 1 and ${maxSem} for ${isMastersBranch(regBranch) ? 'Masters (MCA/MBA)' : 'B.Tech'}.`
    }

    // Password validation
    if (!regPassword) {
      errors.regPassword = 'Password is required.'
    } else if (regPassword.length < 6) {
      errors.regPassword = 'Password must be at least 6 characters.'
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      setAuthError('Please correct the validation errors below.')
      return
    }

    setFieldErrors({})
    setAuthLoading(true)
    setAuthError(null)

    try {
      const res = await registerStudent({
        full_name: trimmedName,
        college_roll_no: trimmedRoll,
        email: trimmedEmail,
        branch: regBranch,
        semester: Number(regSemester),
        password: regPassword,
      })
      setCurrentStudent(res.student)
      setStudentIdState(res.student.college_roll_no)
      setActiveStudentId(res.student.college_roll_no)

      // Brand new registered user has zero dummy chats
      setConversations([])
      setActiveChatId('')

      setShowAccountModal(false)
      setRegPassword('')
    } catch (err: any) {
      setAuthError(err.message || 'Registration failed.')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = () => {
    clearAuthToken()
    setCurrentStudent(null)
    setStudentIdState('student_guest')
    setActiveStudentId('student_guest')
    setConversations([])
    setActiveChatId('')
    setShowAccountModal(false)
  }

  // ----------------- Sending Messages with History Memory -----------------

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim()
    if (!query || isTyping) return

    setLastUserQuery(query)

    const cleanSnippet = query.split('\n')[0].trim()
    const autoTitle = cleanSnippet.length > 36 ? `${cleanSnippet.slice(0, 36)}...` : cleanSnippet

    // Resolve or instantiate session
    let convId = activeChatId
    let isNewSession = false

    let targetConv = conversations.find((c) => c.id === convId)
    if (!targetConv) {
      isNewSession = true
      convId =
        typeof crypto !== 'undefined' && crypto.randomUUID
          ? crypto.randomUUID()
          : `chat_${Date.now()}`

      targetConv = {
        id: convId,
        student_id: studentId,
        title: autoTitle,
        is_pinned: false,
        is_archived: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [],
      }
    }

    const userMsg: BubbleMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    const newTitle =
      targetConv.title === 'New Chat' || targetConv.title === 'Untitled Chat' || isNewSession
        ? autoTitle
        : targetConv.title

    const updatedMessages = [...targetConv.messages, userMsg]
    const updatedConv: Conversation = {
      ...targetConv,
      title: newTitle,
      messages: updatedMessages,
      updated_at: new Date().toISOString(),
    }

    const updatedConvs = isNewSession
      ? [updatedConv, ...conversations]
      : conversations.map((c) => (c.id === convId ? updatedConv : c))

    setConversations(updatedConvs)
    setActiveChatId(convId)

    if (!isGuest) {
      saveLocalConversations(updatedConvs, studentId)
      if (isNewSession) {
        createChatSession(studentId, updatedConv.title, updatedConv.messages).catch(() => {})
      } else {
        backgroundUpdateServerSession(updatedConv)
      }
    }

    if (!textToSend) {
      setInput('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }

    setIsTyping(true)
    try {
      // Past Conversation History Memory (last 4 turns)
      const historyPayload = targetConv.messages
        .filter((m) => m.id !== 'welcome-1')
        .slice(-4)
        .map((m) => ({
          role: m.sender as 'user' | 'assistant',
          content: m.text,
        }))

      const res = await sendChatMessage(
        query,
        selectedDepartment === 'all' ? null : selectedDepartment,
        historyPayload,
        isGuest ? null : convId
      )

      const botMsg: BubbleMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: res.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        confidence: res.confidence,
        confidenceScore: res.confidence_score,
        isFallback: res.is_fallback,
        queryId: res.query_id,
        suggestions: res.suggestions || [],
        sources: res.sources.map((s) => ({
          title: s.title,
          url: s.url,
          department: s.department,
          lastVerified: s.last_verified,
          confidenceScore: s.confidence_score,
        })),
      }

      const finalMessages = [...updatedMessages, botMsg]
      const finalConv: Conversation = {
        ...updatedConv,
        messages: finalMessages,
        updated_at: new Date().toISOString(),
      }

      const finalConvs = updatedConvs.map((c) => (c.id === convId ? finalConv : c))
      setConversations(finalConvs)
      if (!isGuest) {
        saveLocalConversations(finalConvs, studentId)
        backgroundUpdateServerSession(finalConv)
      }
    } catch (err: any) {
      const errorMsg: BubbleMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text:
          err.message ||
          'Sorry, could not connect to the backend server. Please verify the API is running.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
      }
      const withErrorMessages = [...updatedMessages, errorMsg]
      const withErrorConvs = updatedConvs.map((c) =>
        c.id === convId ? { ...c, messages: withErrorMessages } : c
      )
      setConversations(withErrorConvs)
      if (!isGuest) {
        saveLocalConversations(withErrorConvs, studentId)
      }
    } finally {
      setIsTyping(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFeedback = async (
    messageId: string,
    queryId: string | undefined,
    type: 'up' | 'down'
  ) => {
    if (!currentConversation) return

    const updatedMessages = messages.map((msg) =>
      msg.id === messageId ? { ...msg, feedback: msg.feedback === type ? null : type } : msg
    )
    const updatedConvs = conversations.map((c) =>
      c.id === currentConversation.id ? { ...c, messages: updatedMessages } : c
    )
    setConversations(updatedConvs)
    if (!isGuest) {
      saveLocalConversations(updatedConvs, studentId)
    }

    if (queryId) {
      try {
        await sendChatFeedback(queryId, type)
      } catch (err) {
        console.warn('Failed to record student feedback to server:', err)
      }
    }
  }

  // Filtered lists for sidebar
  const activeConversations = conversations.filter((c) => !c.is_archived)
  const pinnedConversations = activeConversations.filter((c) => c.is_pinned)
  const recentConversations = activeConversations.filter((c) => !c.is_pinned)
  const archivedConversations = conversations.filter((c) => c.is_archived)

  const filterMatches = (title: string) => {
    if (!searchFilter.trim()) return true
    return title.toLowerCase().includes(searchFilter.toLowerCase().trim())
  }

  // Check if current conversation has real user dialogue
  const hasUserMessages = messages.some((m) => m.sender === 'user')

  // If URL path is /admin or #admin, render full-page Admin Dashboard
  if (isAdminView) {
    return <AdminDashboard />
  }

  return (
    <div className="flex h-[100dvh] w-full bg-[#fcfcfc] text-[#18181b] overflow-hidden font-['Inter',sans-serif]">
      {/* Mobile Backdrop Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/25 backdrop-blur-xs z-40 lg:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Responsive Left Sidebar (ChatGPT-styled in EduSync palette) */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 sm:w-64 bg-[#f8f9fa] border-r border-[#ebecee] flex flex-col justify-between transition-all duration-200 ease-in-out lg:static ${
          sidebarOpen ? 'translate-x-0 shadow-2xl lg:shadow-none' : '-translate-x-full lg:translate-x-0'
        } ${sidebarCollapsed ? 'lg:w-0 lg:border-none lg:overflow-hidden' : ''}`}
      >
        <div className="flex flex-col h-full min-h-0">
          {/* Top Brand & New Chat */}
          <div className="p-3.5 sm:p-4 space-y-3 shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <img src="/logo-icon.png" alt="EduSync" className="w-6 h-6 object-contain" />
                <span className="font-bold text-sm tracking-tight text-[#18181b]">EduSync</span>
              </div>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => setSidebarCollapsed(true)}
                  className="hidden lg:flex p-1.5 text-neutral-400 hover:text-neutral-700 hover:bg-neutral-200/50 rounded-lg transition cursor-pointer"
                  title="Collapse sidebar"
                >
                  <PanelLeft className="w-4 h-4" />
                </button>
                <button
                  className="lg:hidden p-1.5 text-neutral-400 hover:text-neutral-700 rounded-lg cursor-pointer"
                  onClick={() => setSidebarOpen(false)}
                  aria-label="Close sidebar"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* New Chat Button (ChatGPT-style) */}
            <button
              onClick={handleNewChat}
              className="w-full flex items-center justify-between px-3 py-2 bg-white hover:bg-neutral-100 text-[#18181b] rounded-xl border border-[#e4e4e7] shadow-2xs text-xs font-semibold transition cursor-pointer group"
            >
              <div className="flex items-center gap-2">
                <SquarePen className="w-3.5 h-3.5 text-neutral-600 group-hover:text-black" />
                <span>New chat</span>
              </div>
              <span className="text-[10px] text-neutral-400 font-normal">⌘+K</span>
            </button>

            {/* Quick Search in Conversations (Grayed out in Guest Mode) */}
            <div className="relative group">
              <Search className="w-3.5 h-3.5 text-neutral-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                disabled={isGuest}
                placeholder={isGuest ? 'Search (Sign in to enable)...' : 'Search chats...'}
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className={`w-full pl-7 pr-2.5 py-1.5 rounded-lg text-xs transition ${
                  isGuest
                    ? 'bg-[#f0f1f3]/70 text-neutral-400 border border-transparent cursor-not-allowed opacity-60'
                    : 'bg-[#f4f4f5] border border-transparent text-neutral-800 placeholder-neutral-400 focus:outline-none focus:bg-white focus:border-[#e4e4e7]'
                }`}
              />
              {isGuest && (
                <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 hidden group-hover:flex flex-col z-50 w-64 p-2.5 bg-[#18181b] text-white text-[11px] rounded-xl shadow-xl border border-neutral-800 pointer-events-none transition-all animate-in fade-in">
                  <div className="flex items-center gap-1.5 font-semibold text-neutral-200 mb-0.5">
                    <Lock className="w-3 h-3 text-amber-400 shrink-0" />
                    <span>Guest Mode</span>
                  </div>
                  <p className="text-neutral-300 text-[10px] leading-snug">
                    Searching across past conversation history requires signing in to a student account.
                  </p>
                </div>
              )}
            </div>

            {/* Navigation Tabs (Recent Chats vs Archived) */}
            <div className="relative group">
              <div
                className={`flex items-center p-0.5 rounded-lg text-xs font-semibold ${
                  isGuest ? 'bg-[#ebecee]/60 opacity-60' : 'bg-[#eaecee] text-neutral-600'
                }`}
              >
                <button
                  onClick={() => {
                    if (isGuest) {
                      setAuthTab('login')
                      setShowAccountModal(true)
                    } else {
                      setSidebarTab('recent')
                    }
                  }}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-1 rounded-md transition ${
                    isGuest
                      ? 'text-neutral-400 hover:text-neutral-600 cursor-pointer'
                      : sidebarTab === 'recent'
                      ? 'bg-white text-[#18181b] shadow-2xs cursor-pointer'
                      : 'hover:text-neutral-900 cursor-pointer'
                  }`}
                >
                  <History className="w-3 h-3" />
                  <span>Recents</span>
                  {isGuest && <Lock className="w-2.5 h-2.5 text-neutral-400 ml-0.5" />}
                </button>
                <button
                  onClick={() => {
                    if (isGuest) {
                      setAuthTab('login')
                      setShowAccountModal(true)
                    } else {
                      setSidebarTab('archived')
                    }
                  }}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-1 rounded-md transition ${
                    isGuest
                      ? 'text-neutral-400 hover:text-neutral-600 cursor-pointer'
                      : sidebarTab === 'archived'
                      ? 'bg-white text-[#18181b] shadow-2xs cursor-pointer'
                      : 'hover:text-neutral-900 cursor-pointer'
                  }`}
                >
                  <Archive className="w-3 h-3" />
                  <span>Archived</span>
                  {isGuest && <Lock className="w-2.5 h-2.5 text-neutral-400 ml-0.5" />}
                </button>
              </div>

              {isGuest && (
                <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 hidden group-hover:flex flex-col z-50 w-64 p-2.5 bg-[#18181b] text-white text-[11px] rounded-xl shadow-xl border border-neutral-800 pointer-events-none transition-all animate-in fade-in">
                  <div className="flex items-center gap-1.5 font-semibold text-neutral-200 mb-0.5">
                    <Lock className="w-3 h-3 text-amber-400 shrink-0" />
                    <span>History & Archive Disabled</span>
                  </div>
                  <p className="text-neutral-300 text-[10px] leading-snug">
                    Chat history and archives are only saved for signed-in students. Click to sign in.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Scrollable Conversation List */}
          <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-4 min-h-0 select-none">
            {isGuest ? (
              /* GUEST MODE: Clean state with hover description */
              <div
                onClick={() => {
                  setAuthTab('login')
                  setAuthError(null)
                  setShowAccountModal(true)
                }}
                className="relative group flex flex-col items-center justify-center p-6 text-center select-none cursor-pointer rounded-2xl hover:bg-neutral-100/60 transition mt-6 space-y-2 border border-dashed border-neutral-200/80"
              >
                <div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-400 group-hover:text-neutral-700 transition">
                  <Lock className="w-3.5 h-3.5" />
                </div>
                <span className="text-xs font-medium text-neutral-500">History disabled in guest mode</span>
                <span className="text-[11px] text-neutral-400">Click to sign in & save chats</span>

                {/* Little description tooltip on hover */}
                <div className="absolute left-1/2 -translate-x-1/2 bottom-2 hidden group-hover:flex flex-col z-50 w-56 p-2.5 bg-[#18181b] text-white text-[11px] rounded-xl shadow-xl border border-neutral-800 pointer-events-none transition-all animate-in fade-in text-left">
                  <div className="flex items-center gap-1.5 font-semibold text-neutral-200 mb-0.5">
                    <Lock className="w-3 h-3 text-amber-400 shrink-0" />
                    <span>Student Account Required</span>
                  </div>
                  <p className="text-neutral-300 text-[10px] leading-snug">
                    Chat history, pinned circulars, and archives are preserved only when signed in to your student account.
                  </p>
                </div>
              </div>
            ) : sidebarTab === 'recent' ? (
              <>
                {/* 1. PINNED SECTION */}
                {pinnedConversations.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider px-2 py-1 flex items-center gap-1">
                      <Pin className="w-3 h-3 text-amber-500 fill-amber-400" />
                      <span>Pinned</span>
                    </div>

                    {pinnedConversations.filter((c) => filterMatches(c.title)).map((conv) => {
                      const isActive = conv.id === activeChatId
                      return (
                        <div
                          key={conv.id}
                          onClick={() => handleSelectChat(conv.id)}
                          className={`group relative flex items-center justify-between px-2.5 py-2 rounded-xl text-xs transition cursor-pointer ${
                            isActive
                              ? 'bg-[#ebecee] text-[#18181b] font-semibold'
                              : 'text-neutral-600 hover:bg-neutral-200/50 hover:text-neutral-900'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0 pr-1">
                            <Pin className="w-3.5 h-3.5 text-amber-500 fill-amber-400 shrink-0" />
                            {editingTitleId === conv.id ? (
                              <form onSubmit={(e) => handleSaveRename(conv.id, e)} className="flex-1">
                                <input
                                  autoFocus
                                  type="text"
                                  value={editingTitleValue}
                                  onChange={(e) => setEditingTitleValue(e.target.value)}
                                  onBlur={(e) => handleSaveRename(conv.id, e)}
                                  className="w-full px-1.5 py-0.5 bg-white border border-[#e4e4e7] rounded text-xs text-neutral-900 focus:outline-none"
                                />
                              </form>
                            ) : (
                              <span className="truncate">{conv.title}</span>
                            )}
                          </div>

                          {/* Hover Action Buttons */}
                          <div
                            className={`flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition ${
                              isActive ? 'opacity-100' : ''
                            }`}
                          >
                            <button
                              onClick={(e) => handleTogglePin(conv.id, e)}
                              className="p-1 text-neutral-400 hover:text-neutral-800 rounded transition cursor-pointer"
                              title="Unpin chat"
                            >
                              <Pin className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleStartRename(conv.id, conv.title, e)}
                              className="p-1 text-neutral-400 hover:text-neutral-800 rounded transition cursor-pointer"
                              title="Rename chat"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleToggleArchive(conv.id, e)}
                              className="p-1 text-neutral-400 hover:text-neutral-800 rounded transition cursor-pointer"
                              title="Archive chat"
                            >
                              <Archive className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleDeleteChat(conv.id, e)}
                              className="p-1 text-neutral-400 hover:text-rose-600 rounded transition cursor-pointer"
                              title="Delete chat"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}

                {/* 2. RECENT CHATS SECTION */}
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider px-2 py-1">
                    Recent Chats
                  </div>

                  {recentConversations.filter((c) => filterMatches(c.title)).length === 0 ? (
                    <div className="text-center py-6 text-xs text-neutral-400">
                      No recent chats found.
                    </div>
                  ) : (
                    recentConversations.filter((c) => filterMatches(c.title)).map((conv) => {
                      const isActive = conv.id === activeChatId
                      return (
                        <div
                          key={conv.id}
                          onClick={() => handleSelectChat(conv.id)}
                          className={`group relative flex items-center justify-between px-2.5 py-2 rounded-xl text-xs transition cursor-pointer ${
                            isActive
                              ? 'bg-[#ebecee] text-[#18181b] font-semibold'
                              : 'text-neutral-600 hover:bg-neutral-200/50 hover:text-neutral-900'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0 pr-1">
                            <MessageSquare className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                            {editingTitleId === conv.id ? (
                              <form onSubmit={(e) => handleSaveRename(conv.id, e)} className="flex-1">
                                <input
                                  autoFocus
                                  type="text"
                                  value={editingTitleValue}
                                  onChange={(e) => setEditingTitleValue(e.target.value)}
                                  onBlur={(e) => handleSaveRename(conv.id, e)}
                                  className="w-full px-1.5 py-0.5 bg-white border border-[#e4e4e7] rounded text-xs text-neutral-900 focus:outline-none"
                                />
                              </form>
                            ) : (
                              <span className="truncate">{conv.title}</span>
                            )}
                          </div>

                          {/* Hover Action Buttons */}
                          <div
                            className={`flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition ${
                              isActive ? 'opacity-100' : ''
                            }`}
                          >
                            <button
                              onClick={(e) => handleTogglePin(conv.id, e)}
                              className="p-1 text-neutral-400 hover:text-neutral-800 rounded transition cursor-pointer"
                              title="Pin chat to top"
                            >
                              <Pin className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleStartRename(conv.id, conv.title, e)}
                              className="p-1 text-neutral-400 hover:text-neutral-800 rounded transition cursor-pointer"
                              title="Rename chat"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleToggleArchive(conv.id, e)}
                              className="p-1 text-neutral-400 hover:text-neutral-800 rounded transition cursor-pointer"
                              title="Archive chat"
                            >
                              <Archive className="w-3 h-3" />
                            </button>
                            <button
                              onClick={(e) => handleDeleteChat(conv.id, e)}
                              className="p-1 text-neutral-400 hover:text-rose-600 rounded transition cursor-pointer"
                              title="Delete chat"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </>
            ) : (
              /* 3. ARCHIVED SECTION */
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider px-2 py-1 flex items-center justify-between">
                  <span>Archived Chats</span>
                  <span>{archivedConversations.length}</span>
                </div>

                {archivedConversations.length === 0 ? (
                  <div className="text-center py-8 text-xs text-neutral-400 space-y-1">
                    <Archive className="w-5 h-5 mx-auto text-neutral-300 mb-1" />
                    <div>No archived conversations.</div>
                  </div>
                ) : (
                  archivedConversations.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => handleSelectChat(conv.id)}
                      className="group flex items-center justify-between px-2.5 py-2 rounded-xl text-xs bg-white border border-[#e4e4e7] hover:bg-neutral-50 transition cursor-pointer shadow-2xs"
                    >
                      <span className="truncate text-neutral-700 font-medium">{conv.title}</span>
                      <div className="flex items-center gap-1 shrink-0 ml-1">
                        <button
                          onClick={(e) => handleToggleArchive(conv.id, e)}
                          className="p-1 text-neutral-500 hover:text-neutral-900 rounded hover:bg-neutral-100 transition cursor-pointer"
                          title="Restore to recent chats"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={(e) => handleDeleteChat(conv.id, e)}
                          className="p-1 text-neutral-400 hover:text-rose-600 rounded hover:bg-rose-50 transition cursor-pointer"
                          title="Delete permanently"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Sidebar Footer: Student Profile Card */}
          <div className="p-3 border-t border-[#ebecee] bg-[#f8f9fa] shrink-0">
            <div
              onClick={() => {
                setAuthError(null)
                setShowAccountModal(true)
              }}
              className="flex items-center justify-between p-2 rounded-xl bg-white border border-[#e4e4e7] hover:bg-neutral-50 transition cursor-pointer shadow-2xs group"
              title={
                isGuest
                  ? 'Using as guest. Click to sign in or create student account.'
                  : 'Click to view profile or sign out'
              }
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-full bg-neutral-900 text-white font-bold text-xs flex items-center justify-center shrink-0">
                  {currentStudent
                    ? currentStudent.full_name
                        .split(' ')
                        .map((n) => n[0])
                        .join('')
                        .slice(0, 2)
                        .toUpperCase()
                    : 'ST'}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-[#18181b] truncate group-hover:text-black">
                    {currentStudent ? currentStudent.full_name : 'Student Guest'}
                  </div>
                  <div className="text-[10px] text-neutral-400 truncate">
                    {currentStudent
                      ? `${currentStudent.college_roll_no} • Sem ${currentStudent.semester}`
                      : 'Sign in'}
                  </div>
                </div>
              </div>
              <User className="w-3.5 h-3.5 text-neutral-400 group-hover:text-neutral-700 shrink-0" />
            </div>
          </div>
        </div>
      </aside>

      {/* Main Chat Interface */}
      <div className="flex-1 flex flex-col h-full bg-[#fcfcfc] relative min-w-0 overflow-hidden">
        {/* Top Navigation Bar */}
        <header className="h-14 border-b border-[#f0f0f2] flex items-center justify-between px-3 sm:px-6 bg-[#fcfcfc] sticky top-0 z-30 shrink-0">
          {/* Left: Sidebar Toggle */}
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 text-neutral-700 hover:text-neutral-950 rounded-lg hover:bg-neutral-100 transition-colors cursor-pointer"
              aria-label="Open sidebar"
            >
              <Menu className="w-4 h-4" />
            </button>

            {sidebarCollapsed && (
              <button
                onClick={() => setSidebarCollapsed(false)}
                className="hidden lg:flex p-2 text-neutral-700 hover:text-neutral-950 rounded-lg hover:bg-neutral-100 transition-colors cursor-pointer"
                title="Open sidebar"
              >
                <PanelLeft className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            {/* Reset Active Chat Button */}
            {currentConversation && hasUserMessages && (
              <button
                onClick={handleResetActiveChat}
                className="p-2 text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100 rounded-xl transition cursor-pointer"
                title="Reset active chat"
              >
                <RotateCw className="w-4 h-4" />
              </button>
            )}

            {/* Pin Chat Action (Active when signed in, grayed out with tooltip in Guest Mode) */}
            {isGuest ? (
              <div className="relative group">
                <button
                  type="button"
                  onClick={() => {
                    setAuthTab('login')
                    setAuthError(null)
                    setShowAccountModal(true)
                  }}
                  className="p-2 text-neutral-300 hover:text-neutral-500 rounded-xl transition cursor-pointer opacity-50 hover:opacity-90"
                  aria-label="Pin circular (sign in required)"
                >
                  <Pin className="w-4 h-4 text-neutral-300" />
                </button>
                <div className="absolute right-0 top-full mt-2 hidden group-hover:flex flex-col z-50 w-60 p-2.5 bg-[#18181b] text-white text-[11px] rounded-xl shadow-xl border border-neutral-800 pointer-events-none transition-all animate-in fade-in">
                  <div className="flex items-center gap-1.5 font-semibold text-neutral-200 mb-0.5">
                    <Lock className="w-3 h-3 text-amber-400 shrink-0" />
                    <span>Student Account Required</span>
                  </div>
                  <p className="text-neutral-300 text-[10px] leading-snug">
                    Pinning circulars is unavailable in guest mode. Sign in to pin and keep notices for quick access.
                  </p>
                </div>
              </div>
            ) : currentConversation ? (
              <button
                onClick={(e) => handleTogglePin(currentConversation.id, e)}
                className={`p-2 rounded-xl transition cursor-pointer ${
                  currentConversation.is_pinned
                    ? 'text-amber-600 bg-amber-50 hover:bg-amber-100'
                    : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100'
                }`}
                title={currentConversation.is_pinned ? 'Unpin chat' : 'Pin chat to top'}
              >
                <Pin
                  className={`w-4 h-4 ${
                    currentConversation.is_pinned ? 'fill-amber-400 text-amber-500' : ''
                  }`}
                />
              </button>
            ) : null}

            {/* Archive Chat Action (Active when signed in, grayed out with tooltip in Guest Mode) */}
            {isGuest ? (
              <div className="relative group">
                <button
                  type="button"
                  onClick={() => {
                    setAuthTab('login')
                    setAuthError(null)
                    setShowAccountModal(true)
                  }}
                  className="p-2 text-neutral-300 hover:text-neutral-500 rounded-xl transition cursor-pointer opacity-50 hover:opacity-90"
                  aria-label="Archive chat (sign in required)"
                >
                  <Archive className="w-4 h-4 text-neutral-300" />
                </button>
                <div className="absolute right-0 top-full mt-2 hidden group-hover:flex flex-col z-50 w-60 p-2.5 bg-[#18181b] text-white text-[11px] rounded-xl shadow-xl border border-neutral-800 pointer-events-none transition-all animate-in fade-in">
                  <div className="flex items-center gap-1.5 font-semibold text-neutral-200 mb-0.5">
                    <Lock className="w-3 h-3 text-amber-400 shrink-0" />
                    <span>Student Account Required</span>
                  </div>
                  <p className="text-neutral-300 text-[10px] leading-snug">
                    Archiving conversations is unavailable in guest mode. Sign in to save and organize past chats.
                  </p>
                </div>
              </div>
            ) : currentConversation ? (
              <button
                onClick={(e) => handleToggleArchive(currentConversation.id, e)}
                className={`p-2 rounded-xl transition cursor-pointer ${
                  currentConversation.is_archived
                    ? 'text-indigo-600 bg-indigo-50 hover:bg-indigo-100'
                    : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100'
                }`}
                title={currentConversation.is_archived ? 'Restore from archive' : 'Archive chat'}
              >
                <Archive className="w-4 h-4" />
              </button>
            ) : null}

            {/* Admin Panel Link */}
            <a
              href="/admin"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-neutral-50 text-neutral-700 hover:text-[#18181b] rounded-xl text-xs font-semibold border border-[#e4e4e7] shadow-2xs transition ml-1"
              title="Open Admin Data Sources in a new tab"
            >
              <Database className="w-3.5 h-3.5 text-indigo-600" />
              <span className="hidden sm:inline">Admin</span>
              <ExternalLink className="w-3 h-3 text-neutral-400" />
            </a>
          </div>
        </header>

        {/* Dynamic Chat Canvas: Centered Hero when Empty, Thread when Active */}
        {!hasUserMessages ? (
          <main className="flex-1 flex flex-col justify-start items-center px-4 sm:px-6 pt-10 sm:pt-14 pb-8 w-full max-w-2xl sm:max-w-3xl mx-auto min-h-0 text-center space-y-6 overflow-y-auto animate-in fade-in">
            {/* 1. Centered Hero Branding */}
            <div className="space-y-2">
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-2xl bg-white border border-[#e4e4e7] shadow-2xs mb-1">
                <img src="/logo-icon.png" alt="EduSync" className="w-5 h-5 object-contain" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[#18181b]">
                Ready when you are.
              </h1>
              <p className="text-xs sm:text-sm text-neutral-500 max-w-lg mx-auto">
                Institutional AI assistant for Engineering College Ajmer. Grounded strictly in official circulars.
              </p>
            </div>

            {/* 2. Department Scope Selector & Floating Pill Input Bar */}
            <div className="w-full space-y-2">
              {/* Department Scope Selector above Input (Consistent with active chat) */}
              <DepartmentSelector
                selectedDept={selectedDepartment}
                onSelectDept={setSelectedDepartment}
              />

              {/* Floating Pill Input Bar */}
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSend()
                }}
                className="w-full flex items-end gap-2 bg-white border border-[#e4e4e7] rounded-3xl px-3 py-2 sm:px-4 sm:py-2.5 shadow-xs focus-within:border-neutral-400 focus-within:shadow-md transition-all text-left"
              >
                <button
                  type="button"
                  className="p-1.5 text-neutral-400 hover:text-neutral-700 rounded-lg transition-colors shrink-0 mb-0.5 cursor-pointer"
                  title="Options"
                >
                  <Plus className="w-4 h-4" />
                </button>

                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    selectedDepartment === 'all'
                      ? 'Ask about exams, fee notices, circulars...'
                      : `Ask about circulars scoped to ${selectedDepartment}...`
                  }
                  className="flex-1 bg-transparent text-sm sm:text-[15px] text-[#18181b] placeholder-neutral-400 focus:outline-none px-1 py-1 font-normal resize-none max-h-28 overflow-y-auto leading-relaxed"
                />

                <button
                  type="submit"
                  disabled={!input.trim() || isTyping}
                  className={`p-2 rounded-full flex items-center justify-center transition-all shrink-0 mb-0.5 ${
                    input.trim() && !isTyping
                      ? 'bg-[#18181b] text-white hover:bg-black cursor-pointer shadow-xs'
                      : 'text-neutral-300 cursor-not-allowed'
                  }`}
                  title="Send"
                >
                  <Send className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                </button>
              </form>
            </div>

            {/* 3. Starter Questions (Strictly Kept & Beautifully Rearranged) */}
            <div className="w-full space-y-2 pt-1 text-left">
              <div className="flex items-center gap-1.5 text-[11px] font-medium text-neutral-400 px-1">
                <Sparkles className="w-3 h-3 text-neutral-400" />
                <span>Suggested inquiries from official circulars</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full">
                {STARTER_QUESTIONS.map((item, idx) => {
                  const IconComp = item.icon
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSend(item.title)}
                      className="group flex items-center justify-between p-3.5 bg-white hover:bg-neutral-50/80 border border-[#e4e4e7] hover:border-neutral-300 rounded-2xl text-left transition-all shadow-2xs hover:shadow-xs cursor-pointer"
                    >
                      <div className="flex items-center gap-3 min-w-0 pr-2">
                        <div className="w-8 h-8 rounded-xl bg-neutral-100 group-hover:bg-neutral-200/70 flex items-center justify-center text-neutral-600 shrink-0 transition-colors">
                          <IconComp className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-neutral-800 group-hover:text-black truncate">
                            {item.title}
                          </div>
                          <div className="text-[10px] text-neutral-400 truncate">
                            {item.category}
                          </div>
                        </div>
                      </div>
                      <ArrowUpRight className="w-4 h-4 text-neutral-300 group-hover:text-neutral-700 shrink-0 transition-colors" />
                    </button>
                  )
                })}
              </div>
            </div>

            {/* 4. Verification Footnote */}
            <p className="text-center text-[10px] sm:text-[11px] text-neutral-400 pt-2">
              EduSync answers are strictly verified against official ECA circulars.
            </p>
          </main>
        ) : (
          <>
            {/* Active Chat Message Stream */}
            <main className="flex-1 overflow-y-auto px-3 sm:px-6 md:px-8 py-4 sm:py-6 space-y-4 sm:space-y-6 w-full max-w-3xl lg:max-w-4xl mx-auto min-h-0">
              <div className="text-center pt-1 pb-2">
                <span className="text-xs sm:text-[13px] text-neutral-400 font-normal">
                  {messages[0]?.timestamp || 'Today 9:41 AM'}
                </span>
              </div>

              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onSuggestionClick={(sugg) => handleSend(sugg)}
                  onRetry={(q) => handleSend(q)}
                  onFeedback={handleFeedback}
                  userQueryForRetry={lastUserQuery}
                />
              ))}

              {isTyping && (
                <div className="flex items-start gap-2.5 sm:gap-3.5 max-w-full sm:max-w-2xl md:max-w-3xl pr-4">
                  <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-white border border-[#e4e4e7] flex-shrink-0 flex items-center justify-center p-1 mt-0.5 shadow-2xs">
                    <img
                      src="/logo-icon.png"
                      alt="EduSync AI"
                      className="w-full h-full object-contain animate-pulse"
                    />
                  </div>
                  <div className="bg-[#f4f4f5] rounded-2xl px-4 py-3 text-xs text-neutral-500 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
                    <span>Searching verified circulars & generating grounded answer...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </main>

            {/* Sticky Bottom Input Bar with Department Selector Filter */}
            <div className="p-3 sm:p-5 md:p-6 bg-gradient-to-t from-[#fcfcfc] via-[#fcfcfc] to-transparent sticky bottom-0 z-20 shrink-0">
              <div className="max-w-3xl lg:max-w-4xl mx-auto space-y-2">
                <DepartmentSelector
                  selectedDept={selectedDepartment}
                  onSelectDept={setSelectedDepartment}
                />

                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleSend()
                  }}
                  className="flex items-end gap-2 bg-white border border-[#e4e4e7] rounded-3xl px-3 py-2 sm:px-4 sm:py-2.5 shadow-xs focus-within:border-neutral-400 focus-within:shadow-md transition-all"
                >
                  <button
                    type="button"
                    className="p-1.5 text-neutral-400 hover:text-neutral-700 rounded-lg transition-colors shrink-0 mb-0.5 cursor-pointer"
                    title="Options"
                  >
                    <Plus className="w-4 h-4" />
                  </button>

                  <textarea
                    ref={textareaRef}
                    rows={1}
                    value={input}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      selectedDepartment === 'all'
                        ? 'Ask about exams, fee notices, circulars...'
                        : `Ask about circulars scoped to ${selectedDepartment}...`
                    }
                    className="flex-1 bg-transparent text-sm sm:text-[15px] text-[#18181b] placeholder-neutral-400 focus:outline-none px-1 py-1 font-normal resize-none max-h-28 overflow-y-auto leading-relaxed"
                  />

                  <button
                    type="submit"
                    disabled={!input.trim() || isTyping}
                    className={`p-2 rounded-full flex items-center justify-center transition-all shrink-0 mb-0.5 ${
                      input.trim() && !isTyping
                        ? 'bg-[#18181b] text-white hover:bg-black cursor-pointer shadow-xs'
                        : 'text-neutral-300 cursor-not-allowed'
                    }`}
                    title="Send"
                  >
                    <Send className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  </button>
                </form>

                <p className="text-center text-[10px] sm:text-[11px] text-neutral-400">
                  EduSync answers are strictly verified against official ECA circulars.
                </p>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Student Authentication & Account Profile Modal */}
      {showAccountModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#e4e4e7] max-w-md w-full p-5 space-y-4 shadow-xl animate-in fade-in zoom-in-95">
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-neutral-100">
              <h3 className="font-bold text-sm text-[#18181b] flex items-center gap-2">
                <User className="w-4 h-4 text-neutral-700" />
                <span>{currentStudent ? 'Student Account Profile' : 'Student Authentication'}</span>
              </h3>
              <button
                onClick={() => {
                  setShowAccountModal(false)
                  setFieldErrors({})
                  setAuthError(null)
                }}
                className="p-1 text-neutral-400 hover:text-neutral-800 rounded-lg hover:bg-neutral-100 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Error Banner */}
            {authError && (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 text-xs p-2.5 rounded-xl flex items-center gap-2 animate-in fade-in">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span className="flex-1">{authError}</span>
              </div>
            )}

            {currentStudent ? (
              /* Profile Details View for Logged-In Student */
              <div className="space-y-4 text-xs">
                <div className="flex items-center gap-3 p-3 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl">
                  <div className="w-10 h-10 rounded-full bg-neutral-900 text-white font-bold text-sm flex items-center justify-center shrink-0">
                    {currentStudent.full_name
                      .split(' ')
                      .map((n) => n[0])
                      .join('')
                      .slice(0, 2)
                      .toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-[#18181b] truncate">
                      {currentStudent.full_name}
                    </div>
                    <div className="text-neutral-500 font-mono text-[11px]">
                      {currentStudent.college_roll_no}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full">
                    Verified
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="p-2.5 bg-neutral-50 border border-neutral-200/60 rounded-xl space-y-0.5">
                    <div className="text-neutral-400 font-medium flex items-center gap-1">
                      <Building2 className="w-3 h-3" />
                      <span>Branch</span>
                    </div>
                    <div className="font-semibold text-neutral-800 truncate">
                      {currentStudent.branch}
                    </div>
                  </div>

                  <div className="p-2.5 bg-neutral-50 border border-neutral-200/60 rounded-xl space-y-0.5">
                    <div className="text-neutral-400 font-medium flex items-center gap-1">
                      <GraduationCap className="w-3 h-3" />
                      <span>Semester</span>
                    </div>
                    <div className="font-semibold text-neutral-800">
                      Semester {currentStudent.semester}
                    </div>
                  </div>

                  <div className="p-2.5 bg-neutral-50 border border-neutral-200/60 rounded-xl space-y-0.5 col-span-2">
                    <div className="text-neutral-400 font-medium flex items-center gap-1">
                      <Mail className="w-3 h-3" />
                      <span>Institutional Email</span>
                    </div>
                    <div className="font-semibold text-neutral-800 truncate">
                      {currentStudent.email}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-neutral-100">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-xl transition cursor-pointer"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Log Out</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setShowAccountModal(false)
                      setFieldErrors({})
                      setAuthError(null)
                    }}
                    className="px-4 py-1.5 text-xs font-semibold text-white bg-[#18181b] hover:bg-black rounded-xl shadow-xs transition cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              /* Auth Form (Log In / Register) */
              <div className="space-y-4 text-xs">
                {/* Segmented Switcher */}
                <div className="flex items-center p-0.5 bg-[#eaecee] rounded-lg text-xs font-semibold text-neutral-600">
                  <button
                    type="button"
                    onClick={() => {
                      setAuthTab('login')
                      setAuthError(null)
                      setFieldErrors({})
                    }}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md transition cursor-pointer ${
                      authTab === 'login'
                        ? 'bg-white text-[#18181b] shadow-2xs'
                        : 'hover:text-neutral-900'
                    }`}
                  >
                    <LogIn className="w-3.5 h-3.5" />
                    <span>Log In</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAuthTab('register')
                      setAuthError(null)
                      setFieldErrors({})
                    }}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md transition cursor-pointer ${
                      authTab === 'register'
                        ? 'bg-white text-[#18181b] shadow-2xs'
                        : 'hover:text-neutral-900'
                    }`}
                  >
                    <UserPlus className="w-3.5 h-3.5" />
                    <span>Register</span>
                  </button>
                </div>

                {authTab === 'login' ? (
                  /* Login Form */
                  <form onSubmit={handleLoginSubmit} className="space-y-3">
                    <div>
                      <label className="block font-semibold text-neutral-700 mb-1">
                        College Roll No or Email
                      </label>
                      <div className="relative">
                        <Hash className="w-3.5 h-3.5 text-neutral-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          required
                          value={loginIdentifier}
                          onChange={(e) => {
                            setLoginIdentifier(e.target.value)
                            if (fieldErrors.loginIdentifier) {
                              setFieldErrors((prev) => {
                                const next = { ...prev }
                                delete next.loginIdentifier
                                return next
                              })
                            }
                          }}
                          placeholder="e.g. 21ECA045 or student@ecajmer.ac.in"
                          className={`w-full pl-8 pr-2.5 py-2 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 focus:outline-none focus:bg-white ${
                            fieldErrors.loginIdentifier
                              ? 'border-rose-400 focus:border-rose-600 bg-rose-50/20'
                              : 'border-[#e4e4e7] focus:border-neutral-900'
                          }`}
                        />
                      </div>
                      {fieldErrors.loginIdentifier && (
                        <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.loginIdentifier}</p>
                      )}
                    </div>

                    <div>
                      <label className="block font-semibold text-neutral-700 mb-1">
                        Password
                      </label>
                      <div className="relative">
                        <KeyRound className="w-3.5 h-3.5 text-neutral-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                        <input
                          type="password"
                          required
                          value={loginPassword}
                          onChange={(e) => {
                            setLoginPassword(e.target.value)
                            if (fieldErrors.loginPassword) {
                              setFieldErrors((prev) => {
                                const next = { ...prev }
                                delete next.loginPassword
                                return next
                              })
                            }
                          }}
                          placeholder="Enter your student password"
                          className={`w-full pl-8 pr-2.5 py-2 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 focus:outline-none focus:bg-white ${
                            fieldErrors.loginPassword
                              ? 'border-rose-400 focus:border-rose-600 bg-rose-50/20'
                              : 'border-[#e4e4e7] focus:border-neutral-900'
                          }`}
                        />
                      </div>
                      {fieldErrors.loginPassword && (
                        <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.loginPassword}</p>
                      )}
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-neutral-100">
                      <button
                        type="button"
                        onClick={() => {
                          setShowAccountModal(false)
                          setFieldErrors({})
                          setAuthError(null)
                        }}
                        className="px-3.5 py-1.5 text-xs font-semibold text-neutral-700 bg-neutral-100 hover:bg-neutral-200 rounded-xl transition cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={authLoading}
                        className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-[#18181b] hover:bg-black rounded-xl shadow-xs transition cursor-pointer disabled:opacity-50"
                      >
                        {authLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                        <span>Sign In</span>
                      </button>
                    </div>
                  </form>
                ) : (
                  /* Register Form */
                  <form onSubmit={handleRegisterSubmit} className="space-y-2.5">
                    <div>
                      <label className="block font-semibold text-neutral-700 mb-1">
                        Full Name
                      </label>
                      <input
                        type="text"
                        required
                        value={regFullName}
                        onChange={(e) => {
                          setRegFullName(e.target.value)
                          if (fieldErrors.regFullName) {
                            setFieldErrors((prev) => {
                              const next = { ...prev }
                              delete next.regFullName
                              return next
                            })
                          }
                        }}
                        placeholder="e.g. Priya Sharma"
                        className={`w-full px-2.5 py-1.5 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 focus:outline-none focus:bg-white ${
                          fieldErrors.regFullName
                            ? 'border-rose-400 focus:border-rose-600 bg-rose-50/20'
                            : 'border-[#e4e4e7] focus:border-neutral-900'
                        }`}
                      />
                      {fieldErrors.regFullName && (
                        <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.regFullName}</p>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block font-semibold text-neutral-700 mb-1">
                          Roll No
                        </label>
                        <input
                          type="text"
                          required
                          value={regRollNo}
                          onChange={(e) => {
                            setRegRollNo(e.target.value)
                            if (fieldErrors.regRollNo) {
                              setFieldErrors((prev) => {
                                const next = { ...prev }
                                delete next.regRollNo
                                return next
                              })
                            }
                          }}
                          placeholder="e.g. 22ECA108"
                          className={`w-full px-2.5 py-1.5 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 font-mono uppercase focus:outline-none focus:bg-white ${
                            fieldErrors.regRollNo
                              ? 'border-rose-400 focus:border-rose-600 bg-rose-50/20'
                              : 'border-[#e4e4e7] focus:border-neutral-900'
                          }`}
                        />
                        {fieldErrors.regRollNo && (
                          <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.regRollNo}</p>
                        )}
                      </div>
                      <div>
                        <label className="block font-semibold text-neutral-700 mb-1">
                          Email
                        </label>
                        <input
                          type="email"
                          required
                          value={regEmail}
                          onChange={(e) => {
                            setRegEmail(e.target.value)
                            if (fieldErrors.regEmail) {
                              setFieldErrors((prev) => {
                                const next = { ...prev }
                                delete next.regEmail
                                return next
                              })
                            }
                          }}
                          placeholder="priya@ecajmer.ac.in"
                          className={`w-full px-2.5 py-1.5 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 focus:outline-none focus:bg-white ${
                            fieldErrors.regEmail
                              ? 'border-rose-400 focus:border-rose-600 bg-rose-50/20'
                              : 'border-[#e4e4e7] focus:border-neutral-900'
                          }`}
                        />
                        {fieldErrors.regEmail && (
                          <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.regEmail}</p>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div className="col-span-2">
                        <div className="flex items-center justify-between mb-1">
                          <label className="block font-semibold text-neutral-700">
                            Department / Branch
                          </label>
                          <span className="text-[10px] text-neutral-400">
                            {isMastersBranch(regBranch) ? 'Masters (4 Sem)' : 'B.Tech (8 Sem)'}
                          </span>
                        </div>
                        <select
                          value={regBranch}
                          onChange={(e) => handleBranchChange(e.target.value)}
                          className={`w-full px-2 py-1.5 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 focus:outline-none focus:bg-white ${
                            fieldErrors.regBranch
                              ? 'border-rose-400 focus:border-rose-600'
                              : 'border-[#e4e4e7] focus:border-neutral-900'
                          }`}
                        >
                          {DEPARTMENTS_LIST.map((b) => (
                            <option key={b} value={b}>
                              {b}
                            </option>
                          ))}
                        </select>
                        {fieldErrors.regBranch && (
                          <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.regBranch}</p>
                        )}
                      </div>

                      <div>
                        <label className="block font-semibold text-neutral-700 mb-1">
                          Semester
                        </label>
                        <select
                          value={regSemester}
                          onChange={(e) => {
                            setRegSemester(Number(e.target.value))
                            if (fieldErrors.regSemester) {
                              setFieldErrors((prev) => {
                                const next = { ...prev }
                                delete next.regSemester
                                return next
                              })
                            }
                          }}
                          className={`w-full px-2 py-1.5 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 focus:outline-none focus:bg-white ${
                            fieldErrors.regSemester
                              ? 'border-rose-400 focus:border-rose-600'
                              : 'border-[#e4e4e7] focus:border-neutral-900'
                          }`}
                        >
                          {Array.from({ length: getMaxSemesters(regBranch) }, (_, i) => i + 1).map(
                            (s) => (
                              <option key={s} value={s}>
                                Sem {s}
                              </option>
                            )
                          )}
                        </select>
                        {fieldErrors.regSemester && (
                          <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.regSemester}</p>
                        )}
                      </div>
                    </div>

                    <div>
                      <label className="block font-semibold text-neutral-700 mb-1">
                        Password
                      </label>
                      <input
                        type="password"
                        required
                        minLength={6}
                        value={regPassword}
                        onChange={(e) => {
                          setRegPassword(e.target.value)
                          if (fieldErrors.regPassword) {
                            setFieldErrors((prev) => {
                              const next = { ...prev }
                              delete next.regPassword
                              return next
                            })
                          }
                        }}
                        placeholder="At least 6 characters"
                        className={`w-full px-2.5 py-1.5 bg-[#f8f9fa] border rounded-xl text-xs text-neutral-900 focus:outline-none focus:bg-white ${
                          fieldErrors.regPassword
                            ? 'border-rose-400 focus:border-rose-600 bg-rose-50/20'
                            : 'border-[#e4e4e7] focus:border-neutral-900'
                        }`}
                      />
                      {fieldErrors.regPassword && (
                        <p className="text-[10px] text-rose-600 mt-1">{fieldErrors.regPassword}</p>
                      )}
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-neutral-100">
                      <button
                        type="button"
                        onClick={() => {
                          setShowAccountModal(false)
                          setFieldErrors({})
                          setAuthError(null)
                        }}
                        className="px-3.5 py-1.5 text-xs font-semibold text-neutral-700 bg-neutral-100 hover:bg-neutral-200 rounded-xl transition cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={authLoading}
                        className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-[#18181b] hover:bg-black rounded-xl shadow-xs transition cursor-pointer disabled:opacity-50"
                      >
                        {authLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                        <span>Create Account</span>
                      </button>
                    </div>
                  </form>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
