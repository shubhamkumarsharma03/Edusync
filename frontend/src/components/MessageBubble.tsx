import React, { useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  RotateCcw,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'
import { MarkdownContent } from './MarkdownContent'

export interface BubbleMessage {
  id: string
  sender: 'user' | 'assistant'
  text: string
  timestamp: string
  suggestions?: string[]
  sources?: {
    title: string
    url?: string
    department?: string
    lastVerified?: string
    confidenceScore?: number
  }[]
  confidence?: 'high' | 'medium' | 'low' | string
  confidenceScore?: number
  isFallback?: boolean
  isError?: boolean
  queryId?: string
  feedback?: 'up' | 'down' | null
}

interface MessageBubbleProps {
  message: BubbleMessage
  onSuggestionClick?: (suggestion: string) => void
  onRetry?: (queryText: string) => void
  onFeedback?: (messageId: string, queryId: string | undefined, type: 'up' | 'down') => void
  userQueryForRetry?: string
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  onSuggestionClick,
  onRetry,
  onFeedback,
  userQueryForRetry,
}) => {
  const [copied, setCopied] = useState(false)
  const [feedbackFeedback, setFeedbackFeedback] = useState<string | null>(null)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleThumb = (type: 'up' | 'down') => {
    if (onFeedback) {
      onFeedback(message.id, message.queryId, type)
      setFeedbackFeedback(type === 'up' ? 'Positive feedback recorded' : 'Feedback recorded')
      setTimeout(() => setFeedbackFeedback(null), 2500)
    }
  }

  // 1. User Message
  if (message.sender === 'user') {
    return (
      <div className="flex justify-end pl-6 sm:pl-12">
        <div className="bg-white border border-[#e5e7eb] rounded-xl sm:rounded-2xl px-4 py-3 sm:px-5 sm:py-3.5 text-sm sm:text-[15px] text-[#18181b] shadow-xs max-w-full sm:max-w-xl md:max-w-2xl break-words">
          <p className="leading-relaxed whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    )
  }

  // 2. Error Message Bubble
  if (message.isError) {
    return (
      <div className="flex items-start gap-2.5 sm:gap-3.5 max-w-full sm:max-w-2xl md:max-w-3xl pr-4 sm:pr-8">
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-rose-50 border border-rose-200 flex-shrink-0 flex items-center justify-center p-1 mt-0.5 shadow-xs text-rose-600">
          <AlertCircle className="w-4 h-4" />
        </div>
        <div className="space-y-2 flex-1 min-w-0">
          <div className="bg-rose-50/60 border border-rose-200 rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm text-rose-950 leading-relaxed shadow-xs">
            <div className="flex items-center gap-1.5 font-semibold text-rose-800 text-xs sm:text-sm mb-1.5">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>Connection or Response Error</span>
            </div>
            <p className="text-neutral-700">{message.text}</p>

            {userQueryForRetry && onRetry && (
              <div className="mt-3.5 pt-3 border-t border-rose-200/80 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => onRetry(userQueryForRetry)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Retry Question</span>
                </button>
                <span className="text-[11px] text-neutral-500">
                  Ensure the FastAPI backend is running on port 8000.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // 3. Fallback Response Bubble (Confidence Gate Triggered / Out-of-Scope)
  if (message.isFallback) {
    return (
      <div className="flex items-start gap-2.5 sm:gap-3.5 max-w-full sm:max-w-2xl md:max-w-3xl pr-4 sm:pr-8">
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-amber-50 border border-amber-200 flex-shrink-0 flex items-center justify-center p-1 mt-0.5 shadow-xs text-amber-600">
          <AlertTriangle className="w-4 h-4" />
        </div>

        <div className="space-y-2 flex-1 min-w-0">
          <div className="bg-amber-50/40 border border-amber-200 rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm sm:text-[15px] text-[#18181b] leading-relaxed shadow-xs">
            {/* Fallback Banner */}
            <div className="flex items-center justify-between pb-2 mb-2.5 border-b border-amber-200/80 text-xs text-amber-800">
              <div className="flex items-center gap-1.5 font-semibold">
                <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
                <span>Trust Layer Gate: Unverified / Out-of-Scope</span>
              </div>
              <span className="px-2 py-0.5 bg-amber-100 text-amber-900 border border-amber-200 rounded-md text-[10px] font-bold uppercase tracking-wider">
                Low Confidence
              </span>
            </div>

            <MarkdownContent content={message.text} />

            <div className="mt-3.5 pt-3 border-t border-amber-200/60 text-xs text-neutral-500 bg-amber-100/30 rounded-lg p-2.5">
              <span className="font-semibold text-neutral-700 block mb-0.5">Note for Students:</span>
              EduSync grounds answers only in official Engineering College Ajmer circulars. If your question concerns general knowledge, unreleased notices, or personal matters, please consult the respective departmental office.
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex items-center gap-3 px-1 text-neutral-400">
            <button
              onClick={handleCopy}
              title="Copy message"
              className="hover:text-neutral-700 transition-colors p-1"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
            <button
              onClick={() => handleThumb('up')}
              title="Thumbs up"
              className={`hover:text-neutral-700 transition-colors p-1 ${
                message.feedback === 'up' ? 'text-blue-600' : ''
              }`}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => handleThumb('down')}
              title="Thumbs down"
              className={`hover:text-neutral-700 transition-colors p-1 ${
                message.feedback === 'down' ? 'text-rose-600' : ''
              }`}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
            {feedbackFeedback && (
              <span className="text-[11px] text-neutral-600 font-medium animate-in fade-in">
                {feedbackFeedback}
              </span>
            )}
          </div>
        </div>
      </div>
    )
  }

  // 4. Standard Verified Assistant Response Bubble
  const confidenceBadge =
    message.confidence === 'high' ? (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md text-[10px] font-semibold uppercase tracking-wider">
        <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
        High Confidence
      </span>
    ) : message.confidence === 'medium' ? (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-md text-[10px] font-semibold uppercase tracking-wider">
        <CheckCircle2 className="w-2.5 h-2.5 text-blue-600" />
        Medium Confidence
      </span>
    ) : null

  return (
    <div className="flex items-start gap-2.5 sm:gap-3.5 max-w-full sm:max-w-2xl md:max-w-3xl pr-4 sm:pr-8">
      {/* Bot Icon */}
      <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-white border border-[#e4e4e7] flex-shrink-0 flex items-center justify-center p-1 mt-0.5 shadow-xs">
        <img src="/logo-icon.png" alt="EduSync AI" className="w-full h-full object-contain" />
      </div>

      {/* Bubble Content */}
      <div className="space-y-2 flex-1 min-w-0">
        <div className="bg-[#f4f4f5] border border-transparent rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm sm:text-[15px] text-[#18181b] leading-relaxed break-words shadow-2xs">
          {/* Header Confidence Pill if present */}
          {confidenceBadge && (
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-neutral-200/60">
              <div className="flex items-center gap-1.5 text-xs text-neutral-500 font-medium">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Verified ECA Institutional Grounding</span>
              </div>
              {confidenceBadge}
            </div>
          )}

          <MarkdownContent content={message.text} />

          {/* Source Citations */}
          {message.sources && message.sources.length > 0 && (
            <div className="mt-3.5 pt-3 border-t border-neutral-200/80 space-y-1.5">
              <span className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider block">
                Official Sources & Provenance:
              </span>
              {message.sources.map((src, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 text-xs text-neutral-700 bg-white/90 px-3 py-2 rounded-lg border border-neutral-200 shadow-2xs hover:border-neutral-300 transition"
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-neutral-900 truncate">{src.title}</div>
                    <div className="flex items-center gap-2 text-[11px] text-neutral-400 mt-0.5">
                      {src.department && (
                        <span className="text-neutral-600 font-medium">{src.department}</span>
                      )}
                      {src.lastVerified && (
                        <span>&bull; {src.lastVerified}</span>
                      )}
                    </div>
                  </div>
                  {src.url && (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-indigo-600 hover:text-white bg-indigo-50 hover:bg-indigo-600 rounded-md border border-indigo-200 transition flex-shrink-0"
                      title="Open source circular PDF"
                    >
                      <span>View PDF</span>
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
            onClick={handleCopy}
            title="Copy message"
            className="hover:text-neutral-700 transition-colors p-1 cursor-pointer"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-emerald-600" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
          <button
            onClick={() => handleThumb('up')}
            title="Helpful (thumbs up)"
            className={`hover:text-neutral-700 transition-colors p-1 cursor-pointer ${
              message.feedback === 'up' ? 'text-blue-600' : ''
            }`}
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleThumb('down')}
            title="Unhelpful (thumbs down)"
            className={`hover:text-neutral-700 transition-colors p-1 cursor-pointer ${
              message.feedback === 'down' ? 'text-rose-600' : ''
            }`}
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
          {feedbackFeedback && (
            <span className="text-[11px] text-neutral-600 font-medium animate-in fade-in">
              {feedbackFeedback}
            </span>
          )}
        </div>

        {/* Follow-up Suggestions */}
        {message.suggestions && message.suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1.5">
            {message.suggestions.map((suggestion, index) => (
              <button
                key={index}
                onClick={() => onSuggestionClick && onSuggestionClick(suggestion)}
                className="px-3.5 py-1.5 rounded-full border border-[#d4d4d8] bg-white hover:bg-neutral-50 text-neutral-700 text-xs sm:text-[13px] font-normal transition-colors shadow-2xs active:scale-95 cursor-pointer"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
