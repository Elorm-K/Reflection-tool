import { api } from './client'
import type {
  JoinResponse,
  MessagesResponse,
  StudentGroupView,
  StudentMe,
  StudentUnplacedView,
} from './types/student'

export const studentApi = {
  join: (class_code: string, student_id: string) =>
    api<JoinResponse>('POST', '/api/join', { class_code, student_id }),

  me: () => api<StudentMe>('GET', '/api/me'),

  submitAvailability: (slots: boolean[]) =>
    api<{ ok: boolean; slots_selected: number }>('PUT', '/api/me/availability', { slots }),

  submitSurvey: (answers: { gender?: string; disability?: string } | { skip: true }) =>
    api<{ ok: boolean }>('PUT', '/api/me/survey', answers),

  myGroup: () => api<StudentGroupView | StudentUnplacedView>('GET', '/api/me/group'),

  messages: (since = 0) =>
    api<MessagesResponse>('GET', `/api/me/group/messages?since=${since}`),

  sendMessage: (body: string) =>
    api<{ id: number }>('POST', '/api/me/group/messages', { body }),
}
