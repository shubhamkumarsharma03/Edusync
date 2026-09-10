/**
 * EduSync Admin Departments API Client
 */

export interface Department {
  id: number
  name: string
  code?: string | null
  category: string
  slug?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DepartmentCreatePayload {
  id?: number
  name: string
  code?: string
  category?: string
  slug?: string
  is_active?: boolean
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function getDepartments(category?: string): Promise<Department[]> {
  const url = new URL(`${API_BASE_URL}/admin/departments`)
  if (category) {
    url.searchParams.append('category', category)
  }
  const res = await fetch(url.toString(), {
    headers: { 'Accept': 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Failed to fetch departments: ${res.status}`)
  }
  return res.json()
}

export async function createDepartment(payload: DepartmentCreatePayload): Promise<Department> {
  const res = await fetch(`${API_BASE_URL}/admin/departments`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(errorData.detail || `Failed to create department: ${res.status}`)
  }
  return res.json()
}

export async function updateDepartment(
  id: number,
  payload: Partial<DepartmentCreatePayload>
): Promise<Department> {
  const res = await fetch(`${API_BASE_URL}/admin/departments/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`Failed to update department: ${res.status}`)
  }
  return res.json()
}

export async function deleteDepartment(id: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/admin/departments/${id}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    throw new Error(`Failed to delete department: ${res.status}`)
  }
}
