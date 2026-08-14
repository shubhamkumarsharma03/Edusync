import React, { useState, useEffect, useRef } from 'react'
import {
  Settings,
  History,
  Archive,
  Pin,
  Plus,
  Send,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Menu,
  X,
  Bot,
  ExternalLink,
  Share2,
} from 'lucide-react'
import { checkBackendHealth } from './api/client'

interface Message {
  id: string
  sender: 'user' | 'assistant'
  text: string
  timestamp: string
  suggestions?: string[]
  sources?: {
    title: string
    url?: string
    lastVerified?: string
  }[]
  feedback?: 'up' | 'down' | null
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: '1',
    sender: 'assistant',
    text: 'Hello. I am EduSync. How can I assist you with your research or college circulars today?',
    timestamp: 'Today 9:41 AM',
    suggestions: [
      'Analyze dataset',
      'Summarize article',
      'Mid-term schedule',
      'Semester fee notice',
    ],
  },
]

export const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES)
  const [input, setInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

  const handleSend = (textToSend?: string) => {
    const query = (textToSend || input).trim()
    if (!query) return

    const userMsg: Message = {
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

    // Responsive simulated bot reply
    setTimeout(() => {
      let botReply =
        'Certainly. Recent developments in quantum error correction (QEC), specifically concerning surface codes, have focused on lowering overhead and improving logical qubit fidelity.\n\nReal-time decoding: Advancements in FPGA-based decoders allow for faster-than-coherence-time error tracking.'
      let sources = [
        {
          title: 'Quantum Architecture Circular (Notice No. ECA/Res/2026/14)',
          url: 'https://ecajmer.ac.in/notices/research-qec.pdf',
          lastVerified: '2026-08-10',
        },
      ]

      if (query.toLowerCase().includes('fee')) {
        botReply =
          'According to the Accounts Branch circular, the last date for submitting odd-semester academic fees without late fee penalty is 31 August 2026.'
        sources = [
          {
            title: 'Odd-Semester Fee Schedule Notification 2026-27',
            url: 'https://ecajmer.ac.in/accounts/fee-notice-2026.pdf',
            lastVerified: '2026-08-12',
          },
        ]
      } else if (query.toLowerCase().includes('exam') || query.toLowerCase().includes('schedule')) {
        botReply =
          'The mid-semester examinations for CS/IT are scheduled to commence from 14 September 2026 per the official examination cell notification.'
        sources = [
          {
            title: 'Mid-Term Examination Circular (Notice No. ECA/Exam/2026/89)',
            url: 'https://ecajmer.ac.in/notices/exam-2026.pdf',
            lastVerified: '2026-08-10',
          },
        ]
      }

      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: botReply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources,
      }
      setMessages((prev) => [...prev, botMsg])
    }, 400)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleFeedback = (id: string, type: 'up' | 'down') => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === id ? { ...msg, feedback: msg.feedback === type ? null : type } : msg
      )
    )
  }

  return (
    <div className="flex h-[100dvh] w-full bg-[#fcfcfc] text-[#1a1a1a] overflow-hidden font-['Inter',sans-serif]">
      {/* Mobile Backdrop Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/25 backdrop-blur-sm z-40 lg:hidden transition-opacity"
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
              <div className="w-6 h-6 rounded-md bg-[#18181b] flex items-center justify-center text-white shadow-sm">
                <Bot className="w-3.5 h-3.5" />
              </div>
              <span className="font-bold text-base tracking-tight text-[#18181b]">EduSync</span>
            </div>
            <button
              className="lg:hidden p-1.5 text-neutral-400 hover:text-neutral-700 rounded-md"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close sidebar"
            >
              <X className="w-5 h-5" />
            </button>
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
          {/* Left Actions (Mobile drawer button / Share icon) */}
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 text-neutral-700 hover:text-neutral-950 rounded-md hover:bg-neutral-100 transition-colors"
              aria-label="Open menu"
            >
              <Menu className="w-5 h-5" />
            </button>
            <button
              className="p-1.5 text-neutral-500 hover:text-neutral-800 rounded-md hover:bg-neutral-100 transition-colors hidden sm:flex"
              title="Share chat"
            >
              <Share2 className="w-4 h-4" />
            </button>
          </div>

          {/* Center Brand / Status */}
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base sm:text-lg tracking-tight text-[#18181b]">
              EduSync
            </span>
            <span className="w-2 h-2 rounded-full bg-blue-500" />
          </div>

          {/* Right Actions */}
          <div className="flex items-center gap-1">
            <button
              title="Settings"
              className="p-2 text-neutral-500 hover:text-neutral-900 rounded-md hover:bg-neutral-100 transition-colors"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Dynamic Scrollable Chat Canvas */}
        <main className="flex-1 overflow-y-auto px-3 sm:px-6 md:px-8 py-4 sm:py-6 space-y-4 sm:space-y-6 w-full max-w-3xl lg:max-w-4xl mx-auto">
          {/* Centered Timestamp */}
          <div className="text-center pt-1 pb-2">
            <span className="text-xs sm:text-[13px] text-neutral-400 font-normal">
              {messages[0]?.timestamp || 'Today'}
            </span>
          </div>

          {/* Chat Messages */}
          {messages.map((msg) => (
            <div key={msg.id} className="space-y-2 sm:space-y-3">
              {msg.sender === 'user' ? (
                /* User Bubble */
                <div className="flex justify-end pl-6 sm:pl-12">
                  <div className="bg-white border border-[#e5e7eb] rounded-xl sm:rounded-2xl px-4 py-3 sm:px-5 sm:py-3.5 text-sm sm:text-[15px] text-[#18181b] shadow-[0_1px_2px_rgba(0,0,0,0.04)] max-w-full sm:max-w-xl md:max-w-2xl break-words">
                    <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                  </div>
                </div>
              ) : (
                /* Assistant Bubble */
                <div className="flex items-start gap-2.5 sm:gap-3.5 max-w-full sm:max-w-2xl md:max-w-3xl pr-4 sm:pr-8">
                  {/* Bot Icon */}
                  <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-md bg-[#18181b] flex-shrink-0 flex items-center justify-center text-white mt-1 shadow-sm">
                    <Bot className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  </div>

                  {/* Bubble Content */}
                  <div className="space-y-2 flex-1 min-w-0">
                    <div className="bg-[#f4f4f5] rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm sm:text-[15px] text-[#18181b] leading-relaxed break-words">
                      <p className="whitespace-pre-wrap">{msg.text}</p>

                      {/* Sources */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-3.5 pt-3 border-t border-neutral-200/80 space-y-1.5">
                          <span className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider block">
                            Sources:
                          </span>
                          {msg.sources.map((src, idx) => (
                            <div
                              key={idx}
                              className="flex items-center gap-1.5 text-xs text-neutral-700 bg-white/80 px-2.5 py-1.5 rounded-lg border border-neutral-200"
                            >
                              <span className="font-medium truncate">{src.title}</span>
                              {src.lastVerified && (
                                <span className="text-[11px] text-neutral-400 flex-shrink-0">
                                  &bull; {src.lastVerified}
                                </span>
                              )}
                              {src.url && (
                                <a
                                  href={src.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="ml-auto text-neutral-500 hover:text-neutral-900 flex-shrink-0"
                                >
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Actions Toolbar */}
                    <div className="flex items-center gap-3 px-1 text-neutral-400">
                      <button
                        onClick={() => handleCopy(msg.id, msg.text)}
                        title="Copy message"
                        className="hover:text-neutral-700 transition-colors p-1"
                      >
                        {copiedId === msg.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <button
                        onClick={() => handleFeedback(msg.id, 'up')}
                        title="Thumbs up"
                        className={`hover:text-neutral-700 transition-colors p-1 ${
                          msg.feedback === 'up' ? 'text-blue-600' : ''
                        }`}
                      >
                        <ThumbsUp className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleFeedback(msg.id, 'down')}
                        title="Thumbs down"
                        className={`hover:text-neutral-700 transition-colors p-1 ${
                          msg.feedback === 'down' ? 'text-rose-600' : ''
                        }`}
                      >
                        <ThumbsDown className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Suggestions */}
                    {msg.suggestions && (
                      <div className="flex flex-wrap gap-2 pt-1.5">
                        {msg.suggestions.map((suggestion, index) => (
                          <button
                            key={index}
                            onClick={() => handleSend(suggestion)}
                            className="px-3.5 py-1.5 rounded-full border border-[#d4d4d8] bg-white hover:bg-neutral-50 text-neutral-700 text-xs sm:text-[13px] font-normal transition-colors shadow-sm active:scale-95"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          <div ref={messagesEndRef} />
        </main>

        {/* Dynamic Responsive Input Bar */}
        <div className="p-3 sm:p-5 md:p-6 bg-gradient-to-t from-[#fcfcfc] via-[#fcfcfc] to-transparent sticky bottom-0 z-20 flex-shrink-0">
          <div className="max-w-3xl lg:max-w-4xl mx-auto">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                handleSend()
              }}
              className="flex items-end gap-2 bg-white border border-[#e4e4e7] rounded-2xl px-3 py-2 sm:px-4 sm:py-2.5 shadow-[0_2px_8px_rgba(0,0,0,0.04)] focus-within:border-neutral-400 focus-within:shadow-[0_2px_12px_rgba(0,0,0,0.08)] transition-all"
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
                placeholder="Message EduSync..."
                className="flex-1 bg-transparent text-sm sm:text-[15px] text-[#18181b] placeholder-neutral-400 focus:outline-none px-1 py-1 font-normal resize-none max-h-28 overflow-y-auto leading-relaxed"
              />

              <button
                type="submit"
                disabled={!input.trim()}
                className={`p-2 rounded-xl flex items-center justify-center transition-all flex-shrink-0 mb-0.5 ${
                  input.trim()
                    ? 'bg-[#18181b] text-white hover:bg-black cursor-pointer shadow-sm'
                    : 'text-neutral-300 cursor-not-allowed'
                }`}
                title="Send"
              >
                <Send className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button>
            </form>

            <p className="text-center text-[10px] sm:text-[11px] text-neutral-400 mt-2">
              EduSync can make mistakes. Consider verifying important information.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
