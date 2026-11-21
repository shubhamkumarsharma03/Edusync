import React, { useState, useEffect } from 'react'
import {
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  ShieldCheck,
  HelpCircle,
  FileText,
  RotateCw,
  TrendingUp,
  Download,
  ChevronDown,
  ChevronUp,
  Target,
} from 'lucide-react'
import { AnalyticsData, getAdminAnalytics, getExportAnalyticsCsvUrl } from '../api/admin'

export const AnalyticsPanel: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [queryFilter, setQueryFilter] = useState('all')
  const [expandedQueryId, setExpandedQueryId] = useState<string | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      const data = await getAdminAnalytics(queryFilter)
      setAnalytics(data)
    } catch (err) {
      console.error('Failed to load admin analytics:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [queryFilter])

  if (loading && !analytics) {
    return (
      <div className="py-24 text-center text-neutral-500 font-['Inter',sans-serif]">
        <RotateCw className="w-6 h-6 animate-spin mx-auto text-neutral-400 mb-2" />
        <span className="text-sm">Aggregating query volume and satisfaction metrics...</span>
      </div>
    )
  }

  const stats = analytics?.feedback_stats || {
    up_count: 0,
    down_count: 0,
    unrated_count: 0,
    positive_feedback_rate: 100,
  }

  const groundedRate = analytics ? Math.max(0, 100 - analytics.fallback_rate) : 100

  return (
    <div className="space-y-6 font-['Inter',sans-serif]">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#f0f0f2]">
        <div>
          <h2 className="text-lg font-bold text-[#18181b]">System Performance & Analytics</h2>
          <p className="text-xs text-neutral-500 mt-0.5">
            Real-time query metrics, student satisfaction breakdown, and knowledge base coverage.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Export CSV Button */}
          <a
            href={getExportAnalyticsCsvUrl()}
            download="edusync_queries_export.csv"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-sm cursor-pointer"
            title="Download full query history as CSV"
          >
            <Download className="w-3.5 h-3.5 text-neutral-600" />
            <span>Export CSV</span>
          </a>

          {/* Refresh Button */}
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-sm cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
        {/* Total Queries */}
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Total Queries</span>
            <MessageSquare className="w-4 h-4 text-neutral-700" />
          </div>
          <div className="text-2xl font-bold text-[#18181b]">{analytics?.total_queries || 0}</div>
          <p className="text-[11px] text-neutral-500 mt-1">Student questions answered</p>
        </div>

        {/* Grounded Precision Rate */}
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Grounded Answers</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-[#18181b]">{groundedRate.toFixed(1)}%</div>
          <p className="text-[11px] text-neutral-500 mt-1">
            {analytics?.fallback_rate.toFixed(1)}% abstained (fallback)
          </p>
        </div>

        {/* Student Satisfaction */}
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Satisfaction</span>
            <ThumbsUp className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-[#18181b]">{stats.positive_feedback_rate}%</div>
          <p className="text-[11px] text-neutral-500 mt-1">
            {stats.up_count} positive &bull; {stats.down_count} negative
          </p>
        </div>

        {/* Ingestion Corpus */}
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Knowledge Base</span>
            <FileText className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-2xl font-bold text-[#18181b]">{analytics?.total_documents || 0} docs</div>
          <p className="text-[11px] text-neutral-500 mt-1">
            {analytics?.total_chunks || 0} dense vector chunks
          </p>
        </div>
      </div>

      {/* Retrieval Confidence Distribution Bar Card */}
      {analytics?.confidence_distribution && (
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-neutral-500" />
                <span>Retrieval Confidence Distribution</span>
              </h3>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                Production threshold gating (&ge;0.65 high precision, 0.40 - 0.65 moderate, &lt;0.40 strict fallback abstention)
              </p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                High ({analytics.confidence_distribution.high_count}) {analytics.confidence_distribution.high_percentage}%
              </span>
              <span className="flex items-center gap-1 text-amber-700 font-semibold">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                Medium ({analytics.confidence_distribution.medium_count}) {analytics.confidence_distribution.medium_percentage}%
              </span>
              <span className="flex items-center gap-1 text-rose-700 font-semibold">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                Fallback ({analytics.confidence_distribution.low_count}) {analytics.confidence_distribution.low_percentage}%
              </span>
            </div>
          </div>

          {/* Segmented Progress Bar */}
          <div className="w-full h-3 bg-neutral-100 rounded-full overflow-hidden flex">
            <div
              style={{ width: `${analytics.confidence_distribution.high_percentage}%` }}
              className="bg-emerald-500 transition-all duration-500 h-full"
              title={`High Confidence: ${analytics.confidence_distribution.high_percentage}%`}
            />
            <div
              style={{ width: `${analytics.confidence_distribution.medium_percentage}%` }}
              className="bg-amber-500 transition-all duration-500 h-full"
              title={`Medium Confidence: ${analytics.confidence_distribution.medium_percentage}%`}
            />
            <div
              style={{ width: `${analytics.confidence_distribution.low_percentage}%` }}
              className="bg-rose-500 transition-all duration-500 h-full"
              title={`Fallback Abstentions: ${analytics.confidence_distribution.low_percentage}%`}
            />
          </div>
        </div>
      )}

      {/* Two Column Layout: Feedback Breakdown + Top Fallback Questions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Feedback Breakdown */}
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider">
              Student Feedback Breakdown
            </h3>
            <span className="text-xs text-neutral-400">Total Rated: {stats.up_count + stats.down_count}</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between text-xs font-medium mb-1">
                <span className="flex items-center gap-1.5 text-neutral-700">
                  <ThumbsUp className="w-3.5 h-3.5 text-emerald-600" /> Positive
                </span>
                <span className="text-neutral-700 font-semibold">{stats.up_count}</span>
              </div>
              <div className="w-full bg-neutral-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${
                      stats.up_count + stats.down_count > 0
                        ? (stats.up_count / (stats.up_count + stats.down_count)) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-xs font-medium mb-1">
                <span className="flex items-center gap-1.5 text-neutral-700">
                  <ThumbsDown className="w-3.5 h-3.5 text-rose-600" /> Negative
                </span>
                <span className="text-neutral-700 font-semibold">{stats.down_count}</span>
              </div>
              <div className="w-full bg-neutral-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-rose-500 h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${
                      stats.up_count + stats.down_count > 0
                        ? (stats.down_count / (stats.up_count + stats.down_count)) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Top Fallback / Unanswered Questions */}
        <div className="bg-white border border-[#e4e4e7] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5">
              <HelpCircle className="w-3.5 h-3.5 text-neutral-500" />
              <span>Unanswered Questions (Content Gaps)</span>
            </h3>
            <span className="text-[11px] text-neutral-400">Low confidence fallbacks</span>
          </div>

          {!analytics?.top_fallback_questions || analytics.top_fallback_questions.length === 0 ? (
            <p className="text-xs text-neutral-400 py-6 text-center">
              No fallback queries recorded yet. EduSync has answered queries with verified evidence.
            </p>
          ) : (
            <ul className="divide-y divide-neutral-100 text-xs">
              {analytics.top_fallback_questions.map((q, idx) => (
                <li key={idx} className="py-2.5 flex items-start gap-2 text-neutral-800">
                  <span className="w-4 h-4 rounded-full bg-neutral-100 text-neutral-700 text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5 border border-neutral-200">
                    {idx + 1}
                  </span>
                  <span className="font-medium">{q}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Recent Queries Log Table with Filter */}
      <div className="bg-white border border-[#e4e4e7] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-neutral-500" />
            <span>Recent Student Queries Log</span>
          </h3>

          {/* Filter Dropdown */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-neutral-500 font-medium">Filter:</span>
            <select
              value={queryFilter}
              onChange={(e) => setQueryFilter(e.target.value)}
              className="px-2.5 py-1 bg-[#f8f9fa] border border-[#e4e4e7] rounded-lg text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer"
            >
              <option value="all">All Queries</option>
              <option value="positive">Positive Feedback</option>
              <option value="negative">Negative Feedback</option>
              <option value="unrated">Unrated</option>
              <option value="fallback">Fallbacks (&le;0.40)</option>
            </select>
          </div>
        </div>

        {!analytics?.recent_queries || analytics.recent_queries.length === 0 ? (
          <p className="text-xs text-neutral-400 py-6 text-center">
            No queries matching filter "{queryFilter}".
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#f8f9fa] border-b border-[#e4e4e7] text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Student Question</th>
                  <th className="py-2.5 px-3">Answer Summary</th>
                  <th className="py-2.5 px-3 text-center">Confidence</th>
                  <th className="py-2.5 px-3 text-center">Rating</th>
                  <th className="py-2.5 px-3 text-center w-12">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ebecee]">
                {analytics.recent_queries.map((q) => {
                  const isExpanded = expandedQueryId === q.id
                  return (
                    <React.Fragment key={q.id}>
                      <tr
                        onClick={() => setExpandedQueryId(isExpanded ? null : q.id)}
                        className="hover:bg-[#f8f9fa] transition cursor-pointer"
                      >
                        <td className="py-2.5 px-3 text-neutral-500 whitespace-nowrap">
                          {new Date(q.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                        <td className="py-2.5 px-3 font-medium text-neutral-900 max-w-xs truncate">
                          {q.question}
                        </td>
                        <td className="py-2.5 px-3 text-neutral-600 max-w-sm truncate">
                          {q.answer_preview || 'N/A'}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span className="px-2 py-0.5 bg-neutral-100 text-neutral-800 rounded font-mono text-[10px] border border-neutral-200">
                            {q.confidence_score !== null && q.confidence_score !== undefined
                              ? Number(q.confidence_score).toFixed(2)
                              : 'N/A'}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {q.feedback === 'up' ? (
                            <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
                              <ThumbsUp className="w-3 h-3 text-emerald-600" /> Positive
                            </span>
                          ) : q.feedback === 'down' ? (
                            <span className="inline-flex items-center gap-1 text-rose-700 font-medium">
                              <ThumbsDown className="w-3 h-3 text-rose-600" /> Negative
                            </span>
                          ) : (
                            <span className="text-neutral-400">-</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-center text-neutral-400">
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5 mx-auto" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5 mx-auto" />
                          )}
                        </td>
                      </tr>

                      {/* Expanded Query Row */}
                      {isExpanded && (
                        <tr className="bg-neutral-50/70">
                          <td colSpan={6} className="py-3 px-4 space-y-2 border-b border-neutral-200">
                            <div>
                              <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 block mb-0.5">
                                Full Question:
                              </span>
                              <p className="font-semibold text-neutral-900 text-xs">{q.question}</p>
                            </div>
                            <div>
                              <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 block mb-0.5">
                                Full Answer Preview:
                              </span>
                              <p className="text-neutral-700 text-xs whitespace-pre-wrap leading-relaxed">
                                {q.answer_preview || 'No answer generated.'}
                              </p>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
