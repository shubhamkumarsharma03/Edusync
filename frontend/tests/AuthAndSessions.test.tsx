import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  registerStudent,
  loginStudent,
  fetchCurrentStudent,
  getAuthToken,
  setAuthToken,
  clearAuthToken,
} from '../src/api/auth'
import { fetchChatSessions, createChatSession } from '../src/api/chat'
import {
  syncConversationsWithServer,
  loadLocalConversations,
  saveLocalConversations,
  Conversation,
} from '../src/utils/chatStorage'

const storageMap = new Map<string, string>()
const mockLocalStorage = {
  getItem: (key: string) => storageMap.get(key) || null,
  setItem: (key: string, val: string) => storageMap.set(key, String(val)),
  removeItem: (key: string) => storageMap.delete(key),
  clear: () => storageMap.clear(),
}
;(globalThis as any).localStorage = mockLocalStorage

describe('Student Authentication & Multi-Student Database Partitioning', () => {
  beforeEach(() => {
    storageMap.clear()
    vi.restoreAllMocks()
  })

  it('registerStudent sends registration payload and stores JWT token', async () => {
    const mockAuthRes = {
      access_token: 'fake-jwt-token-123',
      token_type: 'bearer',
      student: {
        id: 'uuid-1111',
        college_roll_no: '21ECA050',
        email: 'rahul@ecajmer.ac.in',
        full_name: 'Rahul Sharma',
        branch: 'Computer Science & Engineering',
        semester: 6,
        degree: 'B.Tech',
        admission_year: 2021,
        role: 'student',
        created_at: new Date().toISOString(),
      },
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAuthRes,
    }) as any

    const res = await registerStudent({
      college_roll_no: '21ECA050',
      email: 'rahul@ecajmer.ac.in',
      full_name: 'Rahul Sharma',
      branch: 'Computer Science & Engineering',
      semester: 6,
      password: 'password123',
    })

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/register'),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
    )
    expect(res.access_token).toBe('fake-jwt-token-123')
    expect(getAuthToken()).toBe('fake-jwt-token-123')
    expect(res.student.college_roll_no).toBe('21ECA050')
  })

  it('loginStudent sends identifier and password, saving JWT', async () => {
    const mockAuthRes = {
      access_token: 'fake-jwt-token-456',
      token_type: 'bearer',
      student: {
        id: 'uuid-2222',
        college_roll_no: '22ECA080',
        email: 'priya@ecajmer.ac.in',
        full_name: 'Priya Verma',
        branch: 'Information Technology',
        semester: 4,
        degree: 'B.Tech',
        admission_year: 2022,
        role: 'student',
        created_at: new Date().toISOString(),
      },
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAuthRes,
    }) as any

    const res = await loginStudent({
      identifier: '22ECA080',
      password: 'mypassword',
    })

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/login'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ identifier: '22ECA080', password: 'mypassword' }),
      })
    )
    expect(res.student.full_name).toBe('Priya Verma')
    expect(getAuthToken()).toBe('fake-jwt-token-456')
  })

  it('fetchCurrentStudent attaches Bearer token header', async () => {
    setAuthToken('test-bearer-token-789')

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'uuid-3333',
        college_roll_no: '21ECA099',
        email: 'student@ecajmer.ac.in',
        full_name: 'Aditya Gupta',
        branch: 'Mechanical Engineering',
        semester: 6,
        degree: 'B.Tech',
        admission_year: 2021,
        role: 'student',
        created_at: new Date().toISOString(),
      }),
    }) as any

    const student = await fetchCurrentStudent()
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/me'),
      expect.objectContaining({
        headers: {
          Authorization: 'Bearer test-bearer-token-789',
        },
      })
    )
    expect(student?.college_roll_no).toBe('21ECA099')
  })

  it('clearAuthToken successfully purges token', () => {
    setAuthToken('token-to-delete')
    expect(getAuthToken()).toBe('token-to-delete')
    clearAuthToken()
    expect(getAuthToken()).toBeNull()
  })

  it('fetchChatSessions passes student_id and auth headers', async () => {
    setAuthToken('token-xyz')
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: 'sess-1',
          student_id: '21ECA050',
          title: 'Exam schedule query',
          is_pinned: true,
          is_archived: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          message_count: 2,
        },
      ],
    }) as any

    const sessions = await fetchChatSessions('21ECA050')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/chat/sessions?student_id=21ECA050'),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer token-xyz',
        }),
      })
    )
    expect(sessions.length).toBe(1)
    expect(sessions[0].is_pinned).toBe(true)
  })

  it('syncConversationsWithServer enforces zero dummy data by not pushing empty chats', async () => {
    // Mock server returning empty list
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }) as any

    // Local conversation with NO user messages (empty draft)
    const emptyConv: Conversation = {
      id: 'draft-1',
      student_id: '21ECA050',
      title: 'New Chat',
      is_pinned: false,
      is_archived: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [],
    }

    const synced = await syncConversationsWithServer([emptyConv], '21ECA050')
    // Should filter out empty dummy chats, returning empty array
    expect(synced.length).toBe(0)
  })

  it('isolates chat history and storage across different student accounts', () => {
    const student1 = '21ECA001'
    const student2 = '22ECA045'

    const conv1: Conversation = {
      id: 'conv-101',
      student_id: student1,
      title: 'CSE Midterms',
      is_pinned: true,
      is_archived: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [{ id: 'm1', sender: 'user', text: 'When is mid-term?' }],
    }

    const conv2: Conversation = {
      id: 'conv-202',
      student_id: student2,
      title: 'Fee Payment',
      is_pinned: false,
      is_archived: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [{ id: 'm2', sender: 'user', text: 'Where to submit fees?' }],
    }

    saveLocalConversations([conv1], student1)
    saveLocalConversations([conv2], student2)

    const loaded1 = loadLocalConversations(student1)
    const loaded2 = loadLocalConversations(student2)

    expect(loaded1.length).toBe(1)
    expect(loaded1[0].title).toBe('CSE Midterms')

    expect(loaded2.length).toBe(1)
    expect(loaded2[0].title).toBe('Fee Payment')
  })
})
