import React from 'react'
import { X } from 'lucide-react'

export interface DepartmentOption {
  id: string
  name: string
  shortLabel: string
}

export const DEPARTMENTS: DepartmentOption[] = [
  { id: 'all', name: 'All Departments', shortLabel: 'All' },
  { id: 'Computer Science and Engineering', name: 'Computer Science & IT', shortLabel: 'CSE / IT' },
  { id: 'Examination Section', name: 'Examination Section', shortLabel: 'Exam' },
  { id: 'Registrar Section', name: 'Registrar Section', shortLabel: 'Registrar' },
  { id: 'Civil Engineering', name: 'Civil Engineering', shortLabel: 'Civil' },
  { id: 'Electrical Engineering', name: 'Electrical Engineering', shortLabel: 'Electrical' },
  { id: 'Mechanical Engineering', name: 'Mechanical Engineering', shortLabel: 'Mechanical' },
  { id: 'Electronics & Communication Engineering', name: 'Electronics & Comm.', shortLabel: 'ECE' },
  { id: 'Computer Applications (MCA)', name: 'Computer Applications', shortLabel: 'MCA' },
  { id: 'Management Studies (MBA)', name: 'Management Studies', shortLabel: 'MBA' },
]

interface DepartmentSelectorProps {
  selectedDept: string
  onSelectDept: (deptId: string) => void
}

export const DepartmentSelector: React.FC<DepartmentSelectorProps> = ({
  selectedDept,
  onSelectDept,
}) => {
  return (
    <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1 px-1">
      <span className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider flex-shrink-0 mr-1 hidden sm:inline">
        Scope:
      </span>

      {DEPARTMENTS.map((dept) => {
        const isSelected =
          selectedDept === dept.id || (selectedDept === '' && dept.id === 'all')
        return (
          <button
            key={dept.id}
            type="button"
            onClick={() => onSelectDept(dept.id === 'all' ? 'all' : dept.id)}
            className={`px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1 flex-shrink-0 cursor-pointer ${
              isSelected
                ? 'bg-neutral-900 text-white shadow-xs'
                : 'bg-white hover:bg-neutral-100 text-neutral-600 border border-neutral-200 hover:text-neutral-900'
            }`}
          >
            <span>{dept.shortLabel}</span>
            {isSelected && dept.id !== 'all' && (
              <span
                onClick={(e) => {
                  e.stopPropagation()
                  onSelectDept('all')
                }}
                className="hover:bg-neutral-700 rounded-full p-0.5 ml-0.5 transition"
                title="Clear filter"
              >
                <X className="w-2.5 h-2.5" />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
