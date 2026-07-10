import { api } from './client'
import type { ChosenMeeting } from './types/common'
import type {
  JoinResponse,
  MessagesResponse,
  NotificationsResponse,
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

  setGroupMeeting: (label: string) =>
    api<{ ok: boolean; chosen_meeting: ChosenMeeting }>('PUT', '/api/me/group/meeting', {
      label,
    }),

  notifications: () => api<NotificationsResponse>('GET', '/api/me/notifications'),

  markNotificationsRead: () =>
    api<{ ok: boolean; marked: number }>('POST', '/api/me/notifications/read'),
}
