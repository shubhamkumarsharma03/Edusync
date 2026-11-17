import React, { useEffect, useRef, useState } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Cpu,
  Database,
  ExternalLink,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  Layers,
  Pause,
  RefreshCw,
  Terminal,
  X,
} from 'lucide-react'
import { getLiveProgress, pauseFetchSource, PipelineProgressState } from '../api/sources'

interface LivePipelineModalProps {
  isOpen: boolean
  onClose: () => void
  sourceId?: string
  sourceName?: string
}

const STEPS = [
  { id: 1, key: 'portal_fetch', label: 'Portal Fetch', desc: 'Query notices & index', icon: Layers },
  { id: 2, key: 'hash_check', label: 'Hash Verification', desc: 'SHA-256 diff check', icon: FileCheck2 },
  { id: 3, key: 'ocr_inference', label: 'Baidu PaddleOCR', desc: 'Layout & table extraction', icon: Cpu },
  { id: 4, key: 'chunking', label: 'Semantic Chunking', desc: 'Table isolation & rows', icon: FileSpreadsheet },
  { id: 5, key: 'embedding', label: 'Vector Storage', desc: 'pgvector embedding upsert', icon: Database },
]

export const LivePipelineModal: React.FC<LivePipelineModalProps> = ({
  isOpen,
  onClose,
  sourceId,
  sourceName,
}) => {
  const [progress, setProgress] = useState<PipelineProgressState | null>(null)
  const [loading, setLoading] = useState(true)
  const [isManualRefreshing, setIsManualRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [copied, setCopied] = useState(false)
  const terminalEndRef = useRef<HTMLDivElement>(null)

  const fetchState = async (isManual = false) => {
    if (isManual) setIsManualRefreshing(true)
    try {
      const data = await getLiveProgress(sourceId)
      setProgress(data)
      setError(null)
      setLoading(false)
    } catch (err: any) {
      setError(err.message || 'Failed to connect to live progress stream')
      setLoading(false)
    } finally {
      if (isManual) {
        setTimeout(() => setIsManualRefreshing(false), 500)
      }
    }
  }

  // Auto-polling every 5 seconds (5000ms) while modal is open
  useEffect(() => {
    if (!isOpen) return

    let isMounted = true

    const runPoll = async () => {
      try {
        const data = await getLiveProgress(sourceId)
        if (isMounted) {
          setProgress(data)
          setError(null)
          setLoading(false)
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Failed to connect to live progress stream')
          setLoading(false)
        }
      }
    }

    runPoll()
    const interval = setInterval(runPoll, 5000)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [isOpen, sourceId])

  // Auto-scroll terminal to bottom
  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [progress?.logs, autoScroll])

  if (!isOpen) return null

  const handleCopyLogs = () => {
    if (!progress?.logs) return
    const text = progress.logs
      .map((l) => `[${l.timestamp}] [${l.tag || l.level.toUpperCase()}] ${l.message}`)
      .join('\n')
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const currentStepIdx = progress?.step_index || 0
  const isFetching = progress?.status === 'fetching'
  const isCompleted = progress?.status === 'completed'
  const isError = progress?.status === 'error'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/40 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white border border-neutral-200 w-full max-w-4xl max-h-[90vh] rounded-2xl shadow-xl flex flex-col overflow-hidden text-[#18181b]">
        {/* MODAL HEADER - Minimal & Clean matching Chat/Admin UI */}
        <div className="px-5 py-4 border-b border-neutral-200 bg-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <img
                src="/logo.png"
                alt="EduSync Logo"
                className="h-6 w-auto object-contain"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                }}
              />
              <div className="p-1.5 bg-neutral-100 text-neutral-800 rounded-lg border border-neutral-200">
                <Activity className={`w-4 h-4 ${isFetching ? 'animate-pulse' : ''}`} />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-semibold text-neutral-900">
                  Live Pipeline Inspector
                </h2>
                {isFetching && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-neutral-100 text-neutral-800 border border-neutral-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Live Active
                  </span>
                )}
                {isCompleted && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                    Completed
                  </span>
                )}
                {isError && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                    <AlertCircle className="w-3 h-3 text-rose-600" />
                    Error
                  </span>
                )}
              </div>
              <p className="text-xs text-neutral-500 mt-0.5">
                Source: <span className="font-medium text-neutral-800">{sourceName || progress?.source_name || 'All Active Sources'}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-neutral-500 bg-neutral-100 px-2.5 py-1 rounded-lg border border-neutral-200">
              <Clock className="w-3.5 h-3.5 text-neutral-400" />
              <span>Auto-polling (5s)</span>
            </div>
            {isFetching && sourceId && (
              <button
                onClick={async () => {
                  try {
                    await pauseFetchSource(sourceId)
                    fetchState(true)
                  } catch (e) {
                    console.error('Failed to pause source', e)
                  }
                }}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg border border-amber-200 transition"
                title="Pause ingestion"
              >
                <Pause className="w-3.5 h-3.5 fill-current" />
                <span>Pause</span>
              </button>
            )}
            <button
              onClick={() => fetchState(true)}
              className="p-1.5 text-neutral-500 hover:text-neutral-900 hover:bg-neutral-100 rounded-lg transition border border-transparent hover:border-neutral-200"
              title="Refresh now"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isManualRefreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 rounded-lg transition"
              title="Close inspector"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* MODAL BODY (SCROLLABLE) */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 bg-neutral-50/50">
          {error && (
            <div className="bg-rose-50 border border-rose-200 text-rose-800 px-3.5 py-2.5 rounded-xl text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading && !progress && (
            <div className="py-6 flex items-center justify-center gap-2 text-xs text-neutral-500 bg-white rounded-xl border border-neutral-200">
              <RefreshCw className="w-4 h-4 animate-spin text-neutral-700" />
              <span>Connecting to live pipeline stream...</span>
            </div>
          )}

          {/* PIPELINE 5-STAGE STEPPER */}
          <div className="bg-white p-3.5 sm:p-4 rounded-xl border border-neutral-200 shadow-xs">
            <div className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider mb-2.5">
              Pipeline Execution Lifecycle
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {STEPS.map((step) => {
                const isStepCompleted = isCompleted || (isFetching && currentStepIdx > step.id)
                const isStepActive = isFetching && currentStepIdx === step.id
                const StepIcon = step.icon

                return (
                  <div
                    key={step.id}
                    className={`p-2.5 sm:p-3 rounded-xl border text-left transition-all ${
                      isStepActive
                        ? 'bg-neutral-900 text-white border-neutral-900 shadow-xs ring-1 ring-neutral-900'
                        : isStepCompleted
                        ? 'bg-neutral-50 border-neutral-200 text-neutral-800'
                        : 'bg-white border-neutral-200/80 text-neutral-400'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div
                        className={`w-5 h-5 rounded-md flex items-center justify-center text-xs font-semibold ${
                          isStepActive
                            ? 'bg-white text-neutral-900'
                            : isStepCompleted
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : 'bg-neutral-100 text-neutral-500'
                        }`}
                      >
                        {isStepCompleted ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        ) : isStepActive ? (
                          <RefreshCw className="w-3 h-3 animate-spin text-neutral-900" />
                        ) : (
                          step.id
                        )}
                      </div>
                      <StepIcon
                        className={`w-3.5 h-3.5 ${
                          isStepActive
                            ? 'text-neutral-200'
                            : isStepCompleted
                            ? 'text-emerald-600'
                            : 'text-neutral-400'
                        }`}
                      />
                    </div>
                    <div
                      className={`text-xs font-medium truncate ${
                        isStepActive ? 'text-white font-semibold' : 'text-neutral-800'
                      }`}
                    >
                      {step.label}
                    </div>
                    <div
                      className={`text-[10px] truncate mt-0.5 ${
                        isStepActive ? 'text-neutral-300' : 'text-neutral-400'
                      }`}
                    >
                      {step.desc}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* DUAL ACTION CARDS: CURRENT & NEXT ACTION */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {/* CURRENT STEP CARD - Minimal White Card */}
            <div className="bg-white border border-neutral-200 rounded-xl p-4 sm:p-5 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    Current Action (Step {currentStepIdx}/5)
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-neutral-100 text-neutral-700 border border-neutral-200">
                    {progress?.phase?.toUpperCase() || 'IDLE'}
                  </span>
                </div>
                <h3 className="text-sm sm:text-base font-semibold text-neutral-900 leading-snug">
                  {progress?.current_action || 'Standing by for pipeline task'}
                </h3>
              </div>

              {progress?.active_document ? (
                <div className="mt-3.5 pt-3 border-t border-neutral-100 text-xs flex items-center justify-between gap-2 text-neutral-600 bg-neutral-50/80 p-2.5 rounded-lg border border-neutral-200/60">
                  <div className="flex items-center gap-2 truncate min-w-0">
                    <FileText className="w-4 h-4 text-neutral-500 shrink-0" />
                    <span className="truncate font-medium text-neutral-900">
                      {progress.active_document.filename || progress.active_document.title}
                    </span>
                    {progress.active_document.size_kb ? (
                      <span className="text-[11px] text-neutral-400 shrink-0">
                        ({progress.active_document.size_kb} KB)
                      </span>
                    ) : null}
                  </div>
                  {progress.active_document.url && (
                    <a
                      href={progress.active_document.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-neutral-600 hover:text-neutral-900 transition flex items-center gap-1 shrink-0 font-medium"
                      title="Open attachment"
                    >
                      <span className="text-[11px]">PDF</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              ) : (
                <div className="mt-3.5 pt-3 border-t border-neutral-100 text-xs text-neutral-400 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                  <span>No document currently active</span>
                </div>
              )}
            </div>

            {/* WHAT WILL BE NEXT DONE CARD - Minimal White Card */}
            <div className="bg-white border border-neutral-200 rounded-xl p-4 sm:p-5 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500 flex items-center gap-1.5">
                    <ArrowRight className="w-3.5 h-3.5 text-neutral-400" />
                    What Will Be Next Done
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-neutral-100 text-neutral-600 border border-neutral-200 font-medium">
                    Upcoming Step
                  </span>
                </div>
                <h3 className="text-sm sm:text-base font-medium text-neutral-700 leading-snug">
                  {progress?.next_action || 'Next pipeline step will be scheduled automatically.'}
                </h3>
              </div>

              <div className="mt-3.5 pt-3 border-t border-neutral-100 flex items-center gap-2 text-xs text-neutral-500">
                <Cpu className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                <span className="truncate">
                  Baidu PaddleOCR-VL & SHA-256 hash caching enabled (0 re-embed overhead).
                </span>
              </div>
            </div>
          </div>

          {/* REAL-TIME STATS COUNTERS */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
            <div className="bg-white p-3 rounded-xl border border-neutral-200 text-center shadow-xs">
              <div className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">Checked</div>
              <div className="text-base sm:text-lg font-bold text-neutral-900 mt-0.5">
                {progress?.stats.checked || 0} / {progress?.stats.total || 0}
              </div>
            </div>
            <div className="bg-white p-3 rounded-xl border border-neutral-200 text-center shadow-xs">
              <div className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">OCR Processed</div>
              <div className="text-base sm:text-lg font-bold text-neutral-800 mt-0.5">
                {progress?.stats.ocr_count || 0}
              </div>
            </div>
            <div className="bg-white p-3 rounded-xl border border-neutral-200 text-center shadow-xs">
              <div className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">Hash Bypassed</div>
              <div className="text-base sm:text-lg font-bold text-emerald-600 mt-0.5">
                {progress?.stats.bypassed_count || 0}
              </div>
            </div>
            <div className="bg-white p-3 rounded-xl border border-neutral-200 text-center shadow-xs">
              <div className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">Chunks Embedded</div>
              <div className="text-base sm:text-lg font-bold text-neutral-800 mt-0.5">
                {progress?.stats.chunks_count || 0}
              </div>
            </div>
            <div className="bg-white p-3 rounded-xl border border-neutral-200 text-center shadow-xs col-span-2 sm:col-span-1">
              <div className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">Created / Updated</div>
              <div className="text-base sm:text-lg font-bold text-neutral-900 mt-0.5">
                {progress?.stats.created_count || 0} / {progress?.stats.updated_count || 0}
              </div>
            </div>
          </div>

          {/* LIVE BACKEND TERMINAL LOGS */}
          <div className="bg-[#18181b] rounded-xl border border-neutral-800 shadow-inner flex flex-col overflow-hidden">
            {/* Terminal Header Bar */}
            <div className="bg-[#202024] px-4 py-2.5 border-b border-neutral-800 flex items-center justify-between text-xs text-neutral-300">
              <div className="flex items-center gap-2">
                <Terminal className="w-3.5 h-3.5 text-neutral-400" />
                <span className="font-mono font-medium text-neutral-200">Live Ingestion Terminal</span>
                {isFetching && (
                  <span className="flex h-2 w-2 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                )}
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setAutoScroll(!autoScroll)}
                  className={`text-[11px] px-2 py-0.5 rounded transition ${
                    autoScroll
                      ? 'bg-neutral-800 text-neutral-200 border border-neutral-700'
                      : 'text-neutral-400 hover:text-white'
                  }`}
                >
                  Auto-Scroll: {autoScroll ? 'ON' : 'OFF'}
                </button>
                <button
                  onClick={handleCopyLogs}
                  className="flex items-center gap-1 text-[11px] text-neutral-400 hover:text-white transition"
                  title="Copy terminal logs"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            {/* Terminal Console View */}
            <div className="p-4 font-mono text-[11px] sm:text-xs leading-relaxed max-h-60 sm:max-h-64 overflow-y-auto space-y-1.5 text-neutral-300">
              {progress?.logs && progress.logs.length > 0 ? (
                progress.logs.map((log, index) => {
                  let tagBg = 'bg-neutral-800 text-neutral-300 border border-neutral-700'
                  let textCol = 'text-neutral-300'

                  if (log.level === 'ocr') {
                    tagBg = 'bg-amber-950/60 text-amber-300 border border-amber-800/80'
                    textCol = 'text-amber-200'
                  } else if (log.level === 'embed' || log.level === 'chunk') {
                    tagBg = 'bg-blue-950/60 text-blue-300 border border-blue-800/80'
                    textCol = 'text-blue-200'
                  } else if (log.level === 'bypass') {
                    tagBg = 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/80'
                    textCol = 'text-emerald-200'
                  } else if (log.level === 'success') {
                    tagBg = 'bg-emerald-900/80 text-emerald-200 border border-emerald-700'
                    textCol = 'text-emerald-300 font-medium'
                  } else if (log.level === 'error') {
                    tagBg = 'bg-rose-950 text-rose-300 border border-rose-800'
                    textCol = 'text-rose-200'
                  } else if (log.level === 'fetch') {
                    tagBg = 'bg-neutral-800 text-neutral-300 border border-neutral-700'
                    textCol = 'text-neutral-300'
                  }

                  return (
                    <div
                      key={index}
                      className="flex items-start gap-2 group hover:bg-neutral-800/40 px-1 py-0.5 rounded transition"
                    >
                      <span className="text-neutral-500 select-none text-[10px] sm:text-[11px] shrink-0 font-mono mt-0.5">
                        {log.timestamp}
                      </span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider shrink-0 ${tagBg}`}
                      >
                        {log.tag || log.level}
                      </span>
                      <span className={`break-words flex-1 ${textCol}`}>{log.message}</span>
                    </div>
                  )
                })
              ) : (
                <div className="py-8 text-center text-neutral-500">
                  <Clock className="w-5 h-5 mx-auto mb-2 text-neutral-600" />
                  <p>Awaiting live execution events...</p>
                </div>
              )}
              <div ref={terminalEndRef} />
            </div>
          </div>
        </div>

        {/* MODAL FOOTER */}
        <div className="px-5 py-3 border-t border-neutral-200 bg-white flex items-center justify-between text-xs text-neutral-500">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
            <span>EduSync Ingestion Engine</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-[#18181b] hover:bg-neutral-800 text-white rounded-lg text-xs font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
