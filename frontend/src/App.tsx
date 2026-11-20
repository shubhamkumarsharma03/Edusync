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
} from 'lucide-react'
import { checkBackendHealth } from './api/client'
import { sendChatMessage, sendChatFeedback } from './api/chat'
import { AdminDashboard } from './components/AdminDashboard'
import { MessageBubble, BubbleMessage } from './components/MessageBubble'
import { DepartmentSelector } from './components/DepartmentSelector'

const INITIAL_MESSAGES: BubbleMessage[] = [
  {
    id: '1',
    sender: 'assistant',
    text: 'Hello! I am EduSync, the institutional AI assistant for Engineering College Ajmer. Ask me about exam schedules, fees, syllabi, or official circulars.',
    timestamp: 'Today 9:41 AM',
    suggestions: [
      'Mid-term exam schedule for CSE',
      'Semester fee notice and due dates',
      'Mercy exam rules for B.Tech',
      'Central Library book issue timings',
    ],
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

  const [messages, setMessages] = useState<BubbleMessage[]>(INITIAL_MESSAGES)
  const [input, setInput] = useState('')
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all')
  const [lastUserQuery, setLastUserQuery] = useState<string>('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(false)
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

  useEffect(() => {
    checkBackendHealth()
      .then((res) => setIsBackendOnline(res.status === 'healthy'))
      .catch(() => setIsBackendOnline(false))
  }, [])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Auto-grow textarea height dynamically
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim()
    if (!query || isTyping) return

    setLastUserQuery(query)

    const userMsg: BubbleMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    if (!textToSend) {
      setInput('')
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }

    setIsTyping(true)
    try {
      const historyPayload = messages.slice(-4).map((m) => ({
        role: m.sender as 'user' | 'assistant',
        content: m.text,
      }))

      const res = await sendChatMessage(
        query,
        selectedDepartment === 'all' ? null : selectedDepartment,
        historyPayload
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
        sources: res.sources.map((s) => ({
          title: s.title,
          url: s.url,
          department: s.department,
          lastVerified: s.last_verified,
          confidenceScore: s.confidence_score,
        })),
      }
      setMessages((prev) => [...prev, botMsg])
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
      setMessages((prev) => [...prev, errorMsg])
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
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, feedback: msg.feedback === type ? null : type } : msg
      )
    )

    if (queryId) {
      try {
        await sendChatFeedback(queryId, type)
      } catch (err) {
        console.warn('Failed to record student feedback to server:', err)
      }
    }
  }

  const openAdminInNewTab = () => {
    window.open('/admin', '_blank')
  }

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

      {/* Responsive Left Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 sm:w-64 bg-[#f8f9fa] border-r border-[#ebecee] flex flex-col justify-between transition-transform duration-250 ease-in-out lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0 shadow-2xl lg:shadow-none' : '-translate-x-full'
        }`}
      >
        <div className="p-4 sm:p-5">
          {/* Logo Header */}
          <div className="flex items-center justify-between pb-6">
            <div className="flex items-center gap-2.5">
              <img src="/logo.png" alt="EduSync" className="h-7 w-auto object-contain" />
            </div>
            <button
              className="lg:hidden p-1.5 text-neutral-400 hover:text-neutral-700 rounded-md"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close sidebar"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Section */}
          <div className="mb-6">
            <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider px-2 mb-2">
              Navigation
            </h3>
            <nav className="space-y-1">
              <button className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold rounded-lg bg-[#eaecee] text-[#18181b]">
                <MessageSquare className="w-3.5 h-3.5 text-neutral-700" />
                <span>Student Assistant</span>
              </button>

              <button
                onClick={openAdminInNewTab}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg text-neutral-600 hover:bg-neutral-200/50 hover:text-[#18181b] transition-colors group"
                title="Open Admin Data Sources in a new tab"
              >
                <div className="flex items-center gap-2.5">
                  <Database className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Data Sources</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-bold border border-indigo-100">
                    Admin
                  </span>
                  <ExternalLink className="w-3 h-3 text-neutral-400 group-hover:text-neutral-700" />
                </div>
              </button>
            </nav>
          </div>

          {/* History Navigation */}
          <div>
            <h3 className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider px-2 mb-2">
              History
            </h3>
            <nav className="space-y-1">
              <button className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-lg bg-[#eaecee] text-[#18181b]">
                <History className="w-3.5 h-3.5 text-neutral-700" />
                <span>Recent Chats</span>
              </button>
              <button className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-lg text-neutral-600 hover:bg-neutral-200/50 hover:text-[#18181b] transition-colors">
                <Archive className="w-3.5 h-3.5" />
                <span>Archived</span>
              </button>
              <button className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-lg text-neutral-600 hover:bg-neutral-200/50 hover:text-[#18181b] transition-colors">
                <Pin className="w-3.5 h-3.5" />
                <span>Pinned</span>
              </button>
            </nav>
          </div>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[#ebecee] flex items-center justify-between text-xs text-neutral-500">
          <span className="text-[11px] font-medium truncate max-w-[120px]">ECA Assistant</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendOnline ? 'bg-emerald-500' : 'bg-neutral-300'
              }`}
            />
            <span className="text-[11px] text-neutral-500">
              {isBackendOnline ? 'Online' : 'Offline'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Chat Interface */}
      <div className="flex-1 flex flex-col h-full bg-[#fcfcfc] relative min-w-0">
        {/* Responsive Header */}
        <header className="h-14 border-b border-[#f0f0f2] flex items-center justify-between px-3 sm:px-6 bg-[#fcfcfc] sticky top-0 z-30 flex-shrink-0">
          {/* Left Actions */}
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 text-neutral-700 hover:text-neutral-950 rounded-md hover:bg-neutral-100 transition-colors"
              aria-label="Open menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          </div>

          {/* Center Brand */}
          <div className="flex items-center gap-2">
            <img src="/logo-icon.png" alt="EduSync" className="w-6 h-6 object-contain" />
            <span className="font-semibold text-base sm:text-lg tracking-tight text-[#18181b]">
              EduSync
            </span>
            <span
              className={`w-2 h-2 rounded-full ${isBackendOnline ? 'bg-emerald-500' : 'bg-neutral-300'}`}
              title={isBackendOnline ? 'Online' : 'Offline'}
            />
          </div>

          {/* Right Actions: Admin Panel Link in New Tab */}
          <div className="flex items-center gap-2">
            <a
              href="/admin"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-neutral-50 text-neutral-700 hover:text-[#18181b] rounded-xl text-xs font-semibold border border-[#e4e4e7] shadow-2xs transition"
              title="Open Admin Data Sources in a new tab"
            >
              <Database className="w-3.5 h-3.5 text-indigo-600" />
              <span>Admin Panel</span>
              <ExternalLink className="w-3 h-3 text-neutral-400" />
            </a>
          </div>
        </header>

        {/* Dynamic Scrollable Chat Canvas */}
        <main className="flex-1 overflow-y-auto px-3 sm:px-6 md:px-8 py-4 sm:py-6 space-y-4 sm:space-y-6 w-full max-w-3xl lg:max-w-4xl mx-auto">
          {/* Centered Timestamp */}
          <div className="text-center pt-1 pb-2">
            <span className="text-xs sm:text-[13px] text-neutral-400 font-normal">
              {messages[0]?.timestamp || 'Today 9:41 AM'}
            </span>
          </div>

          {/* Chat Messages */}
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

          {/* Loading / Searching Indicator */}
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

        {/* Dynamic Responsive Input Bar with Department Selector Filter */}
        <div className="p-3 sm:p-5 md:p-6 bg-gradient-to-t from-[#fcfcfc] via-[#fcfcfc] to-transparent sticky bottom-0 z-20 flex-shrink-0">
          <div className="max-w-3xl lg:max-w-4xl mx-auto space-y-2">
            {/* Department Filter Selector (FR: All, CSE, Examination, Registrar, Civil, EE, Mech, ECE, MCA, MBA) */}
            <DepartmentSelector
              selectedDept={selectedDepartment}
              onSelectDept={setSelectedDepartment}
            />

            {/* Input Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSend()
              }}
              className="flex items-end gap-2 bg-white border border-[#e4e4e7] rounded-2xl px-3 py-2 sm:px-4 sm:py-2.5 shadow-xs focus-within:border-neutral-400 focus-within:shadow-md transition-all"
            >
              <button
                type="button"
                className="p-1.5 text-neutral-400 hover:text-neutral-700 rounded-lg transition-colors flex-shrink-0 mb-0.5"
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
                className={`p-2 rounded-xl flex items-center justify-center transition-all flex-shrink-0 mb-0.5 ${
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
      </div>
    </div>
  )
}

export default App
