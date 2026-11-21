import React, { useState, useEffect } from 'react'
import {
  Wrench,
  Search,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  Database,
  Layers,
  Cpu,
  RefreshCw,
} from 'lucide-react'
import {
  SystemHealthData,
  RAGPlaygroundResponse,
  getSystemToolsHealth,
  runRAGPlayground,
  triggerCorpusSync,
} from '../api/admin'
import { Department, getDepartments } from '../api/departments'

export const SystemToolsPanel: React.FC = () => {
  // Health State
  const [health, setHealth] = useState<SystemHealthData | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)

  // Corpus Sync State
  const [syncLoading, setSyncLoading] = useState(false)
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  // Playground State
  const [query, setQuery] = useState('')
  const [selectedDept, setSelectedDept] = useState('all')
  const [topK, setTopK] = useState(5)
  const [playgroundLoading, setPlaygroundLoading] = useState(false)
  const [diagnostics, setDiagnostics] = useState<RAGPlaygroundResponse | null>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [expandedChunkId, setExpandedChunkId] = useState<string | null>(null)

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 4000)
  }

  const loadHealth = async () => {
    try {
      setHealthLoading(true)
      const data = await getSystemToolsHealth()
      setHealth(data)
    } catch (err: any) {
      showToast(err.message || 'Failed to ping system health', 'error')
    } finally {
      setHealthLoading(false)
    }
  }

  useEffect(() => {
    loadHealth()
    getDepartments().then(setDepartments).catch(() => {})
  }, [])

  const handleRunPlayground = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || playgroundLoading) return
    try {
      setPlaygroundLoading(true)
      const res = await runRAGPlayground(query, selectedDept === 'all' ? undefined : selectedDept, topK)
      setDiagnostics(res)
    } catch (err: any) {
      showToast(err.message || 'Diagnostic search failed', 'error')
    } finally {
      setPlaygroundLoading(false)
    }
  }

  const handleSyncCorpus = async () => {
    try {
      setSyncLoading(true)
      const res = await triggerCorpusSync()
      showToast(res.message || 'Corpus sync initiated via Celery worker.')
      await loadHealth()
    } catch (err: any) {
      showToast(err.message || 'Failed to trigger corpus sync', 'error')
    } finally {
      setSyncLoading(false)
    }
  }

  return (
    <div className="space-y-6 font-['Inter',sans-serif]">
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

      {/* Header Banner */}
      <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-[#18181b]">System Tools & Diagnostics</h2>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-neutral-100 text-neutral-800 px-2 py-0.5 rounded-md border border-neutral-200">
              Operations & Sandbox
            </span>
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Evaluate retrieval scoring, inspect vector database health, and trigger manual corpus synchronizations.
          </p>
        </div>

        <button
          onClick={loadHealth}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-sm cursor-pointer"
        >
          <RotateCw className={`w-3.5 h-3.5 ${healthLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Status</span>
        </button>
      </div>

      {/* Infrastructure & Vector Health Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">PostgreSQL Latency</span>
            <Database className="w-4 h-4 text-neutral-700" />
          </div>
          <div className="text-2xl font-bold text-[#18181b]">{health?.db_ping_ms ?? '...'} ms</div>
          <p className="text-[11px] text-emerald-600 font-medium mt-1">Live asyncpg connection ping</p>
        </div>

        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">pgvector Extension</span>
            <Cpu className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-[#18181b]">
            {health?.pgvector_installed ? 'Active' : 'Missing'}
          </div>
          <p className="text-[11px] text-neutral-500 mt-1">1024-dim cosine HNSW index</p>
        </div>

        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Knowledge Base</span>
            <Layers className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-2xl font-bold text-[#18181b]">{health?.total_chunks ?? 0} Chunks</div>
          <p className="text-[11px] text-neutral-500 mt-1">{health?.total_documents ?? 0} active documents</p>
        </div>

        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-neutral-500 mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Corpus Sync</span>
              <RefreshCw className="w-4 h-4 text-indigo-600" />
            </div>
            <div className="text-sm font-semibold text-[#18181b]">{health?.total_sources ?? 0} Active Sources</div>
          </div>
          <button
            onClick={handleSyncCorpus}
            disabled={syncLoading}
            className="mt-2 w-full py-1.5 px-3 bg-[#18181b] hover:bg-black text-white text-xs font-semibold rounded-xl shadow-sm transition disabled:opacity-50 cursor-pointer"
          >
            {syncLoading ? 'Triggering...' : 'Sync All Sources'}
          </button>
        </div>
      </div>

      {/* RAG Diagnostic Playground Section */}
      <div className="bg-white border border-[#e4e4e7] rounded-2xl p-5 sm:p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-[#f0f0f2]">
          <div>
            <h3 className="text-sm font-bold text-[#18181b] flex items-center gap-2">
              <Wrench className="w-4 h-4 text-neutral-600" />
              <span>RAG Retrieval & Confidence Gate Sandbox</span>
            </h3>
            <p className="text-xs text-neutral-500 mt-0.5">
              Simulate student questions in isolation to inspect raw vector similarity, BM25 rank, RRF, and cross-encoder scores.
            </p>
          </div>
        </div>

        {/* Search Query Form */}
        <form onSubmit={handleRunPlayground} className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[260px]">
            <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Enter test query (e.g. When is the 5th sem mercy test?)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs text-neutral-900 placeholder-neutral-400 focus:outline-none focus:border-neutral-900"
            />
          </div>

          <div className="flex items-center gap-1 text-xs">
            <span className="text-neutral-500 font-medium">Department:</span>
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="px-2.5 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer max-w-[170px] truncate"
            >
              <option value="all">All Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.name}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-1 text-xs">
            <span className="text-neutral-500 font-medium">Top-K:</span>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="px-2.5 py-2 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer"
            >
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={!query.trim() || playgroundLoading}
            className="px-4 py-2 bg-[#18181b] hover:bg-black text-white text-xs font-semibold rounded-xl shadow-sm transition disabled:opacity-40 cursor-pointer flex items-center gap-1.5"
          >
            {playgroundLoading && <RotateCw className="w-3.5 h-3.5 animate-spin" />}
            <span>{playgroundLoading ? 'Evaluating...' : 'Run Diagnostics'}</span>
          </button>
        </form>

        {/* Diagnostics Results */}
        {diagnostics && (
          <div className="space-y-4 pt-2 border-t border-[#f0f0f2] animate-in fade-in">
            {/* Summary Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#f8f9fa] p-3.5 rounded-xl border border-[#e4e4e7] text-xs">
              <div>
                <span className="text-[10px] text-neutral-500 uppercase tracking-wider block font-semibold">
                  Gate Result
                </span>
                <span className="font-bold flex items-center gap-1 mt-0.5">
                  {diagnostics.passed_gate ? (
                    <span className="text-emerald-700 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      Passed Gate
                    </span>
                  ) : (
                    <span className="text-amber-700 flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      Fallback Triggered
                    </span>
                  )}
                </span>
              </div>

              <div>
                <span className="text-[10px] text-neutral-500 uppercase tracking-wider block font-semibold">
                  Confidence
                </span>
                <span className="font-bold text-neutral-900 mt-0.5 block uppercase text-[11px]">
                  {diagnostics.confidence_level} ({diagnostics.confidence_score.toFixed(3)})
                </span>
              </div>

              <div>
                <span className="text-[10px] text-neutral-500 uppercase tracking-wider block font-semibold">
                  Latency
                </span>
                <span className="font-bold text-neutral-900 mt-0.5 block font-mono">
                  {diagnostics.execution_time_ms} ms
                </span>
              </div>

              <div>
                <span className="text-[10px] text-neutral-500 uppercase tracking-wider block font-semibold">
                  Candidates Evaluated
                </span>
                <span className="font-bold text-neutral-900 mt-0.5 block">
                  {diagnostics.chunks.length} Chunks
                </span>
              </div>
            </div>

            {/* Candidate Chunks Table */}
            <div className="border border-[#e4e4e7] rounded-xl overflow-hidden text-xs">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#f8f9fa] border-b border-[#e4e4e7] text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                    <th className="py-2.5 px-3 w-12 text-center">Rank</th>
                    <th className="py-2.5 px-3">Notice Title & Snippet</th>
                    <th className="py-2.5 px-3 text-center w-24">Vector Cos</th>
                    <th className="py-2.5 px-3 text-center w-24">BM25 Rank</th>
                    <th className="py-2.5 px-3 text-center w-24">RRF Score</th>
                    <th className="py-2.5 px-3 text-center w-28">Rerank Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#ebecee]">
                  {diagnostics.chunks.map((ch) => {
                    const isExpanded = expandedChunkId === ch.chunk_id
                    return (
                      <React.Fragment key={ch.chunk_id}>
                        <tr
                          onClick={() => setExpandedChunkId(isExpanded ? null : ch.chunk_id)}
                          className="hover:bg-[#f8f9fa] transition cursor-pointer"
                        >
                          <td className="py-2.5 px-3 text-center font-bold text-neutral-900">
                            #{ch.rank}
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="font-semibold text-neutral-900 line-clamp-1">{ch.title}</div>
                            <div className="text-neutral-500 text-[11px] line-clamp-1 mt-0.5">
                              {ch.content_snippet}
                            </div>
                          </td>
                          <td className="py-2.5 px-3 text-center font-mono text-neutral-700">
                            {typeof ch.vector_score === 'number' ? ch.vector_score.toFixed(3) : 'N/A'}
                          </td>
                          <td className="py-2.5 px-3 text-center font-mono text-neutral-700">
                            {typeof ch.keyword_score === 'number' ? ch.keyword_score.toFixed(3) : 'N/A'}
                          </td>
                          <td className="py-2.5 px-3 text-center font-mono text-neutral-800 font-semibold">
                            {ch.rrf_score.toFixed(3)}
                          </td>
                          <td className="py-2.5 px-3 text-center font-mono font-bold text-emerald-700">
                            {typeof ch.rerank_score === 'number' ? ch.rerank_score.toFixed(3) : 'N/A'}
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="bg-neutral-50/80">
                            <td colSpan={6} className="p-4 border-b border-neutral-200 space-y-2">
                              <div className="flex items-center justify-between text-[11px] text-neutral-500">
                                <span>Chunk ID: {ch.chunk_id}</span>
                                <span>Department: {ch.department || 'General'}</span>
                              </div>
                              <p className="font-mono text-[11px] text-neutral-800 whitespace-pre-wrap leading-relaxed bg-white p-3 rounded-lg border border-neutral-200">
                                {ch.content_snippet}
                              </p>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
