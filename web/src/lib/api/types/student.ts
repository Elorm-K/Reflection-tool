/* Student-facing payload types.
 *
 * PRIVACY BOUNDARY: these types deliberately have no gender/disability
 * fields, mirroring the server's assert_no_demographics guarantee. Do not
 * add demographic fields here — they exist only in types/review.ts, which
 * student routes are lint-forbidden to import. */

import type { ChatMessage, GridConfig, LifecycleStatus } from './common'

export interface JoinResponse {
  token: string
  student_id: string
  name: string
  class_name: string
}

export interface StudentMe {
  student_id: string
  name: string
  cycle: {
    label: string
    deadline: string | null
    phase: LifecycleStatus
    grid: GridConfig
  } | null
  availability_submitted: boolean
  survey_submitted: boolean
}

export interface StudentGroupView {
  group_number: number
  members: string[]
  meeting_slots: string[]
}

export interface StudentUnplacedView {
  message: string
}

export interface MessagesResponse {
  messages: ChatMessage[]
}

export interface StudentNotification {
  id: number
  kind: 'group-changed' | 'group-updated'
  body: string
  created_at: string
  read_at: string | null
}

export interface NotificationsResponse {
  notifications: StudentNotification[]
  unread: number
}
