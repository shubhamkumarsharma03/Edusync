import { describe, it, expect, vi } from 'vitest'
import { DEPARTMENTS } from '../src/components/DepartmentSelector'
import {
  sendChatMessage,
  sendChatFeedback,
  fetchChatSessions,
  createChatSession,
  deleteChatSession,
} from '../src/api/chat'
import {
  createNewConversation,
  loadLocalConversations,
  saveLocalConversations,
} from '../src/utils/chatStorage'

describe('Student Chat UI - Phase 5 Component & Logic Tests', () => {
  it('DEPARTMENTS list contains all required college departments', () => {
    const requiredShortLabels = ['All', 'CSE / IT', 'Exam', 'Registrar', 'Civil', 'Electrical', 'Mechanical', 'ECE', 'MCA', 'MBA']
    const labels = DEPARTMENTS.map((d) => d.shortLabel)
    for (const req of requiredShortLabels) {
      expect(labels).toContain(req)
    }
  })

  it('sendChatMessage passes department scope and returns formatted response', async () => {
    const mockResponse = {
      answer: 'Exam starts on Dec 1',
      sources: [
        {
          title: 'CSE Exam Schedule',
          url: 'https://ecajmer.ac.in/pdf',
          department: 'Computer Science and Engineering',
          last_verified: 'Verified Fresh',
          confidence_score: 0.95,
        },
      ],
      confidence: 'high',
      confidence_score: 0.95,
      is_fallback: false,
      query: 'When is CSE exam?',
      query_id: '123e4567-e89b-12d3-a456-426614174000',
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    }) as any

    const result = await sendChatMessage('When is CSE exam?', 'Computer Science and Engineering')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/chat'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          query: 'When is CSE exam?',
          department: 'Computer Science and Engineering',
          session_id: null,
          history: [],
        }),
      })
    )
    expect(result.answer).toBe('Exam starts on Dec 1')
    expect(result.is_fallback).toBe(false)
    expect(result.query_id).toBe('123e4567-e89b-12d3-a456-426614174000')
  })

  it('sendChatFeedback sends thumbs up/down rating to the backend', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', query_id: 'test-id', feedback: 'up' }),
    }) as any

    const result = await sendChatFeedback('test-id', 'up')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/chat/feedback'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          query_id: 'test-id',
          feedback: 'up',
          issue_tag: null,
          student_comment: null,
        }),
      })
    )
    expect(result.status).toBe('success')
  })

  it('chatStorage isolates conversations per student account', () => {
    const studentA = 'student_21ECA01'
    const studentB = 'student_21ECA02'

    const convA = createNewConversation(studentA, 'Exam Schedule Inquiry')
    const convB = createNewConversation(studentB, 'Fee Waiver Notice')

    saveLocalConversations([convA], studentA)
    saveLocalConversations([convB], studentB)

    const loadedA = loadLocalConversations(studentA)
    const loadedB = loadLocalConversations(studentB)

    expect(loadedA.length).toBe(1)
    expect(loadedA[0].title).toBe('Exam Schedule Inquiry')
    expect(loadedA[0].student_id).toBe(studentA)

    expect(loadedB.length).toBe(1)
    expect(loadedB[0].title).toBe('Fee Waiver Notice')
    expect(loadedB[0].student_id).toBe(studentB)
  })

  it('session API endpoints fetch, create, and delete server sessions', async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id: 's1', title: 'Test Chat', is_pinned: false, is_archived: false }],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 's2', title: 'New Chat', messages: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'success' }),
      }) as any

    const list = await fetchChatSessions('student_101')
    expect(list.length).toBe(1)
    expect(list[0].id).toBe('s1')

    const created = await createChatSession('student_101', 'New Chat')
    expect(created?.id).toBe('s2')

    const deleted = await deleteChatSession('s2')
    expect(deleted).toBe(true)
  })

  it('sendChatMessage supports guest mode without session ID', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        answer: 'Library is open 9 AM to 6 PM',
        sources: [],
        confidence: 'high',
        confidence_score: 0.92,
        is_fallback: false,
        query: 'Library timings',
      }),
    }) as any

    const res = await sendChatMessage('Library timings', null, [], null)
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/chat'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          query: 'Library timings',
          department: null,
          session_id: null,
          history: [],
        }),
      })
    )
    expect(res.answer).toBe('Library is open 9 AM to 6 PM')
  })

  it('correctly maps Masters programs to 4 semesters and B.Tech to 8 semesters', async () => {
    const { isMastersBranch, getMaxSemesters } = await import('../src/App')

    expect(isMastersBranch('Master of Computer Applications')).toBe(true)
    expect(isMastersBranch('Master of Business Administration')).toBe(true)
    expect(isMastersBranch('MCA')).toBe(true)
    expect(isMastersBranch('Computer Science & Engineering')).toBe(false)
    expect(isMastersBranch('Mechanical Engineering')).toBe(false)

    expect(getMaxSemesters('Master of Computer Applications')).toBe(4)
    expect(getMaxSemesters('Master of Business Administration')).toBe(4)
    expect(getMaxSemesters('Computer Science & Engineering')).toBe(8)
    expect(getMaxSemesters('Civil Engineering')).toBe(8)
  })

  it('sendChatMessage includes closely resembled questions suggestions when query is low confidence', async () => {
    const mockFallbackResponse = {
      answer: "I couldn't find a confident answer in the verified institutional circulars.",
      sources: [],
      confidence: 'low',
      confidence_score: 0.22,
      is_fallback: true,
      query: 'What is rocket propulsion syllabus?',
      query_id: 'fallback-1',
      suggestions: [
        'Mid-term exam schedule for CSE',
        'Semester fee notice and due dates',
        'Mercy exam rules for B.Tech',
      ],
    }

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFallbackResponse,
    }) as any

    const result = await sendChatMessage('What is rocket propulsion syllabus?', null)
    expect(result.is_fallback).toBe(true)
    expect(result.suggestions).toBeDefined()
    expect(result.suggestions?.length).toBe(3)
    expect(result.suggestions?.[0]).toBe('Mid-term exam schedule for CSE')
  })

  it('STARTER_QUESTIONS strictly includes the 4 verified institutional prompts', async () => {
    const { STARTER_QUESTIONS } = await import('../src/App')

    expect(STARTER_QUESTIONS.length).toBe(4)
    const titles = STARTER_QUESTIONS.map((q) => q.title)

    expect(titles).toContain('Mid-term exam schedule for CSE')
    expect(titles).toContain('Semester fee notice and due dates')
    expect(titles).toContain('Mercy exam rules for B.Tech')
    expect(titles).toContain('Central Library book issue timings')
  })
})
