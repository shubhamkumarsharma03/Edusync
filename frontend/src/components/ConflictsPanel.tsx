import React, { useState, useEffect } from 'react'
import {
  CheckCircle2,
  ExternalLink,
  ShieldAlert,
  RotateCw,
  RotateCcw,
  SplitSquareVertical,
  X,
} from 'lucide-react'
import {
  ConflictItem,
  ConflictCompareResponse,
  getAdminConflicts,
  resolveConflict,
  reopenConflict,
  compareConflictDocuments,
} from '../api/admin'
import { Department, getDepartments } from '../api/departments'

export const ConflictsPanel: React.FC = () => {
  const [conflicts, setConflicts] = useState<ConflictItem[]>([])
  const [loading, setLoading] = useState(true)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [customNotes, setCustomNotes] = useState<Record<string, string>>({})
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  // Department Filter
  const [departments, setDepartments] = useState<Department[]>([])
  const [selectedDept, setSelectedDept] = useState('all')

  // Compare Modal State
  const [comparingConflict, setComparingConflict] = useState<ConflictCompareResponse | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 4000)
  }

  const loadConflicts = async () => {
    try {
      setLoading(true)
      const data = await getAdminConflicts()
      setConflicts(data)
    } catch (err: any) {
      showToast(err.message || 'Failed to load conflicts', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadConflicts()
    getDepartments().then(setDepartments).catch(() => {})
  }, [])

  const handleResolve = async (
    conflictId: string,
    authoritativeDocId?: string,
    resolutionType: 'supersede' | 'non_conflicting' | 'archive_both' | 'dismiss' = 'supersede'
  ) => {
    try {
      setResolvingId(conflictId)
      const note = customNotes[conflictId]
      const res = await resolveConflict(conflictId, authoritativeDocId, resolutionType, note)
      showToast(`Conflict resolved: ${res.resolution_type}`)
      await loadConflicts()
    } catch (err: any) {
      showToast(err.message || 'Failed to resolve conflict', 'error')
    } finally {
      setResolvingId(null)
    }
  }

  const handleReopen = async (conflictId: string) => {
    try {
      setResolvingId(conflictId)
      await reopenConflict(conflictId)
      showToast('Conflict reopened for administrative review.')
      await loadConflicts()
    } catch (err: any) {
      showToast(err.message || 'Failed to reopen conflict', 'error')
    } finally {
      setResolvingId(null)
    }
  }

  const handleOpenCompare = async (conflictId: string) => {
    try {
      setCompareLoading(true)
      const comp = await compareConflictDocuments(conflictId)
      setComparingConflict(comp)
    } catch (err: any) {
      showToast(err.message || 'Failed to load document text comparison', 'error')
    } finally {
      setCompareLoading(false)
    }
  }

  const filteredConflicts = conflicts.filter((c) => {
    if (selectedDept === 'all') return true
    return c.documents.some((d) => d.department_name === selectedDept)
  })

  const unresolvedConflicts = filteredConflicts.filter((c) => !c.resolved_at)
  const resolvedConflicts = filteredConflicts.filter((c) => c.resolved_at)

  return (
    <div className="space-y-6 font-['Inter',sans-serif]">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`p-3.5 rounded-xl text-xs font-semibold flex items-center justify-between shadow-sm ${
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
            <h2 className="text-lg font-bold text-[#18181b]">Institutional Conflict Resolution</h2>
            <span
              className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
                unresolvedConflicts.length > 0
                  ? 'bg-amber-50 text-amber-800 border border-amber-200'
                  : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              }`}
            >
              {unresolvedConflicts.length} Unresolved
            </span>
          </div>
          <p className="text-xs text-neutral-500 mt-0.5">
            Documents flagged in conflicts are strictly excluded from student retrieval until verified by an administrator.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Department Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-neutral-500 font-medium">Department:</span>
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="px-2.5 py-1.5 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl text-xs font-medium text-neutral-800 focus:outline-none cursor-pointer max-w-[200px] truncate"
            >
              <option value="all">All Departments</option>
              {departments.map((dept) => (
                <option key={dept.id} value={dept.name}>
                  {dept.name}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={loadConflicts}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#f4f4f5] hover:bg-[#e4e4e7] text-neutral-700 rounded-xl text-xs font-semibold border border-[#d4d4d8] transition shadow-sm cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Unresolved Conflicts Section */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5">
          <ShieldAlert className="w-3.5 h-3.5 text-neutral-500" />
          <span>Pending Action Required ({unresolvedConflicts.length})</span>
        </h3>

        {unresolvedConflicts.length === 0 ? (
          <div className="bg-white border border-[#e4e4e7] rounded-2xl p-8 text-center text-neutral-600 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-1">
            <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
            <div className="font-semibold text-sm text-[#18181b]">No Active Document Conflicts</div>
            <p className="text-xs text-neutral-500 max-w-md mx-auto">
              All active circulars in the college corpus are consistent and participating in student retrieval.
            </p>
          </div>
        ) : (
          unresolvedConflicts.map((c, idx) => (
            <div
              key={c.id}
              className="bg-white border border-[#e4e4e7] rounded-2xl p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] space-y-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#f0f0f2] text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-neutral-900 bg-neutral-100 border border-neutral-200 px-2 py-0.5 rounded-md text-[11px]">
                    Conflict #{idx + 1}
                  </span>
                  <span className="text-neutral-400 font-mono text-[11px] truncate max-w-xs">
                    {c.id}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-neutral-500 text-[11px]">
                    Detected {new Date(c.detected_at).toLocaleDateString()}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleOpenCompare(c.id)}
                    disabled={compareLoading}
                    className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold text-neutral-700 bg-[#f4f4f5] hover:bg-[#e4e4e7] border border-[#d4d4d8] rounded-md transition shadow-2xs cursor-pointer"
                  >
                    <SplitSquareVertical className="w-3 h-3 text-neutral-500" />
                    <span>Compare Text</span>
                  </button>
                </div>
              </div>

              {/* Conflicting Documents Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {c.documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-4 bg-[#f8f9fa] border border-[#e4e4e7] rounded-xl space-y-3 relative hover:border-neutral-300 transition"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-neutral-800 bg-white border border-neutral-200 px-2 py-0.5 rounded">
                        {doc.notice_sno || 'No S.No'}
                      </span>
                      <span className="text-xs text-neutral-500">{doc.notice_date || 'No Date'}</span>
                    </div>

                    <div>
                      <h4 className="font-semibold text-[#18181b] text-sm line-clamp-2">
                        {doc.title}
                      </h4>
                      <p className="text-[11px] text-neutral-500 truncate mt-1">
                        {doc.department_name || 'General'} &bull; {doc.source_url}
                      </p>
                    </div>

                    <div className="pt-2 flex items-center justify-between gap-2">
                      <a
                        href={doc.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                      >
                        <span>View Notice PDF</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>

                      <button
                        type="button"
                        onClick={() => handleResolve(c.id, doc.id, 'supersede')}
                        disabled={resolvingId === c.id}
                        className="px-3 py-1.5 bg-[#18181b] hover:bg-black text-white rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-40 cursor-pointer"
                        title="Mark this document authoritative and archive the others"
                      >
                        Mark Authoritative
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Resolution Action Row */}
              <div className="pt-2 flex flex-wrap items-center justify-between gap-3 bg-[#f8f9fa] p-3 rounded-xl border border-[#e4e4e7]">
                <div className="flex-1 min-w-[200px]">
                  <input
                    type="text"
                    placeholder="Optional audit notes (e.g. verified distinct cohorts or both outdated)..."
                    value={customNotes[c.id] || ''}
                    onChange={(e) =>
                      setCustomNotes((prev) => ({ ...prev, [c.id]: e.target.value }))
                    }
                    className="w-full px-3 py-1.5 bg-white border border-[#e4e4e7] rounded-lg text-xs text-neutral-900 focus:outline-none focus:border-neutral-900 placeholder-neutral-400"
                  />
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {/* Mark Both Non-Conflicting */}
                  <button
                    type="button"
                    onClick={() => handleResolve(c.id, undefined, 'non_conflicting')}
                    disabled={resolvingId === c.id}
                    className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition shadow-sm disabled:opacity-40 cursor-pointer"
                    title="Both documents apply to distinct cohorts (e.g. Sem 3 vs Sem 7)"
                  >
                    Mark Both Non-Conflicting
                  </button>

                  {/* Drop / Archive Both Documents */}
                  <button
                    type="button"
                    onClick={() => handleResolve(c.id, undefined, 'archive_both')}
                    disabled={resolvingId === c.id}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold transition shadow-sm disabled:opacity-40 cursor-pointer"
                    title="Both documents are wrong, cancelled, or obsolete - drop and archive both"
                  >
                    Drop Both Documents
                  </button>

                  {/* Dismiss Conflict */}
                  <button
                    type="button"
                    onClick={() => handleResolve(c.id, undefined, 'dismiss')}
                    disabled={resolvingId === c.id}
                    className="px-3 py-1.5 bg-white hover:bg-neutral-100 text-neutral-700 border border-[#d4d4d8] rounded-lg text-xs font-semibold transition shadow-sm disabled:opacity-40 cursor-pointer"
                  >
                    Dismiss Conflict
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Resolved Conflicts Audit Trail */}
      {resolvedConflicts.length > 0 && (
        <div className="space-y-4 pt-4">
          <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Resolution Audit History ({resolvedConflicts.length})</span>
          </h3>

          <div className="bg-white border border-[#e4e4e7] rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04)] divide-y divide-[#ebecee] overflow-hidden text-xs">
            {resolvedConflicts.map((c) => (
              <div key={c.id} className="p-4 space-y-2 hover:bg-[#f8f9fa] transition">
                <div className="flex flex-wrap items-center justify-between gap-2 text-neutral-500 text-[11px]">
                  <div>
                    Resolved by <span className="font-semibold text-neutral-800">{c.resolved_by || 'admin'}</span>{' '}
                    on {c.resolved_at ? new Date(c.resolved_at).toLocaleDateString() : 'N/A'}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[10px] font-bold uppercase">
                      Resolved
                    </span>
                    <button
                      type="button"
                      onClick={() => handleReopen(c.id)}
                      disabled={resolvingId === c.id}
                      className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold text-neutral-700 bg-white hover:bg-neutral-100 border border-[#d4d4d8] rounded transition shadow-2xs cursor-pointer"
                      title="Reopen this conflict and return documents to review"
                    >
                      <RotateCcw className="w-2.5 h-2.5 text-neutral-500" />
                      <span>Reopen</span>
                    </button>
                  </div>
                </div>

                <p className="text-neutral-800 font-medium">
                  {c.resolution_note || 'Admin resolved conflict.'}
                </p>

                <div className="flex items-center gap-2 flex-wrap text-[11px] text-neutral-500">
                  <span>Documents:</span>
                  {c.documents.map((d) => (
                    <span
                      key={d.id}
                      className="px-2 py-0.5 bg-neutral-100 rounded text-neutral-700 border border-neutral-200"
                    >
                      {d.notice_sno || d.title.slice(0, 30)} ({d.status})
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Side-by-Side Text Comparison Modal */}
      {comparingConflict && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#e4e4e7] max-w-5xl w-full max-h-[85vh] flex flex-col shadow-xl overflow-hidden animate-in fade-in zoom-in-95">
            {/* Modal Header */}
            <div className="px-5 py-4 border-b border-[#f0f0f2] flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-[#18181b] flex items-center gap-2">
                  <SplitSquareVertical className="w-4 h-4 text-neutral-600" />
                  <span>Side-by-Side Conflict Content Inspection</span>
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5 font-mono">
                  Conflict ID: {comparingConflict.conflict_id}
                </p>
              </div>
              <button
                onClick={() => setComparingConflict(null)}
                className="p-1 text-neutral-400 hover:text-neutral-800 rounded-lg hover:bg-neutral-100 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Content - Side by Side Comparison Grid */}
            <div className="p-5 overflow-y-auto flex-1 grid grid-cols-1 md:grid-cols-2 gap-4 bg-[#f8f9fa]">
              {comparingConflict.documents.map((doc, dIdx) => (
                <div
                  key={doc.id}
                  className="bg-white border border-[#e4e4e7] rounded-xl p-4 flex flex-col space-y-3 shadow-2xs"
                >
                  <div className="pb-2 border-b border-[#f0f0f2]">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-neutral-900 bg-neutral-100 px-2 py-0.5 rounded font-mono text-[11px]">
                        Doc #{dIdx + 1}: {doc.notice_sno || 'No S.No'}
                      </span>
                      <span className="text-[11px] text-neutral-500">{doc.notice_date || 'No Date'}</span>
                    </div>
                    <h4 className="font-semibold text-xs text-[#18181b] line-clamp-2 mt-1">
                      {doc.title}
                    </h4>
                    <span className="text-[10px] text-neutral-500 block truncate mt-0.5">
                      {doc.department_name || 'General'}
                    </span>
                  </div>

                  <div className="flex-1 space-y-2 overflow-y-auto max-h-[50vh]">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400 block">
                      Parsed Text Chunks ({doc.chunks.length})
                    </span>
                    {doc.chunks.length === 0 ? (
                      <p className="text-xs text-neutral-400 py-4 text-center">No chunks available for this notice.</p>
                    ) : (
                      doc.chunks.map((ch, chIdx) => (
                        <div
                          key={ch.id}
                          className="p-3 bg-[#fcfcfc] border border-neutral-200 rounded-lg text-xs space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-[10px] text-neutral-500">
                            <span className="font-semibold">Chunk #{chIdx + 1}</span>
                            <span>{ch.token_count} tokens</span>
                          </div>
                          <p className="text-neutral-800 whitespace-pre-wrap leading-relaxed font-mono text-[11px]">
                            {ch.content}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3 border-t border-[#f0f0f2] bg-white flex justify-end">
              <button
                onClick={() => setComparingConflict(null)}
                className="px-4 py-1.5 bg-neutral-900 hover:bg-black text-white text-xs font-semibold rounded-xl shadow-sm transition cursor-pointer"
              >
                Close Comparison
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
