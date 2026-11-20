import { describe, it, expect, vi } from 'vitest'
import { DEPARTMENTS } from '../src/components/DepartmentSelector'
import { sendChatMessage, sendChatFeedback } from '../src/api/chat'

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
        }),
      })
    )
    expect(result.status).toBe('success')
  })
})
