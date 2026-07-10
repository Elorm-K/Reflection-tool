/* Instructor review-board types — the ONLY module in the frontend where
 * demographic fields exist.
 *
 * These values are served exclusively by the authenticated instructor
 * review endpoints, rendered exclusively by features/reviewBoard/, and are
 * never persisted client-side. Importing this module from student routes
 * or shared UI is forbidden by the ESLint no-restricted-imports boundary. */

import type { ChosenMeeting, MatchConfig, Proposal } from './common'

export interface ReviewStudent {
  name: string
  gender: string
  disability: string
  availability: boolean[]
  free_slot_count: number
}

export interface ReviewBoard {
  proposal: Proposal
  students: Record<string, ReviewStudent>
  config: MatchConfig
  meetings: Record<string, ChosenMeeting>
}

export interface GroupComposition {
  group_id: number
  size: number
  meeting_slots: string[]
  gender_composition: Record<string, number>
  disability_composition: Record<string, number>
  gender_homogeneity: number | null
  disability_homogeneity: number | null
}

export interface CompositionView {
  groups: GroupComposition[]
  unplaced: { student_id: string; reason: string }[]
  warnings: string[]
}
