import { api } from './client'
import type { MatchConfig, MessagesResponse, Proposal } from './types/common'
import type {
  AuditEntry,
  ClassInfo,
  CycleInfo,
  ExplainPlaced,
  ExplainUnplaced,
  InstructorMe,
  RosterStatus,
  RosterStudent,
} from './types/instructor'

export const instructorApi = {
  register: (email: string, password: string, name: string) =>
    api<{ token: string }>('POST', '/api/instructor/register', { email, password, name }),

  login: (email: string, password: string) =>
    api<{ token: string }>('POST', '/api/instructor/login', { email, password }),

  me: () => api<InstructorMe>('GET', '/api/instructor/me'),

  classes: () => api<ClassInfo[]>('GET', '/api/classes'),

  createClass: (name: string, term: string) =>
    api<ClassInfo>('POST', '/api/classes', { name, term }),

  getClass: (id: number) => api<ClassInfo>('GET', `/api/classes/${id}`),

  roster: (classId: number) =>
    api<{ students: RosterStudent[] }>('GET', `/api/classes/${classId}/roster`),

  uploadRoster: (classId: number, students: { student_id: string; name: string }[]) =>
    api<{ count: number }>('PUT', `/api/classes/${classId}/roster`, { students }),

  resetClaim: (classId: number, student_id: string) =>
    api<{ ok: boolean }>('POST', `/api/classes/${classId}/reset-claim`, { student_id }),

  cycles: (classId: number) => api<CycleInfo[]>('GET', `/api/classes/${classId}/cycles`),

  createCycle: (classId: number, label: string, config: Partial<MatchConfig>, deadline?: string) =>
    api<CycleInfo>('POST', `/api/classes/${classId}/cycles`, { label, config, deadline }),

  getCycle: (cycleId: number) => api<CycleInfo>('GET', `/api/cycles/${cycleId}`),

  patchConfig: (cycleId: number, config: Partial<MatchConfig>) =>
    api<CycleInfo>('PATCH', `/api/cycles/${cycleId}/config`, config),

  rosterStatus: (cycleId: number) =>
    api<RosterStatus>('GET', `/api/cycles/${cycleId}/roster-status`),

  match: (cycleId: number) => api<Proposal>('POST', `/api/cycles/${cycleId}/match`),

  proposal: (cycleId: number) => api<Proposal>('GET', `/api/cycles/${cycleId}/proposal`),

  approve: (cycleId: number) =>
    api<{ status: string }>('POST', `/api/cycles/${cycleId}/approve`),

  publish: (cycleId: number) =>
    api<{ status: string; notified: number }>('POST', `/api/cycles/${cycleId}/publish`),

  notifications: (cycleId: number) =>
    api<Record<string, unknown>>('GET', `/api/cycles/${cycleId}/notifications`),

  explain: (cycleId: number, studentId: string) =>
    api<ExplainPlaced | ExplainUnplaced>('GET', `/api/cycles/${cycleId}/explain/${studentId}`),

  audit: (cycleId: number) =>
    api<{ entries: AuditEntry[] }>('GET', `/api/cycles/${cycleId}/audit`),

  groupMessages: (cycleId: number, groupId: number) =>
    api<MessagesResponse>('GET', `/api/cycles/${cycleId}/groups/${groupId}/messages`),

  exportCsvUrl: (cycleId: number) => `/api/cycles/${cycleId}/export.csv`,
}
