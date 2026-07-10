/* Review-board API — the only client module that fetches per-student
 * demographics. Import restricted to features/reviewBoard/ (ESLint boundary). */

import { api } from './client'
import type { Proposal } from './types/common'
import type { CompositionView, ReviewBoard } from './types/review'

export interface EditRequest {
  action: 'move' | 'assign'
  student_id: string
  to_group: number
  allow_oversize?: boolean
  allow_low_overlap?: boolean
}

export const reviewApi = {
  board: (cycleId: number) => api<ReviewBoard>('GET', `/api/cycles/${cycleId}/review-board`),

  composition: (cycleId: number) =>
    api<CompositionView>('GET', `/api/cycles/${cycleId}/composition`),

  edit: (cycleId: number, edit: EditRequest) =>
    api<Proposal>('POST', `/api/cycles/${cycleId}/edits`, edit),

  // Post-publish move/assign: the server demands confirm=true (groups are
  // live) and records notifications for every affected student.
  reassign: (cycleId: number, edit: EditRequest) =>
    api<{ proposal: Proposal; notified: number }>(
      'POST',
      `/api/cycles/${cycleId}/reassignments`,
      { ...edit, confirm: true },
    ),
}
