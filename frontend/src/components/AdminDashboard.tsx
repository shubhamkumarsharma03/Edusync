import React, { useState, useEffect } from 'react'
import {
  BarChart3,
  FileText,
  AlertTriangle,
  Globe,
  MessageSquare,
  LogOut,
  Wrench,
} from 'lucide-react'
import { AdminAuthGate } from './AdminAuthGate'
import { AnalyticsPanel } from './AnalyticsPanel'
import { DocumentsTable } from './DocumentsTable'
import { ConflictsPanel } from './ConflictsPanel'
import { AdminSourcesPanel } from './AdminSourcesPanel'
import { SystemToolsPanel } from './SystemToolsPanel'
import { getAdminConflicts } from '../api/admin'

export const AdminDashboard: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return sessionStorage.getItem('edusync_admin_auth') === 'authenticated'
  })

  const [activeTab, setActiveTab] = useState<'analytics' | 'documents' | 'conflicts' | 'sources' | 'tools'>('analytics')
  const [unresolvedCount, setUnresolvedCount] = useState<number>(0)

  useEffect(() => {
    if (isAuthenticated) {
      getAdminConflicts(true)
        .then((unresolved) => setUnresolvedCount(unresolved.length))
        .catch(() => {})
    }
  }, [isAuthenticated, activeTab])

  const handleLogout = () => {
    sessionStorage.removeItem('edusync_admin_auth')
    setIsAuthenticated(false)
  }

  // 1. Basic Auth Gate Protection
  if (!isAuthenticated) {
    return <AdminAuthGate onAuthenticated={() => setIsAuthenticated(true)} />
  }

  return (
    <div className="min-h-screen bg-[#f8f9fa] text-[#18181b] font-['Inter',sans-serif] p-4 sm:p-6 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Header */}
        <header className="bg-white border border-[#e4e4e7] rounded-2xl p-4 sm:p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <img
              src="/logo-icon.png"
              alt="EduSync"
              className="w-10 h-10 rounded-xl object-contain bg-white border border-[#e4e4e7] p-1 shadow-sm"
            />
            <div>
              <h1 className="font-bold text-lg tracking-tight text-[#18181b]">
                EduSync Admin Portal
              </h1>
              <p className="text-xs text-neutral-500 mt-0.5">
                Institutional knowledge management, conflict audit, and ingestion control.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <a
              href="/"
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-neutral-700 bg-white hover:bg-neutral-100 border border-[#d4d4d8] rounded-xl transition shadow-xs"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Student Chat</span>
            </a>

            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-neutral-700 bg-white hover:bg-neutral-100 border border-[#d4d4d8] rounded-xl transition shadow-xs cursor-pointer"
              title="Lock Admin Dashboard"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Exit Admin</span>
            </button>
          </div>
        </header>

        {/* Tab Navigation Bar */}
        <div className="flex items-center gap-2 border-b border-[#e4e4e7] pb-2 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl transition cursor-pointer ${
              activeTab === 'analytics'
                ? 'bg-[#18181b] text-white shadow-sm'
                : 'bg-white text-neutral-600 hover:text-neutral-900 border border-[#e4e4e7] hover:bg-neutral-50'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>System Analytics</span>
          </button>

          <button
            onClick={() => setActiveTab('documents')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl transition cursor-pointer ${
              activeTab === 'documents'
                ? 'bg-[#18181b] text-white shadow-sm'
                : 'bg-white text-neutral-600 hover:text-neutral-900 border border-[#e4e4e7] hover:bg-neutral-50'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>All Documents</span>
          </button>

          <button
            onClick={() => setActiveTab('conflicts')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl transition cursor-pointer ${
              activeTab === 'conflicts'
                ? 'bg-[#18181b] text-white shadow-sm'
                : 'bg-white text-neutral-600 hover:text-neutral-900 border border-[#e4e4e7] hover:bg-neutral-50'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Conflict Resolution</span>
            {unresolvedCount > 0 && (
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                  activeTab === 'conflicts'
                    ? 'bg-amber-400 text-neutral-950'
                    : 'bg-amber-100 text-amber-800'
                }`}
              >
                {unresolvedCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('sources')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl transition cursor-pointer ${
              activeTab === 'sources'
                ? 'bg-[#18181b] text-white shadow-sm'
                : 'bg-white text-neutral-600 hover:text-neutral-900 border border-[#e4e4e7] hover:bg-neutral-50'
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            <span>Ingestion Sources</span>
          </button>

          <button
            onClick={() => setActiveTab('tools')}
            className={`flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl transition cursor-pointer ${
              activeTab === 'tools'
                ? 'bg-[#18181b] text-white shadow-sm'
                : 'bg-white text-neutral-600 hover:text-neutral-900 border border-[#e4e4e7] hover:bg-neutral-50'
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            <span>System Tools</span>
          </button>
        </div>

        {/* Tab Panels */}
        <div className="transition-all duration-150">
          {activeTab === 'analytics' && <AnalyticsPanel />}
          {activeTab === 'documents' && <DocumentsTable />}
          {activeTab === 'conflicts' && <ConflictsPanel />}
          {activeTab === 'sources' && (
            <div className="-mt-6">
              <AdminSourcesPanel />
            </div>
          )}
          {activeTab === 'tools' && <SystemToolsPanel />}
        </div>
      </div>
    </div>
  )
}
