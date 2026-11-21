import { BubbleMessage } from '../components/MessageBubble'
import {
  fetchChatSessions,
  fetchChatSession,
  createChatSession,
  updateChatSession,
  deleteChatSession,
} from '../api/chat'

export interface Conversation {
  id: string
  student_id: string
  title: string
  is_pinned: boolean
  is_archived: boolean
  created_at: string
  updated_at: string
  messages: BubbleMessage[]
}

const DEFAULT_STUDENT_ID = 'student_guest'
const STORAGE_PREFIX = 'edusync_chats_'

const memoryFallback = new Map<string, string>()

function getStorage() {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage
  }
  if (typeof globalThis !== 'undefined' && (globalThis as any).localStorage) {
    return (globalThis as any).localStorage
  }
  return {
    getItem: (k: string) => memoryFallback.get(k) || null,
    setItem: (k: string, v: string) => {
      memoryFallback.set(k, v)
    },
    removeItem: (k: string) => {
      memoryFallback.delete(k)
    },
  }
}

export function getActiveStudentId(): string {
  try {
    return getStorage().getItem('edusync_active_student_id') || DEFAULT_STUDENT_ID
  } catch {
    return DEFAULT_STUDENT_ID
  }
}

export function setActiveStudentId(studentId: string): void {
  try {
    getStorage().setItem('edusync_active_student_id', studentId.trim() || DEFAULT_STUDENT_ID)
  } catch {}
}

export function createWelcomeMessage(): BubbleMessage {
  return {
    id: 'welcome-1',
    sender: 'assistant',
    text: 'Hello! I am EduSync, the institutional AI assistant for Engineering College Ajmer. Ask me about exam schedules, fees, syllabi, or official circulars.',
    timestamp: 'Today 9:41 AM',
    suggestions: [
      'Mid-term exam schedule for CSE',
      'Semester fee notice and due dates',
      'Mercy exam rules for B.Tech',
      'Central Library book issue timings',
    ],
  }
}

export function createNewConversation(
  studentId: string = getActiveStudentId(),
  title: string = 'New Chat'
): Conversation {
  const now = new Date().toISOString()
  return {
    id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `chat_${Date.now()}`,
    student_id: studentId,
    title,
    is_pinned: false,
    is_archived: false,
    created_at: now,
    updated_at: now,
    messages: [createWelcomeMessage()],
  }
}

export function loadLocalConversations(studentId: string = getActiveStudentId()): Conversation[] {
  try {
    const raw = getStorage().getItem(`${STORAGE_PREFIX}${studentId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (err) {
    console.warn('Failed to load local conversations:', err)
    return []
  }
}

export function saveLocalConversations(
  conversations: Conversation[],
  studentId: string = getActiveStudentId()
): void {
  try {
    getStorage().setItem(`${STORAGE_PREFIX}${studentId}`, JSON.stringify(conversations))
  } catch (err) {
    console.warn('Failed to save local conversations:', err)
  }
}

/**
 * Syncs local conversations with PostgreSQL server chat sessions asynchronously
 */
export async function syncConversationsWithServer(
  localConvs: Conversation[],
  studentId: string = getActiveStudentId()
): Promise<Conversation[]> {
  try {
    const serverSummaries = await fetchChatSessions(studentId)
    if (!serverSummaries || serverSummaries.length === 0) {
      // Only seed local conversations if they have real user dialogue
      const realLocal = localConvs.filter((c) =>
        c.messages.some((m) => m.sender === 'user')
      )
      for (const conv of realLocal) {
        createChatSession(studentId, conv.title, conv.messages).catch(() => {})
      }
      return realLocal
    }

    // Merge strategy: preserve messages from local, reconcile metadata from server
    const localMap = new Map<string, Conversation>(localConvs.map((c) => [c.id, c]))
    const merged: Conversation[] = []

    for (const s of serverSummaries) {
      const local = localMap.get(s.id)
      if (local && local.messages.length > 0) {
        merged.push({
          ...local,
          title: s.title,
          is_pinned: s.is_pinned,
          is_archived: s.is_archived,
          updated_at: s.updated_at,
        })
        localMap.delete(s.id)
      } else {
        merged.push({
          id: s.id,
          student_id: s.student_id,
          title: s.title,
          is_pinned: s.is_pinned,
          is_archived: s.is_archived,
          created_at: s.created_at,
          updated_at: s.updated_at,
          messages: [],
        })
      }
    }

    // Only append locally created conversations that have real user dialogue and aren't on server
    for (const unsynced of localMap.values()) {
      if (unsynced.messages.some((m) => m.sender === 'user')) {
        merged.push(unsynced)
        createChatSession(studentId, unsynced.title, unsynced.messages).catch(() => {})
      }
    }

    saveLocalConversations(merged, studentId)
    return merged
  } catch {
    return localConvs
  }
}

export async function loadSessionMessagesFromServer(
  sessionId: string
): Promise<BubbleMessage[]> {
  try {
    const detail = await fetchChatSession(sessionId)
    if (detail && Array.isArray(detail.messages)) {
      return detail.messages as BubbleMessage[]
    }
  } catch (err) {
    console.warn('Failed to load session messages from server:', err)
  }
  return []
}

export async function backgroundUpdateServerSession(
  conv: Conversation
): Promise<void> {
  try {
    await updateChatSession(conv.id, {
      title: conv.title,
      is_pinned: conv.is_pinned,
      is_archived: conv.is_archived,
      messages: conv.messages,
    })
  } catch {}
}

export async function backgroundDeleteServerSession(
  id: string
): Promise<void> {
  try {
    await deleteChatSession(id)
  } catch {}
}
