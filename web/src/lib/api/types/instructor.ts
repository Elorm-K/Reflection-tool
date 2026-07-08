/* Instructor portal types — everything EXCEPT the review board.
 * Demographic-free: aggregates and demographics live in types/review.ts. */

import type { LifecycleStatus, MatchConfig } from './common'

export interface InstructorMe {
  id: number
  email: string
  name: string
}

export interface ClassInfo {
  id: number
  name: string
  term: string
  class_code: string
  timezone: string
  archived: number
}

export interface RosterStudent {
  student_id: string
  name: string
  joined: boolean
}

export interface CycleInfo {
  id: number
  class_id: number
  label: string
  deadline: string | null
  status: LifecycleStatus
  proposal_rev: number
  reviewed_rev: number
  config: MatchConfig
  created_at: string
}

export interface RosterStatus {
  roster_count: number
  joined_count: number
  submitted_count: number
  missing: string[]
  gender_counts: Record<string, number>
  disability_counts: Record<string, number>
  min_free_slots: number
  median_free_slots: number
  students_below_min_overlap: number
}

export interface AuditEntry {
  id: number
  actor: string
  action: string
  detail: string
  created_at: string
}

export interface ExplainPlaced {
  student_id: string
  group_id: number
  group_size: number
  shared_slot_count: number
  meeting_slots: string[]
  min_overlap_required: number
  status: LifecycleStatus
}

export interface ExplainUnplaced {
  student_id: string
  unplaced: true
  reason: string | null
}
